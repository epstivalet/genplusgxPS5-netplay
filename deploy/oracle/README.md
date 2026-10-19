# Oracle Cloud Always Free: GN2 rendezvous deployment

**This is a controlled testing server for GN2 v0.6 UDP reachability, not a production public lobby or playable Internet netplay.** Both PS5s will use their own network connections with no computers left running in either household.

## 1. Create an Always Free Oracle VM

1. Sign in at https://cloud.oracle.com/ and go to Compute -> Instances -> Create instance.
2. Set the display name to **genplus-netplay**.
3. Select Ubuntu 24.04 LTS. Select shape **VM.Standard.A1.Flex, 1 OCPU, 6 GB RAM**, if the Console marks this configuration **Always Free-eligible**. If capacity is unavailable, use another eligible shape rather than assuming any shape is free.
4. Create/select a public VCN subnet with Internet Gateway and **Assign a public IPv4 address: Yes**.
5. Generate or upload an SSH public key. Save the private key **locally and securely**; do not post it, your Oracle password, API keys, or TLS private key in chat or GitHub.
6. Create the VM. Record its **Public IPv4 address**. All Always Free resources are subject to Oracle region, availability, and published quota rules.

## 2. Add OCI VCN ingress rules

Open the instance's VNIC -> its subnet -> Security Lists -> attached list -> Add Ingress Rules (or use a Network Security Group attached to the instance). Use **stateful** rules. Never expose a PS5 jailbreak loader/helper.

| Source CIDR | Protocol | Destination port | Reason |
| --- | --- | --- | --- |
| YOUR_HOME_PUBLIC_IP/32 | TCP | 22 | SSH administration, restrict to your own public IP |
| 0.0.0.0/0 | TCP | 80 | Let's Encrypt HTTP-01 certificate issuance and renewal |
| 0.0.0.0/0 | TCP | 43380 | GN2 TLS rendezvous/signaling |
| 0.0.0.0/0 | UDP | 43379 | GN2 UDP endpoint observation |

Leave **43377/TCP** closed for now: the legacy GN1 TLS gameplay relay has **not** been provisioned by this new bootstrap. Keep 43378/TCP and PS5 exploit/helper ports closed. You can apply rate limits or tighter source CIDRs for a controlled two-console test.

OCI ingress security rules and the Linux VM's own firewall are separate. Ensure the Ubuntu guest permits these ports too. If using UFW and it is already active, use `sudo ufw allow 80/tcp`, `sudo ufw allow 43380/tcp`, and `sudo ufw allow 43379/udp`. Do not enable/disable a guest firewall blindly or lock out SSH; some OCI images use iptables independently of UFW.

## 3. Configure a DNS hostname

Create an A record with a DNS provider for your VM's public IPv4, for example `gn2.example.net` -> `<VM_PUBLIC_IPV4>`. This is an example, not a preconfigured service.

A real public hostname is required because the PS5 verifies the TLS certificate. The Ubuntu setup uses Let's Encrypt standalone HTTP-01 validation. Verify your DNS record resolves to the VM before running the installer.

## 4. Install GN2 over SSH

On Windows PowerShell, connect using your downloaded private key:

    ssh -i C:\path\to\oracle-private-key.key ubuntu@VM_PUBLIC_IPV4

On your Oracle VM (Ubuntu), run:

    sudo apt-get update && sudo apt-get install -y git
    git clone --depth 1 --single-branch --branch feature/native-internet-p2p https://github.com/epstivalet/genplusgxPS5-netplay.git
    cd genplusgxPS5-netplay
    sudo bash deploy/oracle/setup-ubuntu.sh gn2.example.net your-email@example.com

Replace `gn2.example.net` and the email with your actual DNS hostname and Let's Encrypt contact email. Do **not** paste passwords, private keys, or Oracle account tokens into chat.

The installer verifies that it is running on Ubuntu, checks out the GN2 branch, obtains a publicly trusted TLS certificate, creates an unprivileged `gn2` service account, starts a hardened systemd service at boot, and configures a certificate-renewal hook that refreshes private key copies and restarts the service.

## 5. Verify

    sudo systemctl status gn2-rendezvous.service --no-pager
    sudo journalctl -u gn2-rendezvous.service -n 80 --no-pager
    sudo ss -lntup | grep -E ':(43379|43380)'
    sudo systemctl is-enabled gn2-rendezvous.service

Expected: `active (running)` and bound TCP 43380 / UDP 43379. If certificate issuance fails, verify public DNS, port 80, the VM firewall, and OCI ingress. If service cannot read TLS files, inspect `/etc/gn2/tls` permissions and service logs.

## 6. When both consoles are ready

Install the same GN2 0.6 probe ELF on both jailbroken PS5s, enter the same **16-32 character random room code** and your real DNS hostname into the Relay host field, set Host and Join roles, and choose **Test Internet UDP route (X)** within 75 seconds. This only proves peer UDP reachability; gameplay transport is still under development.

## Security and limits

- Keep SSH limited to your IP, use SSH keys, apply Ubuntu security updates, and check logs.
- The GN2 server is an early research prototype with basic room validation but **not production rate-limited, audited, or ready for untrusted public matchmaking**. Restrict access when possible.
- Do not install a commercial DNS name or assume a certificate was issued until it actually validates.
- Oracle 'Always Free' eligibility and regional resources should be verified in your own account before accepting any paid resource.

Official references:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm
