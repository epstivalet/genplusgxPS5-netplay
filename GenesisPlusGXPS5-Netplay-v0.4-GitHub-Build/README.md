# Genesis Plus GX PS5 — Netplay v0.4 build project

**Status:** experimental source code and GitHub Actions PS5 ELF build workflow.
**No native PS5 ELF has been produced or console-tested by this kit.**

Based on MisterTemaki/genplusgxPS5, pinned to commit
`154212f72704aa99989153626c1658783f35669f`.

## What works in host transport tests

- TLS relay mode (Python TLS server exercised locally).
- Direct P2P over TCP on a trusted LAN or VPN (plaintext test mode).
- Automatic mode: try direct (~3.5-second host listen), fall back to relay.
- Game/settings compatibility handshake, synchronized 60-frame input exchange,
  mismatch rejection, frame desynchronization detection.
- Separate app title ID `PPSA99931`, data directory `/data/genplus-netplay`,
  helper port `19031`; updates disabled in this build.

**10 integration tests passed on Linux.** PS5 networking and native build are
not yet verified. *Do not publicly port-forward P2P TCP 43378*; direct gameplay
transport lacks encryption and strong authentication. Automatic P2P has the
same limitation. Use a trusted LAN/VPN or the encrypted relay.

## Build an installer ELF using GitHub Actions

1. On GitHub, create a new repository named `genplusgxPS5-netplay`.
   Use **Add file → Upload files** to upload the contents of this project,
   preserving `.github/workflows/build-genplus-netplay.yml` and
   `genplusgx-netplay-kit/`. GitHub's web uploader may not preserve nested
   folder structure easily; using `git push` is more reliable.
2. Navigate to **Actions → Build Genesis Plus GX PS5 - Netplay Prototype**.
3. Select **Run workflow** on the `main` branch. Actions downloads the
   upstream source and PS5 Payload SDK v0.44 and attempts `make host`,
   followed by `make ps5`.
4. If the job completes successfully, download artifact
   `GenesisPlusGXPS5-Netplay-GN1-0.4-Auto-Relay-P2P-prealpha-ELF`.
   Inside is `GenesisPlusGXPS5.elf`. If the build fails, examine the Actions
   logs and correct the compiler error before attempting installation.

**Do not assume the ELF works because a build succeeds.** Test on a
jailbroken PS5 and confirm original console/game saves remain separate.

## Run host protocol tests locally

```bash
cd genplusgx-netplay-kit
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Inetplay \
    netplay/fe_netplay.cpp tests/netplay_client_smoke.cpp \
    -o tests/netplay_client_smoke
python3 -m unittest discover -s tests -p test_netplay.py -v
```

## Set up the experimental netplay build

See `genplusgx-netplay-kit/README.md` for relay, direct and automatic
settings. For now, hostnames/room codes must be edited via FTP in
`/data/genplus-netplay/genplus-ps5.ini`.

**The project does not provide any game ROMs, BIOSes, working relay address,
account credentials, or a publicly accessible network service.**
