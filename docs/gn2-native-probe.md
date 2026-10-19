# GN2 0.6 experimental — native PS5-to-PS5 UDP reachability

**This is a diagnostic, NOT playable Internet netplay.** The objective is to test whether PS5s in two separate houses can discover publicly mapped UDP endpoints and exchange direct test messages without either home running a companion PC.

Stable GN1 v0.5 is preserved on main. GN2 development is isolated on feature/native-internet-p2p.

## Architecture

- Both PS5s connect outbound to a GN2 service using verified TLS on TCP 43380.
- Each console opens a UDP socket, registers a unique short-lived token at the server's UDP port 43379, and lets the server observe its public IPv4 address and NAT-mapped port.
- The server returns the other console's observed endpoint and test-only random token over the existing verified TLS connection.
- Both consoles send direct UDP PUNCH messages to their peer and report whether a packet from the expected endpoint containing the expected token arrived.
- No ROMs, game inputs, state data, or saved files are exchanged by the probe. Tokens are not gameplay encryption keys. This is a limited diagnostic and is NOT full ICE.

## What is necessary to test across two homes

A small hosted GN2 rendezvous server with a real DNS name. The code is in this feature branch but no public server has been deployed. No PC must remain on at either PS5 home during gameplay once the complete system exists.

On a remotely hosted test server you control:
1. Point a DNS A record such as gn2.example.net to its public IPv4 address. Replace this example with your actual domain.
2. Obtain a publicly trusted TLS certificate for that hostname and protect the corresponding private key outside the repository.
3. Allow TCP 43380 and UDP 43379 on the **server firewall only**. DO NOT forward PS5 game, exploit loader, or helper ports on a home router.
4. Use an unprivileged OS account with suitable service-level rate limiting, monitoring and firewall restrictions, then run:

    python3 GenesisPlusGXPS5-Netplay-v0.4-GitHub-Build/genplusgx-netplay-kit/netplay/rendezvous.py --host 0.0.0.0 --tcp-port 43380 --udp-port 43379 --tls-cert /path/to/fullchain.pem --tls-key /path/to/privkey.pem

**Security warning:** the GN2 service has basic room caps, expiry, and random tokens, but has not been security audited or production-hardened. Run only a controlled test service, not public matchmaking.

## On two PS5s in different houses

1. Install the same GN2 0.6 development ELF on both consoles after successful CI compilation. This experimental build has separate app data/title from stock Genesis Plus GX.
2. In Settings -> NETPLAY select **Host** on one PS5 and **Join** on the other.
3. Set **Relay host** on both to the GN2 rendezvous service's REAL public TLS DNS hostname (this diagnostic reuses the existing hostname field).
4. Enter the same unpredictable **16–32-character alphanumeric** room on both consoles.
5. Both press **Test Internet UDP route (X)** within 75 seconds.
6. Successful output reports **UDP peer route reachable**. Failure may indicate NAT/CGNAT, UDP blocking, TLS DNS/certificate trouble, bad room or unresponsive second console.

Both consoles initiate outbound connections. There is no PS5-side VPN and no household PC required. This test does not yet launch synchronized gameplay.

## Local test commands (Linux host)

    g++ -std=c++17 -Wall -Wextra -Werror -Inetplay netplay/fe_p2p_probe.cpp tests/p2p_probe_smoke.cpp -o tests/p2p_probe_smoke
    python3 -m unittest discover -s tests -p test_p2p_probe.py -v

The CI/native host version is explicitly restricted to plaintext TCP on 127.0.0.1 for repeatable localhost tests. The PS5 GN2 client requires CA-verified TLS.

## Remaining to make Internet gameplay work

- Authenticated, encrypted UDP peer gameplay (never reuse the probe token as a key).
- Reliable ordered input transport, congestion/latency management, replay checks and deterministic sync.
- Standards-based ICE/STUN/TURN-class NAT negotiation and a secure relay fallback for NATs that do not permit direct traversal.
- Polished Create Room / Join Room UI and real console latency, loss and desync testing.

No direct Internet gameplay claim can be made until the gameplay protocol and physical two-console testing are completed.
