#!/usr/bin/env bash
# Controlled GN2 deployment on Oracle Ubuntu 24.04.
# Run: sudo bash setup-ubuntu.sh gn2.your-domain.tld your-email@example.com
set -euo pipefail
if [[ "$EUID" -ne 0 || "$#" -ne 2 ]]; then
  echo "Usage: sudo bash $0 <DNS_HOSTNAME> <LETSENCRYPT_EMAIL>" >&2
  exit 2
fi
DOMAIN="$1"
EMAIL="$2"
if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ || "$DOMAIN" != *.* || "$DOMAIN" == *..* ]]; then
  echo "Invalid DNS hostname." >&2; exit 2
fi
if [[ ! "$EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
  echo "Invalid certificate notification email." >&2; exit 2
fi
. /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
  echo "This setup script only supports Ubuntu." >&2; exit 2
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates certbot git python3
if ! id gn2 >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/gn2 --create-home --shell /usr/sbin/nologin gn2
fi
if [[ ! -d /opt/gn2-src/.git ]]; then
  if [[ -e /opt/gn2-src ]]; then
    echo "/opt/gn2-src already exists and is not a Git checkout; refusing to overwrite." >&2; exit 1
  fi
  git clone --single-branch --depth 1 --branch feature/native-internet-p2p \
    https://github.com/epstivalet/genplusgxPS5-netplay.git /opt/gn2-src
else
  git -C /opt/gn2-src fetch --depth 1 origin feature/native-internet-p2p
  git -C /opt/gn2-src checkout -B feature/native-internet-p2p FETCH_HEAD
fi
APP="/opt/gn2-src/GenesisPlusGXPS5-Netplay-v0.4-GitHub-Build/genplusgx-netplay-kit/netplay/rendezvous.py"
test -s "$APP"
python3 -m py_compile "$APP"
install -d -o root -g gn2 -m 0750 /etc/gn2
install -d -o root -g gn2 -m 0750 /etc/gn2/tls

echo "Checking Let's Encrypt certificate for $DOMAIN."
echo "DNS must point to this VM, and TCP 80 must be open on the Oracle VCN and guest."
certbot certonly --standalone --non-interactive --agree-tos --no-eff-email \
  --preferred-challenges http --http-01-port 80 \
  -m "$EMAIL" -d "$DOMAIN" --keep-until-expiring
CERTPATH="/etc/letsencrypt/live/$DOMAIN"
test -s "$CERTPATH/fullchain.pem"
test -s "$CERTPATH/privkey.pem"
install -o root -g gn2 -m 0640 "$CERTPATH/fullchain.pem" /etc/gn2/tls/fullchain.pem
install -o root -g gn2 -m 0640 "$CERTPATH/privkey.pem" /etc/gn2/tls/privkey.pem

cat >/etc/systemd/system/gn2-rendezvous.service <<UNIT
[Unit]
Description=GN2 experimental encrypted signaling and UDP reachability observation
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=gn2
Group=gn2
WorkingDirectory=/opt/gn2-src
ExecStart=/usr/bin/python3 $APP --host 0.0.0.0 --tcp-port 43380 --udp-port 43379 --tls-cert /etc/gn2/tls/fullchain.pem --tls-key /etc/gn2/tls/privkey.pem
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
CapabilityBoundingSet=
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT

cat >/usr/local/sbin/gn2-refresh-cert <<HOOK
#!/usr/bin/env bash
set -euo pipefail
test "\$EUID" -eq 0
CERTPATH="/etc/letsencrypt/live/$DOMAIN"
install -o root -g gn2 -m 0640 "\$CERTPATH/fullchain.pem" /etc/gn2/tls/fullchain.pem
install -o root -g gn2 -m 0640 "\$CERTPATH/privkey.pem" /etc/gn2/tls/privkey.pem
systemctl try-restart gn2-rendezvous.service
HOOK
chmod 0750 /usr/local/sbin/gn2-refresh-cert

cat >/etc/letsencrypt/renewal-hooks/deploy/gn2-reload <<HOOK
#!/usr/bin/env bash
set -euo pipefail
if [[ "\${RENEWED_LINEAGE:-}" == "/etc/letsencrypt/live/$DOMAIN" ]]; then
  /usr/local/sbin/gn2-refresh-cert
fi
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/gn2-reload
systemctl daemon-reload
systemctl enable --now gn2-rendezvous.service
echo "GN2 service installed. Verify: sudo systemctl status gn2-rendezvous.service"
echo "Logs: sudo journalctl -u gn2-rendezvous -n 60 --no-pager"
echo "The script does NOT change OCI VCN or guest firewall ingress."
echo "Required: TCP 80 (ACME), TCP 43380 (TLS signaling), UDP 43379 (UDP observation)."
