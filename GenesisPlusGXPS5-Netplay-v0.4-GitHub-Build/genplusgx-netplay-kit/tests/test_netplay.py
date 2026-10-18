import asyncio
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import ssl
import tempfile
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SERVER=ROOT/'netplay'/'relay.py'
CLIENT=ROOT/'tests'/'netplay_client_smoke'

def get_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

class NetplayTests(unittest.TestCase):
    def setUp(self):
        self.port=get_port()
        self.server=subprocess.Popen([sys.executable,str(SERVER),'--port',str(self.port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for i in range(100):
            try:
                with socket.create_connection(('127.0.0.1',self.port),.1):
                    break
            except OSError:
                time.sleep(.03)
        else: self.fail('server did not start')

    def tearDown(self):
        self.server.terminate()
        try: self.server.communicate(timeout=3)
        except subprocess.TimeoutExpired: self.server.kill()

    def test_two_clients_frames(self):
        a=subprocess.Popen([str(CLIENT),'127.0.0.1',str(self.port),'1','m7k9Pq42'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        b=subprocess.Popen([str(CLIENT),'127.0.0.1',str(self.port),'2','m7k9Pq42'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ao,ae=a.communicate(timeout=20)
        bo,be=b.communicate(timeout=20)
        self.assertEqual(a.returncode,0,ae.decode())
        self.assertEqual(b.returncode,0,be.decode())
        self.assertIn(b'60 synchronized frames OK',ao)
        self.assertIn(b'60 synchronized frames OK',bo)

    def test_direct_p2p_two_clients_frames(self):
        # No relay process participates in this test; the host listens itself.
        port = get_port()
        host = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '1', 'directAbcd42', '1'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Allow the host to bind its listening socket before guest dials.
            time.sleep(.15)
            guest = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '2', 'directAbcd42', '1'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            go,ge = guest.communicate(timeout=20)
            ho,he = host.communicate(timeout=20)
            self.assertEqual(host.returncode, 0, he.decode())
            self.assertEqual(guest.returncode, 0, ge.decode())
            self.assertIn(b'60 synchronized frames OK', ho)
            self.assertIn(b'60 synchronized frames OK', go)
        finally:
            if host.poll() is None:
                host.kill();host.communicate(timeout=2)

    def test_auto_prefers_direct(self):
        # The relay is running but should not participate in the game.
        port = get_port()
        host = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '1', 'autoDirectRoom42', '2', '127.0.0.1', str(self.port)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(.15)
            guest = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '2', 'autoDirectRoom42', '2', '127.0.0.1', str(self.port)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            go,ge = guest.communicate(timeout=20)
            ho,he = host.communicate(timeout=20)
            self.assertEqual(host.returncode, 0, he.decode())
            self.assertEqual(guest.returncode, 0, ge.decode())
            self.assertIn(b'60 synchronized frames OK', ho)
            self.assertIn(b'transport=direct', ho)
            self.assertIn(b'60 synchronized frames OK', go)
            self.assertIn(b'transport=direct', go)
        finally:
            if host.poll() is None: host.kill();host.communicate(timeout=2)

    def test_auto_falls_back_to_relay(self):
        # No direct host is reachable initially: both switch to the same relay.
        port = get_port()
        host = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '1', 'autoRelayRoom42', '2', '127.0.0.1', str(self.port)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Start guest after host's direct listener has stopped; both use relay fallback.
            time.sleep(4)
            guest = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '2', 'autoRelayRoom42', '2', '127.0.0.1', str(self.port)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            go,ge = guest.communicate(timeout=20)
            ho,he = host.communicate(timeout=20)
            self.assertEqual(host.returncode, 0, he.decode())
            self.assertEqual(guest.returncode, 0, ge.decode())
            self.assertIn(b'60 synchronized frames OK', ho)
            self.assertIn(b'transport=relay', ho)
            self.assertIn(b'60 synchronized frames OK', go)
            self.assertIn(b'transport=relay', go)
        finally:
            if host.poll() is None: host.kill();host.communicate(timeout=2)

    def test_direct_p2p_room_rejected(self):
        port = get_port()
        host = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '1', 'directAbcd42', '1'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(.15)
            guest = subprocess.Popen([str(CLIENT), '127.0.0.1', str(port), '2', 'different987', '1'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            go,ge = guest.communicate(timeout=10)
            ho,he = host.communicate(timeout=10)
            self.assertNotEqual(host.returncode, 0)
            self.assertNotEqual(guest.returncode, 0)
            self.assertIn(b'room', he.lower())
        finally:
            if host.poll() is None:
                host.kill();host.communicate(timeout=2)

    def test_mismatched_rom_rejected(self):
        async def go():
            h_r,h_w=await asyncio.open_connection('127.0.0.1',self.port)
            h_w.write(b'GN1 HOST abcdefgh 0123456789abcdef 1111111111111111\n')
            await h_w.drain()
            self.assertEqual(await h_r.readline(),b'WAIT\n')
            j_r,j_w=await asyncio.open_connection('127.0.0.1',self.port)
            j_w.write(b'GN1 JOIN abcdefgh ffffffffffffffff 1111111111111111\n')
            await j_w.drain()
            self.assertEqual(await j_r.readline(),b'ERROR game_or_settings_mismatch\n')
            # A rejected guest must NOT destroy the valid waiting host room.
            good_r,good_w=await asyncio.open_connection('127.0.0.1',self.port)
            good_w.write(b'GN1 JOIN abcdefgh 0123456789abcdef 1111111111111111\n')
            await good_w.drain()
            self.assertEqual(await good_r.readline(),b'READY\n')
            self.assertEqual(await h_r.readline(),b'READY\n')
            h_w.close();j_w.close();good_w.close()
            await good_w.wait_closed()
            await h_w.wait_closed();await j_w.wait_closed()
        asyncio.run(go())

    def test_join_first_and_state_desync(self):
        async def go():
            jr,jw=await asyncio.open_connection('127.0.0.1',self.port)
            jw.write(b'GN1 JOIN qwerty42 0123456789abcdef 1111111111111111\n'); await jw.drain()
            self.assertEqual(await jr.readline(),b'WAIT\n')
            hr,hw=await asyncio.open_connection('127.0.0.1',self.port)
            hw.write(b'GN1 HOST qwerty42 0123456789abcdef 1111111111111111\n'); await hw.drain()
            self.assertEqual(await hr.readline(),b'READY\n')
            self.assertEqual(await jr.readline(),b'READY\n')
            hw.write(b'FRAME 0 0000 1234567890abcdef\n')
            jw.write(b'FRAME 0 0000 fedcba0987654321\n')
            await hw.drain();await jw.drain()
            self.assertEqual(await hr.readline(),b'ERROR emulator_state_desynchronized\n')
            self.assertEqual(await jr.readline(),b'ERROR emulator_state_desynchronized\n')
            hw.close();jw.close();await hw.wait_closed();await jw.wait_closed()
        asyncio.run(go())

    def test_public_plaintext_rejected(self):
        # Binding all interfaces without TLS must fail closed.
        run=subprocess.run([sys.executable,str(SERVER),'--host','0.0.0.0','--port','0'],
                           capture_output=True, text=True, timeout=5)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('Refusing', run.stderr)

    def test_tls_room_handshake(self):
        if not shutil.which('openssl'):
            self.skipTest('openssl not installed on test host')
        with tempfile.TemporaryDirectory() as d:
            key=pathlib.Path(d)/'key.pem'; cert=pathlib.Path(d)/'cert.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                            '-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost',
                            '-days','1'],check=True,capture_output=True)
            port=get_port()
            relay=subprocess.Popen([sys.executable,str(SERVER),'--host','127.0.0.1','--port',str(port),
                                    '--tls-cert',str(cert),'--tls-key',str(key)],
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(('127.0.0.1',port),.1):
                            break
                    except OSError:
                        time.sleep(.03)
                else:
                    self.fail('TLS relay did not start')
                async def go():
                    ctx=ssl.create_default_context(cafile=str(cert))
                    a,aw=await asyncio.open_connection('127.0.0.1',port,ssl=ctx,server_hostname='localhost')
                    aw.write(b'GN1 HOST tlsroom44 0123456789abcdef 1111111111111111\n');await aw.drain()
                    self.assertEqual(await a.readline(),b'WAIT\n')
                    b,bw=await asyncio.open_connection('127.0.0.1',port,ssl=ctx,server_hostname='localhost')
                    bw.write(b'GN1 JOIN tlsroom44 0123456789abcdef 1111111111111111\n');await bw.drain()
                    self.assertEqual(await b.readline(),b'READY\n')
                    self.assertEqual(await a.readline(),b'READY\n')
                    aw.close();bw.close()
                    await aw.wait_closed();await bw.wait_closed()
                asyncio.run(go())
            finally:
                relay.terminate();relay.communicate(timeout=3)

    def test_duplicate_host_rejected(self):
        async def go():
            x=await asyncio.open_connection('127.0.0.1',self.port)
            a,b=x
            b.write(b'GN1 HOST abcdefgh 0123456789abcdef 1111111111111111\n');await b.drain()
            self.assertEqual(await a.readline(),b'WAIT\n')
            c,d=await asyncio.open_connection('127.0.0.1',self.port)
            d.write(b'GN1 HOST abcdefgh 0123456789abcdef 1111111111111111\n');await d.drain()
            self.assertEqual(await c.readline(),b'ERROR room_taken\n')
            b.close();d.close();await b.wait_closed();await d.wait_closed()
        asyncio.run(go())

if __name__=='__main__': unittest.main(verbosity=2)
