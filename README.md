# Genesis Plus GX PS5 — GN1 Netplay (experimental)

Two-player Genesis / Mega Drive netplay prototype layered onto [MisterTemaki/genplusgxPS5](https://github.com/MisterTemaki/genplusgxPS5).

**Build status:** A native PS5 installer ELF successfully compiled in [GitHub Actions run #39173747705](https://github.com/epstivalet/genplusgxPS5-netplay/actions/runs/39173747705). The newer controller-keyboard revision is compiled by subsequent Actions runs. **No successful physical-console netplay test has been reported yet.** A green Actions run proves compilation, not correct multiplayer gameplay.

## Supported connection types

| Type | Purpose | Requirements |
| --- | --- | --- |
| **Relay (TLS)** | Play from separate households via hosted encrypted relay | Reachable GN1 relay with valid public TLS certificate and DNS hostname; both connect outbound |
| **Direct P2P (test)** | Two PS5s connect without server | Same LAN or **trusted routed VPN**, IPv4 host address; TCP 43378 reachable; no public forwarding |
| **Automatic (test)** | Try P2P then relay | Working direct setup *or* configured working TLS relay for fallback; not NAT traversal |

**Security:** Direct P2P is plaintext with no strong peer authentication. Do **not** forward TCP 43378 through an Internet-facing router and do not expose the PS5 ELF loader/helper ports. No Internet relay is automatically hosted by this repository.

The development installer has separate title ID `PPSA99931`, data root `/data/genplus-netplay`, helper loopback port `19031`, and disables upstream in-app update installs. It should not overwrite your stock Genesis Plus GX installation.

## Build the PS5 ELF

1. Open [Actions](https://github.com/epstivalet/genplusgxPS5-netplay/actions) and select **Build Genesis Plus GX PS5 - Netplay Prototype**.
2. Open the newest **successful** run (or choose **Run workflow**).
3. Download the `GenesisPlusGXPS5-Netplay-...-ELF` artifact ZIP, extract `GenesisPlusGXPS5.elf`, and send that ELF using your normal PS5 homebrew payload loader.
4. Install/open the distinct Netplay dashboard title on the PS5. **This is unverified experimental homebrew:** keep backups and do not depend on it for saves.

The workflow fetches the exact upstream commit `154212f72704aa99989153626c1658783f35669f`, applies the overlay, runs transport tests, builds the host emulator, and builds the native PS5 installer.

## First two-console test: LAN / trusted VPN

1. Install the **same Netplay build** on both jailbroken consoles. Have the **same legal ROM file** on each console. Choose a two-player Genesis cartridge game; CD/8-bit/multitap netplay is not supported.
2. On each console, navigate to **Settings → NETPLAY (TEST BUILD)**. Choose **Online play → Host** on console A and **Join** on console B.
3. Set **Connection type → Direct P2P (test)** on both, and choose the *same* 8–32 character alphanumeric **Room code**. The current source revision adds a controller keyboard: press **Cross** on Room, Relay host or Direct host; use D-pad to navigate, **Cross** to enter, **Circle** to delete, **Options** to save, and **L3+R3** to cancel.
4. On the join console set **Direct host** to the host console's reachable LAN/VPN IPv4 address, e.g. `192.168.1.55`. The host listens on TCP port `43378`. Open the same ROM on both consoles. Start host first and join within its waiting window.
5. If the session fails, note both consoles' errors and collect logs under `/data/genplus-netplay/logs/` for debugging. Do not publicly share IP addresses, room codes, or unrelated console logs.

When using **Relay (TLS)** instead, both consoles must configure the same strong room code and the DNS hostname of a *separately deployed* TLS relay. Use `deploy/` in the kit for server instructions. The default relay port is `43377`. Relay play cannot work until a relay is deployed.

**Controller note:** Opening the in-game pause menu ends the experimental multiplayer session. No resume/reconnect, rollback, lobby discovery, STUN/ICE, or automatic router traversal is implemented. Matching initial save RAM/settings may be necessary for deterministic synchronization.

## Source and tests

The complete source is currently committed under:

[`GenesisPlusGXPS5-Netplay-v0.4-GitHub-Build/genplusgx-netplay-kit/`](GenesisPlusGXPS5-Netplay-v0.4-GitHub-Build/genplusgx-netplay-kit)

The source kit README describes `apply_to_upstream.py`, the encrypted Python relay, sample INI settings, and test limitations. No ROMs, BIOSes, relay credentials, or commercial resources are included.

This is a community development experiment, not an official Sony or Genesis Plus GX release.
