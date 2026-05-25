[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$Name = "Codex Bridge LAN",
    [ValidateSet("Private", "Domain", "Any")]
    [string]$Profile = "Private"
)

$ErrorActionPreference = "Stop"

$Existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
if ($Existing) {
    Set-NetFirewallRule -DisplayName $Name -Enabled True -Profile $Profile
    Set-NetFirewallPortFilter -AssociatedNetFirewallRule $Existing -Protocol TCP -LocalPort $Port
} else {
    New-NetFirewallRule `
        -DisplayName $Name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -Profile $Profile | Out-Null
}

Write-Host "Firewall rule enabled for TCP port $Port on profile $Profile."

