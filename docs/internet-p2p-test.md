# Internet P2P test: two PS5s in different homes (GN1 v0.5)

**You do NOT need two PS5s on one LAN.** This procedure tests the existing GN1 Direct P2P TCP transport across the Internet.

## Requirements

- One GN1 Netplay v0.5 PS5 and one Windows PC per household; both PCs must be on their respective PS5s' local networks.
- Tailscale installed on both Windows PCs, joined to a trusted tailnet, with permissions to connect on TCP port 43378.
- The two PCs' Tailscale IPv4 addresses, local LAN IPv4 addresses, and each PS5's local LAN IPv4 address.
- Same legal Genesis ROM, matching initial saves/settings and matching 8-32-character alphanumeric room code.
- PowerShell run as Administrator on each PC to install temporary TCP forwarding rules.

**No PS5 VPN client, public router port forwarding, rented VPS, or same-LAN PS5 testing is necessary.** Between PS5 and its local Windows PC, GN1 is still plaintext, so use a trusted local network. Between the Tailscale peers it travels in an encrypted WireGuard tunnel.

## Example network layout

    HOST HOUSE                                 JOIN HOUSE
    Host PS5 192.168.1.55                     Join PS5 192.168.2.45
          ^                                          |
          | TCP 43378                                | TCP 43378
          |                                          v
    Host PC Tailscale 100.101.20.1             Join PC LAN 192.168.2.20
    forwards to Host PS5                     forwards to Host PC Tailscale IP
          ^                                          |
          +------------ encrypted Tailscale ---------+

These addresses are examples, not working service endpoints. Replace all addresses with actual values.

## Configure the PCs

1. Set up Tailscale on both PCs and verify they can reach each other. In a terminal, use: tailscale ip -4
2. Also record each PC's LAN IP (ipconfig) and its nearby PS5's LAN IP.
3. Download/review the helper: tools/windows-internet-p2p.ps1. Ensure Windows IP Helper service is running.
4. Open PowerShell as Administrator on the HOST-HOUSE PC and execute:

    ./tools/windows-internet-p2p.ps1 -Role Host -ListenIP 100.101.20.1 -TargetIP 192.168.1.55 -AllowedRemoteIP 100.101.20.2

5. Open PowerShell as Administrator on the JOIN-HOUSE PC and execute:

    ./tools/windows-internet-p2p.ps1 -Role Join -ListenIP 192.168.2.20 -TargetIP 100.101.20.1 -AllowedRemoteIP 192.168.2.45

These install TCP-only Windows portproxy listeners plus narrowly scoped inbound firewall rules. They do not open home router ports. Keep both PCs powered on and Tailscale connected for the test.

## Configure GN1 on each PS5

HOST PS5:
- Online play: Host
- Connection type: Direct P2P (test)
- Room code: a shared 8-32 character alphanumeric code, e.g. GenesisNet2026
- Direct TCP port: 43378. The Host PS5's own Direct host field is ignored.

JOIN PS5:
- Online play: Join
- Connection type: Direct P2P (test)
- Room code: exactly the same code as the Host PS5
- Direct TCP port: 43378
- Direct host: the JOIN-HOUSE WINDOWS PC's LAN address, e.g. 192.168.2.20. Do not enter the host PS5's private IP, the host's Tailscale IP, or its public IP here.

Host loads the matching ROM first. Join loads the same ROM within the ~120-second Host waiting window. Loading the game initiates connection; there is no separate lobby or Join button in 0.5.

## Troubleshoot

- On both PCs, run tailscale ping <other-PC-Tailscale-IP>. Note whether the tunnel is direct or relayed. Tailscale may use DERP if NAT prevents a direct path; this is still Internet multiplayer, but not pure direct P2P.
- On the HOST PC, while the Host PS5 is waiting, check: Test-NetConnection -ComputerName <Host-PS5-LAN-IP> -Port 43378
- On the JOIN PC, while host is waiting, check: Test-NetConnection -ComputerName <Host-PC-Tailscale-IP> -Port 43378
- If these fail, inspect Windows Firewall, portproxy rules (netsh interface portproxy show all), Tailscale sharing/ACLs, and Windows IP Helper service. Do not disable Windows Firewall globally.
- If network tests succeed but GN1 rejects the session, compare room code, the exact ROM bytes, emulator settings, and initial SRAM.
- Record the precise console error and whether host/join got as far as the connected notification.

## Clean up on both PCs

    ./tools/windows-internet-p2p.ps1 -Role Host -Action Remove -ListenIP 100.101.20.1

    ./tools/windows-internet-p2p.ps1 -Role Join -Action Remove -ListenIP 192.168.2.20

### What this does not implement

This is a secure-overlay Internet test for the current plaintext PS5 TCP protocol, **not native PS5 NAT hole punching**. For a true native direct Internet release without companion PCs, implement authenticated encryption, a lightweight rendezvous/signaling service, modern UDP NAT traversal, and relay fallback. Current GN1 Automatic does not support STUN/ICE/UPnP/hole punching. **Do not port-forward plaintext TCP 43378 or any jailbreak loader/helper port to the Internet.**

References:
- https://tailscale.com/docs/reference/connection-types
- https://learn.microsoft.com/windows-server/networking/technologies/netsh/netsh-interface-portproxy
- https://tailscale.com/docs/features/subnet-routers
