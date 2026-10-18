#!/usr/bin/env python3
"""GN1 two-player input relay. TLS required on all non-loopback listeners.

Line protocol:
  GN1 HOST|JOIN <8-32 alnum room> <16-hex game hash> <16-hex settings hash>\n
  WAIT / READY HOST|JOIN / ERROR <reason>\n
  FRAME <unsigned frame number> <4-hex button bits> <16-hex state digest>\n
  PAIR <frame> <host bits> <join bits>\n
No ROMs or state files are ever uploaded. Pre-alpha: do not publicly deploy without access controls and hardening.
"""
import argparse
import asyncio
from collections import defaultdict
import re
import socket
import ssl
import time

HELLO = re.compile(r"GN1 (HOST|JOIN) ([A-Za-z0-9]{8,32}) ([0-9a-fA-F]{16}) ([0-9a-fA-F]{16})")
FRAME = re.compile(r"FRAME ([0-9]{1,15}) ([0-9a-fA-F]{4}) ([0-9a-fA-F]{16})")
MAX_LINE = 160
MAX_FRAMES = 256
MAX_ROOMS = 64
ROOM_WAIT_SECONDS = 120
IDLE_SECONDS = 20

class Room:
    def __init__(self, code, hashes):
        self.code = code
        self.hashes = hashes
        self.peers = {}
        self.frames = defaultdict(dict)
        self.last_frame = {"HOST": -1, "JOIN": -1}
        self.ready = False

    async def broadcast(self, data):
        for w in tuple(self.peers.values()):
            w.write(data)
        await asyncio.gather(*(w.drain() for w in tuple(self.peers.values())), return_exceptions=True)

rooms = {}

async def send(writer, text):
    writer.write((text + "\n").encode('ascii'))
    await writer.drain()

async def serve(reader, writer):
    room = None
    role = None
    registered = False
    sock = writer.get_extra_info("socket")
    if sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        raw = await asyncio.wait_for(reader.readline(), 10)
        if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
            await send(writer, 'ERROR malformed_handshake')
            return
        hello = HELLO.fullmatch(raw.decode('ascii', 'strict').strip())
        if not hello:
            await send(writer, 'ERROR malformed_handshake')
            return
        role, code, game, settings = hello.groups()
        hashes = (game.lower(), settings.lower())
        room = rooms.get(code)
        if room:
            if room.ready or role in room.peers:
                await send(writer, 'ERROR room_taken')
                return
            if hashes != room.hashes:
                await send(writer, 'ERROR game_or_settings_mismatch')
                return
        else:
            if len(rooms) >= MAX_ROOMS:
                await send(writer, 'ERROR server_busy')
                return
            # Either player can arrive first; otherwise join-before-host races
            # cause silent 120-second waits on the host.
            room = Room(code, hashes)
            rooms[code] = room
        room.peers[role] = writer
        registered = True
        if len(room.peers) < 2:
            await send(writer, 'WAIT')
            deadline = time.monotonic() + ROOM_WAIT_SECONDS
            while not room.ready and time.monotonic() < deadline and not reader.at_eof():
                await asyncio.sleep(.1)
            if not room.ready:
                await send(writer, 'ERROR wait_timeout')
                return
        else:
            room.ready = True
            await room.broadcast(b'READY\n')
        # Monotonic frames prevent malicious/out-of-order packets from corrupting sessions.
        while room.ready:
            raw = await asyncio.wait_for(reader.readline(), IDLE_SECONDS)
            if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
                raise ValueError('bad_frame_line')
            m = FRAME.fullmatch(raw.decode('ascii', 'strict').strip())
            if not m:
                raise ValueError('bad_frame')
            frame, bits, digest = int(m[1]), m[2].lower(), m[3].lower()
            if frame != room.last_frame[role] + 1:
                raise ValueError('out_of_order')
            room.last_frame[role] = frame
            if len(room.frames) > MAX_FRAMES:
                raise ValueError('excessive_lead')
            bucket = room.frames[frame]
            bucket[role] = (bits, digest)
            if len(bucket) == 2:
                if (bucket['HOST'][1] != '0000000000000000' and \
                   bucket['JOIN'][1] != '0000000000000000' and \
                   bucket['HOST'][1] != bucket['JOIN'][1]):
                    await room.broadcast(b'ERROR emulator_state_desynchronized\n')
                    raise ValueError('desync')
                await room.broadcast(f'PAIR {frame} {bucket["HOST"][0]} {bucket["JOIN"][0]}\n'.encode('ascii'))
                room.frames.pop(frame, None)
    except (asyncio.TimeoutError, ConnectionError, UnicodeError, ValueError, OSError):
        pass
    finally:
        if registered and room and rooms.get(room.code) is room:
            rooms.pop(room.code, None)
            if room.ready:
                try:
                    await room.broadcast(b'ERROR peer_disconnected\n')
                except (ConnectionError, OSError):
                    pass
            for peer in room.peers.values():
                peer.close()
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass

async def main(host='127.0.0.1', port=43377, cert=None, key=None):
    if bool(cert) != bool(key):
        raise SystemExit('Both --tls-cert and --tls-key are required for TLS')
    if not cert and host not in ('127.0.0.1', '::1', 'localhost'):
        raise SystemExit('Refusing to expose an unencrypted GN1 relay outside localhost; configure TLS')
    tls = None
    if cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(cert, key)
    server = await asyncio.start_server(serve, host, port, limit=MAX_LINE+2, ssl=tls,
                                        ssl_handshake_timeout=10 if tls else None)
    print('GN1 relay listening on', ', '.join(str(s.getsockname()) for s in server.sockets), flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=43377)
    p.add_argument('--tls-cert', help='Full certificate chain PEM (from a trusted CA)')
    p.add_argument('--tls-key', help='Private key PEM')
    a = p.parse_args()
    asyncio.run(main(a.host, a.port, a.tls_cert, a.tls_key))
