param([switch]$Apply, [switch]$Check, [ValidateSet('Tailnet','LAN')][string]$Network='Tailnet', [string]$Address)
$ErrorActionPreference = 'Stop'
try {
    $root = Split-Path -Parent $PSScriptRoot
    if (-not $Address) {
        $key = if ($Network -eq 'LAN') { 'BILLTRACK_LAN_IP' } else { 'BILLTRACK_TAILSCALE_IP' }
        $line = Get-Content -LiteralPath (Join-Path $root '.env') | Where-Object { $_ -match ('^'+$key+'=') } | Select-Object -First 1
        if ($line) { $Address = ($line -split '=',2)[1].Trim() }
    }
    $bytes = ([Net.IPAddress]::Parse($Address)).GetAddressBytes()
    if ($bytes.Length -ne 4) { throw 'An IPv4 address is required.' }
    $assigned = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $Address -ErrorAction Stop | Select-Object -First 1
    $adapter = Get-NetAdapter -InterfaceIndex $assigned.InterfaceIndex
    if ($Network -eq 'Tailnet') {
        if ($bytes[0] -ne 100 -or $bytes[1] -lt 64 -or $bytes[1] -gt 127 -or ($adapter.InterfaceDescription -notmatch 'Tailscale' -and $adapter.Name -notmatch 'Tailscale')) { throw 'Configured tailnet address must belong to Tailscale.' }
        $remote='100.64.0.0/10'; $remoteMask='100.64.0.0/255.192.0.0'; $ruleName='BillTrack-Tailnet-HTTP'
    } else {
        $private = $bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
        if (-not $private -or -not $adapter.HardwareInterface -or $adapter.Name -match 'Tailscale') { throw 'Configured LAN address must belong to a private physical office adapter.' }
        $mask=@(); $networkBytes=@()
        for ($index=0; $index -lt 4; $index++) {
            $bits=[Math]::Min(8,[Math]::Max(0,$assigned.PrefixLength-$index*8))
            $octet=[int](256-[Math]::Pow(2,8-$bits)); $mask += $octet; $networkBytes += ($bytes[$index] -band $octet)
        }
        $remote=($networkBytes -join '.')+'/'+$assigned.PrefixLength
        $remoteMask=($networkBytes -join '.')+'/'+($mask -join '.')
        $ruleName='BillTrack-LAN-HTTP'
    }
    if (Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object { -not $_.Enabled -or $_.DefaultInboundAction -ne 'Block' }) { throw 'All firewall profiles must be enabled with effective inbound Block. No profiles were changed.' }
    $existing=Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        $port=$existing | Get-NetFirewallPortFilter; $addresses=$existing | Get-NetFirewallAddressFilter; $interfaces=$existing | Get-NetFirewallInterfaceFilter
        if ($existing.Enabled -ne 'True' -or $existing.Direction -ne 'Inbound' -or $existing.Action -ne 'Allow' -or $port.Protocol -notin @('TCP','6') -or $port.LocalPort -ne '8000' -or $addresses.LocalAddress -ne $Address -or $addresses.RemoteAddress -notin @($remote,$remoteMask) -or $interfaces.InterfaceAlias -ne $adapter.Name) { throw ('Existing '+$Network+' rule differs from the expected restricted rule.') }
    }
    $conflicts=@()
    $rules=Get-NetFirewallApplicationFilter -PolicyStore ActiveStore | Where-Object { (-not $_.Package -or $_.Package -eq 'Any') -and ($_.Program -eq 'Any' -or $_.Program -match 'python(w)?\.exe$') } | Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and [string]::IsNullOrEmpty($_.PackageFamilyName) }
    foreach ($rule in $rules) {
        if ($rule.Name -in @('BillTrack-Tailnet-HTTP','BillTrack-LAN-HTTP')) { continue }
        $port=$rule | Get-NetFirewallPortFilter
        if ($port.Protocol -notin @('TCP','6','Any','256')) { continue }
        $match=@($port.LocalPort) | Where-Object { $_ -eq 'Any' -or $_ -eq '8000' -or ($_ -match '^(\d+)-(\d+)$' -and [int]$matches[1] -le 8000 -and [int]$matches[2] -ge 8000) }
        if (-not $match -or ($rule | Get-NetFirewallServiceFilter).Service -ne 'Any') { continue }
        $local=($rule | Get-NetFirewallAddressFilter).LocalAddress
        if (@($local).Count -eq 1 -and ($local -eq '127.0.0.1' -or $local -eq '::1' -or $local -like '100.*' -or $local -like 'fd7a:115c:a1e0:*')) { continue }
        $conflicts += $rule.DisplayName
    }
    if ($conflicts.Count) { throw ('Broader rules can expose port 8000; review: '+($conflicts -join '; ')) }
    if (-not $existing) {
        if (-not $Apply) { throw ('Restricted '+$Network+' rule is not installed.') }
        New-NetFirewallRule -Name $ruleName -DisplayName ('BillTrack - private '+$Network+' HTTP') -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalPort 8000 -LocalAddress $Address -RemoteAddress $remote -InterfaceAlias $adapter.Name | Out-Null
    }
    if (-not $Check) { Write-Output ($Network+' firewall verified: '+$Address+':8000 from '+$remote) }
    exit 0
} catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 1
}
