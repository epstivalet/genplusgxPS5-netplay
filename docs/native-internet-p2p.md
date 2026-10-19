# PS5-native Internet netplay architecture (no companion PC)

## Product requirement

Two players, two PS5 consoles in different households, no Windows/Mac/Linux computer needed during play. A small hosted matchmaking/signaling service is acceptable because it is not a device at either player's home. The consoles must exchange game inputs directly when NAT permits, with a secure relay fallback for difficult network configurations.

**Current reality (v0.5):** Direct TCP is for reachable LAN/VPN routes and is plaintext. Automatic tries TCP direct before a separately deployed TLS relay, but it does *not* do hole punching, Internet discovery, encryption of direct traffic, ICE, or matchmaking. Do not port-forward direct TCP/43378 to the Internet. No public production service is currently deployed. The on-console field editor was confirmed working on physical PS5; two-console netplay is not yet confirmed.

## Target user experience

1. Player A chooses Online -> Create Room -> selects a Genesis cartridge ROM from their own library.
2. Player B chooses Online -> Join Room -> enters a short room code (or receives an invite later).
3. Each console makes an outbound authenticated connection to the rendezvous service and exchanges game/session fingerprints (no game files are uploaded).
4. Both PS5s collect candidate addresses using STUN and try simultaneous UDP connectivity checks (ICE-like behavior; favor a mature standards-conforming ICE implementation over an ad-hoc protocol).
5. Establish authenticated, end-to-end encrypted transport *before* passing game inputs, then verify the game/configuration and deterministic initial state.
6. Prefer direct PS5 <-> PS5 UDP when feasible. If that fails, automatically use an authenticated encrypted relay path; show which path was chosen.
7. Display Waiting, Negotiating, Connected Direct/Relayed, and Clear Error states. Only then start synchronized frames.

## Components

- **Console-native networking:** UDP sockets and timers on PS5, direct connection checks, NAT binding keepalives, stable session identifiers and timeout handling. Keep a reliable ordered framing layer for GN1 frame inputs or adapt an audited reliable UDP transport. No local PC.
- **Rendezvous/control service:** small TLS-secured HTTPS/WebSocket or equivalent application protocol keyed by room code; manages rooms and rate limits, returns ephemeral candidate addresses and session identity data; does not need ROM files or emulator state.
- **STUN + ICE:** discover public mapped endpoints, exchange local and server-reflexive candidates, perform checks from both peers; detect when direct connectivity is blocked. Implement standards-based RFC 8445 or use a vetted existing ICE stack compatible with the PS5 SDK.
- **Security:** authenticate the peer with a cryptographically random invite token or verified identity and bind it to the ephemeral encryption key exchange, preferably an audited DTLS/Noise/WireGuard-class transport. A human-memorable room code alone is not a strong encryption key. Use replay protection, session expiry, rate limits, and safe parsing. Do not expose PS5 loader/helper services.
- **Fallback:** re-use/adapt existing TLS relay for gameplay if direct fails; relay must be deployed separately. Avoid downgrade attacks; retain end-to-end game transport protection when switching routes.
- **Session compatibility:** exact ROM hashes, emulator/build and settings fingerprints, initial SRAM/state identity, frame ordering and desync detection. No copyrighted ROM transfer.
- **Operations:** hosted DNS endpoint with valid TLS certificate, abuse limits, monitoring, error diagnostics without exposing user addresses, and bounded resource limits.

## Milestones and acceptance tests

**M1: Rendezvous protocol, native client, deterministic tests.** Implement creating/joining a room through outgoing PS5 connections, status UI and unit/integration tests using simulated peers. No real internet promise yet.

**M2: Native encrypted UDP transport.** Integrate proven cryptography and authenticated handshake. Test positive/negative cases, replay, tampering, timeouts, and input synchronization on native/host CI builds.

**M3: NAT traversal.** Collect candidates, exchange through rendezvous, ICE checks and switching to confirmed direct endpoint. Test two separate Internet connections with ordinary home NAT; verify via logs that packets go PS5 <-> PS5 rather than through a game relay.

**M4: Relay fallback.** Test hard NAT / CGNAT, restricted UDP and disconnects. Verify UI reports Relayed and session continues without any companion PC.

**M5: PS5 field test.** Install same build on both physical consoles in two houses, load same Genesis ROM and settings, join private room, measure desync/latency, verify no public port forwards or console-side VPN clients.

## Practical caveats

Some NAT combinations cannot establish direct end-to-end connections, even with ICE. A relay is essential for consistent success. A rendezvous service is also required for easy room-code discovery; it is *not* a PC in either home. Server hosting is an operational dependency and can be small, but it is not free by assumption. Starting from verified secure components is preferable to exposing the current plaintext proof-of-concept.

## Standards and references

- ICE NAT traversal: https://www.rfc-editor.org/rfc/rfc8445
- Tailscale direct versus relay behavior (reference architecture, not a requirement for PS5 users): https://tailscale.com/docs/reference/connection-types

The older docs/internet-p2p-test.md is an **optional temporary companion-PC workaround**, not the target solution.
