"""GN2 rendezvous and native C++ UDP probe end-to-end tests (local sockets)."""
import asyncio
import pathlib
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "netplay" / "rendezvous.py"
CLIENT = ROOT / "tests" / "p2p_probe_smoke"
ROOM = "GenesisInternetTest2026"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RendezvousTests(unittest.TestCase):
    def setUp(self):
        self.tcp_port = free_port()
        self.udp_port = free_port()
        self.proc = self.launch()

    def launch(self, extra=()):
        proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--host", "127.0.0.1",
             "--tcp-port", str(self.tcp_port), "--udp-port", str(self.udp_port),
             *extra], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(100):
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                self.fail("GN2 rendezvous failed: " + stderr.decode())
            try:
                with socket.create_connection(("127.0.0.1", self.tcp_port), .1):
                    return proc
            except OSError:
                time.sleep(.03)
        proc.terminate()
        proc.communicate(timeout=3)
        self.fail("GN2 server was not reachable")

    def tearDown(self):
        self.proc.terminate()
        try:
            self.proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.communicate()

    def test_two_native_udp_probe_clients_direct(self):
        host = subprocess.Popen(
            [str(CLIENT), "127.0.0.1", str(self.tcp_port), str(self.udp_port), "1", ROOM],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(.15)
            join = subprocess.Popen(
                [str(CLIENT), "127.0.0.1", str(self.tcp_port), str(self.udp_port), "2", ROOM],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            jo, je = join.communicate(timeout=20)
            ho, he = host.communicate(timeout=20)
            self.assertEqual(join.returncode, 0, je.decode())
            self.assertEqual(host.returncode, 0, he.decode())
            self.assertIn(b"Direct UDP route reached", jo)
            self.assertIn(b"Direct UDP route reached", ho)
        finally:
            if host.poll() is None:
                host.kill()
                host.communicate()

    def test_bad_room_rejected_without_network(self):
        p = subprocess.run(
            [str(CLIENT), "127.0.0.1", str(self.tcp_port), str(self.udp_port),
             "1", "short"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"16-32", p.stderr)

    def test_rejected_join_does_not_destroy_valid_room(self):
        async def run():
            hr, hw = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            hw.write(f"GN2 HOST {ROOM} 1234567890abcdef 1111111111111111\n".encode())
            await hw.drain()
            self.assertTrue((await hr.readline()).startswith(b"TOKEN "))
            badr, badw = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            badw.write(f"GN2 JOIN {ROOM} ffffffffffffffff 1111111111111111\n".encode())
            await badw.drain()
            self.assertEqual(await badr.readline(), b"ERROR game_or_settings_mismatch\n")
            badw.close()
            await badw.wait_closed()
            gr, gw = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            gw.write(f"GN2 JOIN {ROOM} 1234567890abcdef 1111111111111111\n".encode())
            await gw.drain()
            self.assertTrue((await gr.readline()).startswith(b"TOKEN "))
            hw.close()
            gw.close()
            await hw.wait_closed()
            await gw.wait_closed()
        asyncio.run(run())

    def test_duplicate_role_does_not_destroy_room(self):
        async def run():
            hr, hw = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            hw.write(f"GN2 HOST {ROOM} 1234567890abcdef 1111111111111111\n".encode())
            await hw.drain()
            self.assertTrue((await hr.readline()).startswith(b"TOKEN "))
            r2, w2 = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            w2.write(f"GN2 HOST {ROOM} 1234567890abcdef 1111111111111111\n".encode())
            await w2.drain()
            self.assertEqual(await r2.readline(), b"ERROR room_taken\n")
            w2.close()
            await w2.wait_closed()
            r3, w3 = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            w3.write(f"GN2 JOIN {ROOM} 1234567890abcdef 1111111111111111\n".encode())
            await w3.drain()
            self.assertTrue((await r3.readline()).startswith(b"TOKEN "))
            hw.close()
            w3.close()
            await hw.wait_closed()
            await w3.wait_closed()
        asyncio.run(run())

    def test_udp_register_requires_issued_secret(self):
        # Unsolicited datagrams cannot produce a valid mapping ACK.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(.3)
        try:
            sock.sendto(b"GN2 REG " + b"0" * 32 + b"\n", ("127.0.0.1", self.udp_port))
            with self.assertRaises(socket.timeout):
                sock.recvfrom(100)
        finally:
            sock.close()

    def test_tls_signaling_smoke(self):
        if not shutil.which("openssl"):
            self.skipTest("openssl unavailable")
        with tempfile.TemporaryDirectory() as d:
            cert = pathlib.Path(d) / "cert.pem"
            key = pathlib.Path(d) / "key.pem"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                            "-nodes", "-keyout", str(key), "-out", str(cert),
                            "-subj", "/CN=localhost", "-days", "1"],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.proc.terminate()
            self.proc.communicate(timeout=3)
            self.proc = self.launch(("--tls-cert", str(cert), "--tls-key", str(key)))
            async def connect():
                ctx = ssl.create_default_context(cafile=str(cert))
                r, w = await asyncio.open_connection("127.0.0.1", self.tcp_port,
                                                       ssl=ctx, server_hostname="localhost")
                w.write(f"GN2 HOST {ROOM} 1234567890abcdef 1111111111111111\n".encode())
                await w.drain()
                self.assertTrue((await r.readline()).startswith(b"TOKEN "))
                w.close()
                await w.wait_closed()
            asyncio.run(connect())


if __name__ == "__main__":
    unittest.main(verbosity=2)
