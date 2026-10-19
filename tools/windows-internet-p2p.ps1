# Temporary Internet P2P bridge for Genesis Plus GX PS5 Netplay 0.5.
# Requires an elevated Windows PowerShell session and Tailscale on BOTH PCs.
# Run with -Role Host or Join. Remove with -Action Remove.
# Forwards TCP 43378; traffic between Tailscale peers is WireGuard encrypted.
# Do not expose the PS5 via public router port forwarding.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet("Host","Join")][string]$Role,
    [ValidateSet("Install","Remove")][string]$Action = "Install",
    [Parameter(Mandatory=$true)][string]$ListenIP,
    [string]$TargetIP,
    [string]$AllowedRemoteIP,
    [ValidateRange(1024,65535)][int]$Port = 43378
)
$ErrorActionPreference = "Stop"
function RequireIPv4([string]$value,[string]$paramName) {
    $addr = $null
    if (-not [System.Net.IPAddress]::TryParse($value,[ref]$addr) -or
        $addr.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "$paramName must be an IPv4 address; got '$value'."
    }
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run Windows PowerShell as Administrator."
}
RequireIPv4 $ListenIP "ListenIP"
$ruleName = "GN1 Netplay $Role TCP $Port $ListenIP"
if ($Action -eq "Install") {
    if ([string]::IsNullOrWhiteSpace($TargetIP) -or [string]::IsNullOrWhiteSpace($AllowedRemoteIP)) {
        throw "Install requires -TargetIP and -AllowedRemoteIP."
    }
    RequireIPv4 $TargetIP "TargetIP"
    RequireIPv4 $AllowedRemoteIP "AllowedRemoteIP"
    if ($ListenIP -eq $TargetIP) { throw "ListenIP and TargetIP cannot be identical." }
    # Windows portproxy supports TCP, matching the current GN1 transport.
    # Avoid clobbering another application's listener.
    $existing = netsh interface portproxy show v4tov4
    if ($LASTEXITCODE -ne 0) { throw "Cannot query Windows portproxy." }
    foreach($entry in $existing) {
        if ($entry -match '^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+(\d+)\s+') {
            if ($matches[1] -eq $ListenIP -and [int]$matches[2] -eq $Port) {
                throw ("A portproxy rule already listens on " + $ListenIP + ":" + $Port)
            }
        }
    }
    & netsh interface portproxy add v4tov4 "listenaddress=$ListenIP" "listenport=$Port" "connectaddress=$TargetIP" "connectport=$Port" protocol=tcp
    if ($LASTEXITCODE -ne 0) { throw "Could not install portproxy listener." }
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -LocalAddress $ListenIP -RemoteAddress $AllowedRemoteIP -Profile Any | Out-Null
    } catch {
        & netsh interface portproxy delete v4tov4 "listenaddress=$ListenIP" "listenport=$Port" protocol=tcp | Out-Null
        throw
    }
    Write-Host ("Installed " + $Role + " bridge: " + $ListenIP + ":" + $Port + " -> " + $TargetIP + ":" + $Port)
    Write-Host ("Firewall remote peer restricted to: " + $AllowedRemoteIP)
    Write-Host "Keep this PC and Tailscale online while playing."
} else {
    & netsh interface portproxy delete v4tov4 "listenaddress=$ListenIP" "listenport=$Port" protocol=tcp
    if ($LASTEXITCODE -ne 0) { Write-Warning "No matching portproxy rule, or could not delete it." }
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Host ("Removed GN1 " + $Role + " bridge for " + $ListenIP + ":" + $Port)
}
