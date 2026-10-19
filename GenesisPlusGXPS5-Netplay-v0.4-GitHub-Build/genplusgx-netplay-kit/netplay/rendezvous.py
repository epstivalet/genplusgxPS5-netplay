#!/usr/bin/env python3
"""GN2 native Internet reachability diagnostic: TLS room rendezvous + UDP endpoint sampling.

This service does NOT carry gameplay traffic or provide a production-grade identity system.
The short-lived tokens authorize discovery of a peer's observed IPv4 endpoint only.
Run behind network-level rate limits, and never use these probe tokens as gameplay keys.
Non-loopback TCP listeners REQUIRE a trusted TLS certificate.
"""
import argparse
import asyncio
import ipaddress
import re
import secrets
import ssl
import time
from dataclasses import dataclass, field

HELLO = re.compile(rb"GN2 (HOST|JOIN) ([A-Za-z0-9]{16,32}) ([a-fA-F0-9]{16}) ([a-fA-F0-9]{16})\n")
REGISTER = re.compile(rb"GN2 REG ([a-f0-9]{32})\n")
MAX_ROOMS = 64
MAX_LINE = 140
ROOM_TIMEOUT = 75


@dataclass
class Entry:
    role: str
    writer: asyncio.StreamWriter
    token: str
    endpoint: tuple | None = None


@dataclass
class Room:
    code: str
    fingerprints: tuple
    peers: dict = field(default_factory=dict)
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    created: float = field(default_factory=time.monotonic)


class ProbeServer(asyncio.DatagramProtocol):
    def __init__(self, udp_port=43379):
        self.udp_port = udp_port
        self.rooms = {}
        self.tokens = {}
        self.udp = None

    def connection_made(self, transport):
        self.udp = transport

    def datagram_received(self, data, addr):
        m = REGISTER.fullmatch(data)
        if not m or len(data) > MAX_LINE:
            return
        token = m[1].decode("ascii")
        assignment = self.tokens.get(token)
        if assignment is None:
            return
        room, role = assignment
        # Tokens are unpredictable, issued only after TLS handshake; do not allow
        # registration for an expired/cleared session.
        if self.rooms.get(room.code) is not room:
            return
        peer = room.peers.get(role)
        if peer is None or peer.token != token:
            return
        try:
            ipaddress.IPv4Address(addr[0])
        except ipaddress.AddressValueError:
            return
        peer.endpoint = (addr[0], int(addr[1]))
        self.udp.sendto(b"GN2 OK\n", addr)
        if len(room.peers) == 2 and all(p.endpoint for p in room.peers.values()):
            room.ready.set()

    def remove(self, room):
        if self.rooms.get(room.code) is not room:
            return
        self.rooms.pop(room.code, None)
        for p in room.peers.values():
            self.tokens.pop(p.token, None)

    async def handle(self, reader, writer):
        room = None
        peer = None
        try:
            raw = await asyncio.wait_for(reader.readline(), 10)
            m = HELLO.fullmatch(raw) if len(raw) <= MAX_LINE else None
            if not m:
                writer.write(b"ERROR bad_handshake\n")
                await writer.drain()
                return
            role, code, game, settings = (v.decode("ascii") for v in m.groups())
            fingerprints = (game.lower(), settings.lower())
            room = self.rooms.get(code)
            if room is None:
                # Garbage collect stale rooms to bound memory usage.
                for old in list(self.rooms.values()):
                    if time.monotonic() - old.created > ROOM_TIMEOUT:
                        self.remove(old)
                if len(self.rooms) >= MAX_ROOMS:
                    writer.write(b"ERROR capacity\n")
                    await writer.drain()
                    return
                room = Room(code, fingerprints)
                self.rooms[code] = room
            if room.ready.is_set() or role in room.peers:
                writer.write(b"ERROR room_taken\n")
                await writer.drain()
                return
            if room.fingerprints != fingerprints:
                writer.write(b"ERROR game_or_settings_mismatch\n")
                await writer.drain()
                return
            peer = Entry(role, writer, secrets.token_hex(16))
            room.peers[role] = peer
            self.tokens[peer.token] = (room, role)
            writer.write(f"TOKEN {peer.token} {self.udp_port}\n".encode("ascii"))
            await writer.drain()
            await asyncio.wait_for(room.ready.wait(), ROOM_TIMEOUT)
            other = room.peers.get("JOIN" if role == "HOST" else "HOST")
            if other is None or other.endpoint is None:
                raise RuntimeError("peer missing")
            ip, port = other.endpoint
            # TLS conveys a one-time peer endpoint and the peer's probe token.
            # Tokens are for the reachability check only, never gameplay crypto.
            writer.write(f"PEER {ip} {port} {other.token}\n".encode("ascii"))
            await writer.drain()
            # Give clients a brief opportunity to complete UDP probing, before
            # their peer tokens are invalidated. No long-running idle sessions.
            await asyncio.sleep(8)
        except (asyncio.TimeoutError, ConnectionError, OSError, RuntimeError):
            if peer is not None:
                try:
                    writer.write(b"ERROR peer_timeout\n")
                    await writer.drain()
                except (ConnectionError, OSError):
                    pass
        finally:
            if room is not None:
                # A room ends if either peer disconnects; no orphaned tokens.
                self.remove(room)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


async def main(host="127.0.0.1", tcp_port=43380, udp_port=43379, cert=None, key=None):
    if bool(cert) != bool(key):
        raise ValueError("Both --tls-cert and --tls-key must be specified")
    if host not in ("127.0.0.1", "::1", "localhost") and not cert:
        raise ValueError("Refusing non-loopback plaintext GN2 signaling; supply TLS cert/key")
    ctx = None
    if cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
    probe = ProbeServer(udp_port)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: probe, local_addr=(host, udp_port))
    try:
        server = await asyncio.start_server(probe.handle, host, tcp_port, ssl=ctx,
                                            limit=MAX_LINE + 2, ssl_handshake_timeout=10 if ctx else None)
        print(f"GN2 signaling TCP {tcp_port}, UDP observation {udp_port} on {host}", flush=True)
        async with server:
            await server.serve_forever()
    finally:
        transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--tcp-port", type=int, default=43380)
    parser.add_argument("--udp-port", type=int, default=43379)
    parser.add_argument("--tls-cert")
    parser.add_argument("--tls-key")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.tcp_port, args.udp_port, args.tls_cert, args.tls_key))
