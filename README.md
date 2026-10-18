# Genesis Plus GX PS5 — GN1 Netplay Prototype

Experimental **two-player PS5 netplay** overlay for [MisterTemaki/genplusgxPS5](https://github.com/MisterTemaki/genplusgxPS5).

**Status: proof-of-concept only; no successfully verified native PS5 ELF or console networking test.**

## Modes
- **Relay (TLS)**: encrypted client connection to a separately hosted GN1 relay.
- **Direct P2P (test)**: unencrypted TCP on a trusted LAN/VPN only.
- **Automatic (test)**: attempts direct first, then falls back to the TLS relay.

**Important:** Do not forward P2P port 43378 onto the public Internet. The direct mode has no encryption and lacks strong peer authentication. Do not open jailbreak or helper ports. No Internet relay has been deployed.

The development build uses title ID `PPSA99931`, data directory `/data/genplus-netplay`, and helper TCP port `19031` (loopback-only), rather than the upstream title ID, save folder, or helper port. Updates from upstream are disabled in the test build.

## Build

1. Open **Actions → Build Genesis Plus GX PS5 Netplay** and select **Run workflow**.
2. The workflow fetches a pinned upstream revision and PS5 Payload SDK, applies the GN1 overlay, runs network tests, then attempts host and native PS5 builds.
3. **Only if the job succeeds**, download its ELF artifact from the workflow run.
4. Review CI output before installation. A successful build still does not prove real-console functionality.

The files under `genplusgx-netplay-kit/` are the source overlay. See its README for configuration and limitations.

This repo does not contain any game ROMs, BIOSes, server credentials, hosted relay, or verified PS5 release.
