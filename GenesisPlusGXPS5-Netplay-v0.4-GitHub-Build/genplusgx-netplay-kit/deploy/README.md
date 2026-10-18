# Run the GN1 relay securely on an Ubuntu VPS (experimental)

**No cloud server has been provisioned for you.** This folder gives a deployable TLS configuration for a VPS you control. Both players connect *outbound* to the VPS, so neither home router needs port forwarding. The server must have a **publicly reachable IPv4 address**, a DNS hostname such as `relay.example.net` pointing to it, and port TCP/43377 open in the VPS/provider firewall.

**Do not expose the plaintext relay on the Internet.** `relay.py` rejects non-loopback listeners without a TLS certificate/key. The PS5 client build in this kit uses Mbed TLS and verifies the hostname against Mozilla CA roots. Self-signed certificates will not work with the console without a trusted CA. Do not disable certificate checks.

## Ubuntu 24.04 example

Provision a small Ubuntu VPS and set DNS `A: relay.example.net -> VPS_PUBLIC_IPV4` at your DNS provider. Substitute *your actual* hostname below. On the VPS:

```bash
sudo apt-get update
sudo apt-get install -y python3 certbot ufw
# Provider/cloud firewall must also allow these inbound ports.
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 43377/tcp
# Do not run 'ufw enable' until you have confirmed SSH remains allowed.
# Port 80 is needed only for HTTP-01 certificate issuance/renewal.
sudo certbot certonly --standalone -d relay.example.net
sudo useradd --system --home-dir /opt/genplus-relay --shell /usr/sbin/nologin genplus-relay
sudo install -d -m 755 /opt/genplus-relay
sudo install -d -m 750 -o root -g genplus-relay /etc/genplus-relay
sudo install -m 644 netplay/relay.py /opt/genplus-relay/relay.py
sudo install -m 640 -o root -g genplus-relay /etc/letsencrypt/live/relay.example.net/fullchain.pem /etc/genplus-relay/fullchain.pem
sudo install -m 640 -o root -g genplus-relay /etc/letsencrypt/live/relay.example.net/privkey.pem /etc/genplus-relay/privkey.pem
sudo install -m 644 deploy/genplus-relay.service /etc/systemd/system/genplus-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now genplus-relay
sudo systemctl status genplus-relay
```

Run these from the extracted kit's root so `netplay/relay.py` and `deploy/genplus-relay.service` resolve. To renew certificate copies after certbot's regular renewal run, install this hook:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/genplus-relay.sh >/dev/null <<'SH'
#!/bin/sh
set -eu
DOMAIN=relay.example.net
install -m 640 -o root -g genplus-relay "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/genplus-relay/fullchain.pem
install -m 640 -o root -g genplus-relay "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/genplus-relay/privkey.pem
systemctl restart genplus-relay
SH
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/genplus-relay.sh
sudo certbot renew --dry-run
```

Test TLS connectivity *from another device*:

```bash
openssl s_client -connect relay.example.net:43377 -servername relay.example.net -verify_return_error </dev/null
```

Then configure both consoles' `/data/genplus-netplay/genplus-ps5.ini`:

```
netplay_host=relay.example.net
netplay_port=43377
netplay_room=REPLACE_WITH_RANDOM_ROOM_CODE
netplay_delay=6
netplay_mode=1    # Host PS5; use 2 on guest PS5 (do not include comments in the .ini value)
```

Use a separate, randomly generated room code per session (`openssl rand -hex 12`, 24 alphanumeric hex chars); communicate it privately. Both consoles need the *same* Genesis ROM bytes, emulator build and relevant options. No game content is transmitted. If a game has existing battery saves, test with fresh identical data because this version cannot exchange initial states.

## Scope and operating precautions

- GN1 0.2 is an experimental two-person relay with a 64-room limit, 120-second unpaired room timeouts and bounded messages. It is **not hardened for public matchmaking or untrusted public users**, and offers no bandwidth guarantees, ping adaptation or rollback.
- The server sees the room code, game/settings fingerprints, controller inputs and state hashes, although TLS protects them in transit. Keep it under your control.
- Both homes need an Internet connection and working DNS; no inbound home-router ports need to be opened.
- If the VPS uses a restrictive outbound firewall, allow return traffic normally. NAT traversal is not needed because the VPS accepts both outbound connections.
- Do not use official PSN features or request PSN login as part of GN1.
