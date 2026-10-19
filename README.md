# Native Internet P2P Development — GN2 0.6

**Branch: feature/native-internet-p2p (EXPERIMENTAL).** The stable console-tested 0.5 UI is preserved on main.

**Verified:** [GN2 build 39212289710](https://github.com/epstivalet/genplusgxPS5-netplay/actions/runs/39212289710) passed **16 automated network tests**, compiled the host application, and produced a **native PS5 installer ELF**. The new compiled code has *not yet been tested on actual PS5 hardware.*

**Added:** A dedicated GN2 rendezvous TLS+UDP service, native PS5 UDP endpoint discovery and direct peer reachability check, and a new **Settings -> NETPLAY -> Test Internet UDP route (X)** menu entry.

**Not yet implemented:** Encrypted direct UDP gameplay, NAT traversal standards/ICE, gameplay reliability, automatic relay fallback for GN2, server deployment, or confirmed two-PS5 Internet play. The probe merely determines whether short UDP messages can reach another console through NAT; it is *not* a functional multiplayer mode.

**No companion PC is needed** to run GN2 on a PS5. A separately hosted (small) DNS/TLS rendezvous server **is** required. It has not been provisioned. Existing direct-TCP GN1 remains restricted to trusted LAN/VPN and must never be publicly port-forwarded.

See [GN2 v0.6 native connectivity guide](docs/gn2-native-probe.md) for server ports (TCP 43380, UDP 43379), room setup, limitations and console test steps.

---
# Genesis Plus GX PS5 — GN1 Netplay (experimental)

Two-player Genesis / Mega Drive netplay prototype layered onto [MisterTemaki/genplusgxPS5](https://github.com/MisterTemaki/genplusgxPS5).

**Build status:** A native PS5 installer ELF successfully compiled in [GitHub Actions run #39173747705](https://github.com/epstivalet/genplusgxPS5-netplay/actions/runs/39173747705). The newer controller-keyboard revision is compiled by subsequent Actions runs. **No successful physical-console netplay test has been reported yet.** A green Actions run proves compilation, not correct multiplayer gameplay.

## Most recent build: 0.5 (PS5 address editor)

The compiled PS5 ELF from [Actions run 39197251541](https://github.com/epstivalet/genplusgxPS5-netplay/actions/runs/39197251541) has been verified to contain \`1.7-netplay0.5\`, the controller keyboard, and the menu text **"Edit direct IP / hostname (X)"** / **"Edit relay IP / hostname (X)"**. Use the artifact from **this** build, not an older 0.4 ELF whose "Host IP (edit .ini over FTP)" row intentionally does not open an editor.

To test: exit the running app, send the new installer ELF to your PS5's payload loader, and open the **Netplay** title from the dashboard again. In **Settings → NETPLAY**, verify the version in the header is \`1.7-netplay0.5\`. Select **Edit direct IP / hostname (X)**, then press Cross or D-pad Right. The on-screen character keyboard should appear. Navigate with D-pad, Cross to select, Circle to erase, and OPTIONS to save.

If the menu still says **Host IP (edit .ini over FTP)**, the older app is running or the installer did not replace \`/data/homebrew/PPSA99931/eboot.bin\`. Check \`/data/genplus-netplay/logs/installer.log\` and \`boot.log\` on that console before retrying. Do **not** delete stock emulator \`PPSA99921\` or its savedata.

**Status:** The ELF compiles in GitHub CI; keyboard functionality has not yet been confirmed in console testing.

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
