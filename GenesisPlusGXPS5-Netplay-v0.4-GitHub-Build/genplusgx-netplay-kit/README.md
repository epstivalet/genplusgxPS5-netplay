# Genesis Plus GX PS5 — GN1 Netplay Development Kit v0.4

**Status: source-level proof of concept, not a tested/working PS5 Internet release.**
The development kit preserves the original **TLS relay** connection and adds **direct TCP P2P** and **Automatic (direct first → relay fallback)** (for LAN/trusted VPN testing). No PS5 ELF has been successfully built or tested in this conversation; no relay server has been provisioned. The first direct implementation is **NOT encrypted**. Do **NOT** port-forward the direct game port to the public Internet until authentication and encryption are implemented and reviewed.

Target: [`MisterTemaki/genplusgxPS5`](https://github.com/MisterTemaki/genplusgxPS5), pinned to commit `154212f72704aa99989153626c1658783f35669f`. `apply_to_upstream.py` patches the PS5 frontend without modifying the emulation core. Development title ID: `PPSA99931`; data path: `/data/genplus-netplay`; original app `PPSA99921` uses `/data/genplus`, and is not modified. The test build's updater is disabled. Its helper port is `19031` instead of upstream `9088`, avoiding collisions with the original app.

## New menu: connection type selector

Under **Settings → NETPLAY (TEST BUILD)**:

| Setting | Choices/behavior |
| --- | --- |
| Online play | Off / Host / Join |
| **Connection type** | **Relay (TLS) / Direct P2P (test) / Automatic (test)** — toggle with Cross or left/right |
| Room (edit .ini over FTP) | 8–32-character shared alphanumeric code |
| Relay (edit .ini over FTP) | TLS relay hostname (used for Relay and Automatic modes) |
| Host IP (edit .ini over FTP) | Guest's destination address (used for Direct and Automatic modes) |
| Direct TCP port | Dedicated direct gameplay port, default `43378` (Direct or Automatic) |

The UI currently changes the connection method but does **not** provide a PS5 on-screen text keyboard; edit address and room in `/data/genplus-netplay/genplus-ps5.ini` using FTP. Both connection types share the same frame-input system and game/setting hash checks. The existing relay deployment and Python service are kept intact.

### Mode A: relay (default; encrypted)

Both consoles use matching room code and relay host. They initiate outbound connections; no router port forwarding. Requires an Internet-accessible TLS relay with a valid domain certificate (see `deploy/README.md`).

```ini
# HOST PS5
netplay_mode=1
netplay_connection_type=0
netplay_host=relay.example.org
netplay_port=43377
netplay_room=MyLongRandomRoomCode27
netplay_delay=6
```

For the GUEST, use the same settings except `netplay_mode=2`.

### Mode B: direct P2P (experimental; LAN or trusted VPN only)

A PS5 in Host mode listens on TCP port `43378`. The guest connects to the host's address without using the relay. Both players must use identical ROMs, core/version, emulator settings and initial save RAM.

**Host** console's INI:

```ini
netplay_mode=1
netplay_connection_type=1
netplay_direct_port=43378
netplay_room=MyLongRandomRoomCode27
netplay_delay=6
```

**Guest** console's INI:

```ini
netplay_mode=2
netplay_connection_type=1
netplay_direct_host=192.168.1.55
netplay_direct_port=43378
netplay_room=MyLongRandomRoomCode27
netplay_delay=6
```

Set the guest's `netplay_direct_host` to the host console's **reachable LAN/VPN IPv4 address**. The direct host's own `netplay_direct_host` value is unused. Both consoles must be able to communicate over TCP `43378`.

**For future Internet P2P:** direct host would typically need a stable local IP/DHCP reservation and router port forwarding of the game's dedicated TCP port; CGNAT may prevent incoming connections. However this pre-alpha direct protocol is *not secure enough* to expose directly. Before that, implement encrypted/authenticated P2P transport (such as TLS with out-of-band certificate verification or a strong pre-shared key), abuse limits, and full PS5 testing. Never expose the PS5 jailbreak loader or helper ports. VPN is a way to test across households without exposing the game socket publicly when suitable routing exists.

### Mode C: Automatic (direct-first with TLS relay fallback)

Automatic tries the trusted-network P2P connection first, then starts the **existing
TLS relay** path if the direct TCP link cannot be established. It does not do STUN,
NAT traversal or public Internet P2P encryption. The direct-host listen attempt is
bounded to about 3.5 seconds; guest connection probe is about 2.2 seconds per address.
Both consoles still need the relay settings if they expect fallback to work.

**Host INI:**
```ini
netplay_mode=1
netplay_connection_type=2
netplay_direct_port=43378
netplay_host=relay.your-domain.com
netplay_port=43377
netplay_room=MyLongRandomRoomCode27
netplay_delay=6
```

**Guest INI:** same fields, except:
```ini
netplay_mode=2
netplay_direct_host=192.168.1.55
```

On different home networks, use the host's *reachable trusted VPN address*
for `netplay_direct_host`, not `192.168.1.55` unless both are on the same LAN.
Without a VPN or a privately reachable direct peer, Automatic will use the TLS
relay if deployed. **Do not expose the direct port through a public router port
forward.** Automatic does not make plaintext P2P secure.

## What's in the kit

- `netplay/fe_netplay.cpp/.h`: synchronized input delay and connection-type dispatch; relay stays intact, automatic fallback, direct host accepts a guest and synthesizes `PAIR` messages itself.
- `netplay/fe_netplay_tls.cpp/.h`: Mbed TLS certificate-verified **relay client** on PS5, untested on a physical console.
- `netplay/relay.py`: existing Python TLS relay, unchanged from v0.3.
- `apply_to_upstream.py`: source integration; adds the **Connection type** setting and separate persistent addresses/ports, isolates app data/helper, and disables updater actions.
- `build-netplay-workflow.yml`: GitHub Actions job attempting SDK 0.44 host and PS5 builds, with tests first.
- `tests/`: integration tests for two 60-frame direct/relay/automatic clients, rejection of wrong room/game and relay state mismatch.

## Run protocol tests locally

```sh
g++ -std=c++17 -Wall -Wextra -Werror -Inetplay netplay/fe_netplay.cpp tests/netplay_client_smoke.cpp -o tests/netplay_client_smoke
python3 -m unittest discover -s tests -p test_netplay.py -v
```

## Build via GitHub Actions

Create a dedicated `genplusgxPS5-netplay` GitHub repository. Upload this kit under `genplusgx-netplay-kit/` and copy `build-netplay-workflow.yml` to `.github/workflows/build-genplus-netplay.yml`. Run **Actions → Build Genesis Plus GX PS5 - Netplay Prototype → Run workflow**. The job downloads upstream at the pinned SHA, applies the changes, runs the protocol tests, and attempts to build the PS5 ELF. The SDK/native build remains unverified, and compilation is not proof of game functionality.

## Known limitations

1. No working PS5 ELF verified, console networking untested, and the upstream PS5 netplay integration is still experimental.
2. Direct and Auto-direct modes have no transport encryption or strong identity authentication: don't publicly expose it.
3. The direct test protocol needs manual port/address configuration; there is no STUN, UPnP, ICE or automatic NAT traversal yet.
4. ROM transfer, public matchmaking, mid-game resync, rollback, adaptive jitter, text entry, and reconnects are not implemented.
5. Supports only two-player Genesis/Mega Drive cartridge games. ROM bytes and initial save RAM must match.
6. The TLS relay uses an 8–32-character shared room code; prefer randomly generated codes, not dictionary words.

Licensing: GN1 overlay source MIT-licensed; upstream retains its own licenses and notices.
