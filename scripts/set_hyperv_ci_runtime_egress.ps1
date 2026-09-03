[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ForgejoIpv4,

    [Parameter(Mandatory)]
    [string[]]$DeniedFieldCidrs,

    [Parameter(Mandatory)]
    [switch]$DedicatedForgejoEndpointConfirmed,

    [string]$VmName = "openaut-ci",
    [string]$ManagementAdapterName = "management",
    [string]$ReportPath,
    [switch]$ReplaceManagedPolicy
)

$ErrorActionPreference = "Stop"
Import-Module Hyper-V

$parsedForgejoIp = [System.Net.IPAddress]::None
if (-not [System.Net.IPAddress]::TryParse($ForgejoIpv4, [ref]$parsedForgejoIp) -or
    $parsedForgejoIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $ForgejoIpv4 -ne $parsedForgejoIp.ToString()) {
    throw "ForgejoIpv4 must be one canonical IPv4 host address, not a hostname or CIDR."
}
if (@($DeniedFieldCidrs).Count -eq 0 -or
    @($DeniedFieldCidrs | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
    throw "At least one field CIDR is required."
}
if (-not $DedicatedForgejoEndpointConfirmed) {
    throw "The operator must confirm that the allowed IPv4/TCP 443 tuple is dedicated to Forgejo."
}
$reportParent = $null
if ($ReportPath) {
    $reportParent = Split-Path -Parent $ReportPath
    if ([string]::IsNullOrEmpty($reportParent)) {
        $reportParent = "."
    }
    if (-not (Test-Path -LiteralPath $reportParent -PathType Container)) {
        throw "Report parent does not exist: $reportParent"
    }
}

function Convert-Ipv4ToUInt32([System.Net.IPAddress]$address) {
    $bytes = $address.GetAddressBytes()
    return [uint32]($bytes[0] * 16777216 + $bytes[1] * 65536 + $bytes[2] * 256 + $bytes[3])
}

$forgejoValue = Convert-Ipv4ToUInt32 $parsedForgejoIp
foreach ($cidr in $DeniedFieldCidrs) {
    if ($cidr -notmatch "^([^/]+)/([0-9]|[12][0-9]|3[0-2])$") {
        throw "DeniedFieldCidrs must contain canonical IPv4 CIDRs."
    }
    $networkIp = [System.Net.IPAddress]::None
    if (-not [System.Net.IPAddress]::TryParse($Matches[1], [ref]$networkIp) -or
        $networkIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw "DeniedFieldCidrs must contain canonical IPv4 CIDRs."
    }
    $prefixLength = [int]$Matches[2]
    $networkValue = Convert-Ipv4ToUInt32 $networkIp
    $mask = if ($prefixLength -eq 0) {
        [uint32]0
    } else {
        [uint32](([uint64]4294967295 -shl (32 - $prefixLength)) -band [uint64]4294967295)
    }
    if (($networkValue -band $mask) -ne $networkValue) {
        throw "Denied field CIDR '$cidr' is not a canonical network address."
    }
    if (($forgejoValue -band $mask) -eq $networkValue) {
        throw "ForgejoIpv4 must not overlap denied field CIDR '$cidr'."
    }
}
if (-not (Get-Command Add-VMNetworkAdapterExtendedAcl -ErrorAction SilentlyContinue)) {
    throw "This host does not provide Hyper-V extended adapter ACLs."
}

$vm = Get-VM -Name $VmName -ErrorAction Stop
if ($vm.State -ne "Off") {
    Stop-VM -VM $vm -TurnOff -Confirm:$false
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $vm = Get-VM -Name $VmName
    } while ($vm.State -ne "Off" -and (Get-Date) -lt $deadline)
    if ($vm.State -ne "Off") {
        throw "$VmName could not be stopped; refusing to change its runtime egress policy."
    }
}

$adapters = @(Get-VMNetworkAdapter -VM $vm)
if ($adapters.Count -ne 1 -or $adapters[0].Name -ne $ManagementAdapterName) {
    throw "$VmName must have exactly one adapter named '$ManagementAdapterName'."
}
$managementNic = $adapters[0]

$fieldCidrs = @($DeniedFieldCidrs | Sort-Object -Unique)
$basicAcls = @(Get-VMNetworkAdapterAcl -VMNetworkAdapter $managementNic)
foreach ($cidr in $fieldCidrs) {
    foreach ($direction in @("Inbound", "Outbound")) {
        $exists = $basicAcls | Where-Object {
            $_.Action -eq "Deny" -and
            $_.Direction -eq $direction -and
            $_.RemoteAddress -eq $cidr
        }
        if (-not $exists) {
            throw "Missing prerequisite $direction field deny ACL for '$cidr'."
        }
    }
}

$allowWeight = 62000
$denyWeight = 61000
$guardWeight = 63000
$managedWeights = @($guardWeight, $allowWeight, $denyWeight)
$existing = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic)
$managed = @($existing | Where-Object { $_.Weight -in $managedWeights })
$unmanagedHigherPriority = @($existing | Where-Object {
    $_.Weight -gt $denyWeight -and $_.Weight -notin $managedWeights
})
if ($unmanagedHigherPriority.Count -gt 0) {
    throw "Existing unrecognized extended ACL has higher priority than the runtime deny."
}

function Test-AnySelector($value) {
    return [string]::IsNullOrEmpty([string]$value) -or [string]$value -eq "ANY"
}

function Test-AllowRule($rule) {
    return $rule.Action -eq "Allow" -and
        $rule.Direction -eq "Outbound" -and
        (Test-AnySelector $rule.LocalIPAddress) -and
        $rule.RemoteIPAddress -eq $ForgejoIpv4 -and
        (Test-AnySelector $rule.LocalPort) -and
        $rule.RemotePort -eq "443" -and
        $rule.Protocol -eq "TCP" -and
        $rule.Weight -eq $allowWeight -and
        $rule.Stateful -eq $true -and
        $rule.IdleSessionTimeout -eq 3600 -and
        $rule.IsolationID -eq 0
}

function Test-DenyRule($rule, [string]$direction, [int]$weight = $denyWeight) {
    return $rule.Action -eq "Deny" -and
        $rule.Direction -eq $direction -and
        (Test-AnySelector $rule.LocalIPAddress) -and
        $rule.RemoteIPAddress -eq "ANY" -and
        (Test-AnySelector $rule.LocalPort) -and
        (Test-AnySelector $rule.RemotePort) -and
        (Test-AnySelector $rule.Protocol) -and
        $rule.Weight -eq $weight -and
        $rule.Stateful -eq $false -and
        $rule.IsolationID -eq 0
}

$policyComplete =
    @($managed | Where-Object { Test-AllowRule $_ }).Count -eq 1 -and
    @($managed | Where-Object { Test-DenyRule $_ "Outbound" }).Count -eq 1 -and
    @($managed | Where-Object { Test-DenyRule $_ "Inbound" }).Count -eq 1 -and
    $managed.Count -eq 3

if (-not $policyComplete -and $managed.Count -gt 0 -and -not $ReplaceManagedPolicy) {
    throw "Managed runtime ACL weights already contain a different or partial policy; use -ReplaceManagedPolicy after review."
}
if (-not $policyComplete) {
    $guards = @($managed | Where-Object { $_.Weight -eq $guardWeight })
    $outboundGuards = @($guards | Where-Object { Test-DenyRule $_ "Outbound" $guardWeight })
    $inboundGuards = @($guards | Where-Object { Test-DenyRule $_ "Inbound" $guardWeight })
    $malformedGuards = @($guards | Where-Object {
        -not (Test-DenyRule $_ "Outbound" $guardWeight) -and
        -not (Test-DenyRule $_ "Inbound" $guardWeight)
    })

    if ($malformedGuards.Count -gt 0 -or $outboundGuards.Count -gt 1 -or $inboundGuards.Count -gt 1) {
        foreach ($rule in $guards) {
            Remove-VMNetworkAdapterExtendedAcl -InputObject $rule
        }
        $outboundGuards = @()
        $inboundGuards = @()
    }
    if ($outboundGuards.Count -eq 0) {
        Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
            -Direction Outbound -RemoteIPAddress "ANY" -Weight $guardWeight
    }
    if ($inboundGuards.Count -eq 0) {
        Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
            -Direction Inbound -RemoteIPAddress "ANY" -Weight $guardWeight
    }

    $effectiveGuards = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic | Where-Object {
        $_.Weight -eq $guardWeight
    })
    if ($effectiveGuards.Count -ne 2 -or
        @($effectiveGuards | Where-Object { Test-DenyRule $_ "Outbound" $guardWeight }).Count -ne 1 -or
        @($effectiveGuards | Where-Object { Test-DenyRule $_ "Inbound" $guardWeight }).Count -ne 1) {
        throw "Guard denies are not effective; refusing to remove the existing runtime policy."
    }

    foreach ($rule in @($managed | Where-Object { $_.Weight -ne $guardWeight })) {
        Remove-VMNetworkAdapterExtendedAcl -InputObject $rule
    }
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
        -Direction Outbound -RemoteIPAddress "ANY" -Weight $denyWeight
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
        -Direction Inbound -RemoteIPAddress "ANY" -Weight $denyWeight
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Allow `
        -Direction Outbound -RemoteIPAddress $ForgejoIpv4 -RemotePort "443" -Protocol "TCP" `
        -Weight $allowWeight -Stateful $true -IdleSessionTimeout 3600

    $withGuards = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic)
    if (@($withGuards | Where-Object { Test-AllowRule $_ }).Count -ne 1 -or
        @($withGuards | Where-Object { Test-DenyRule $_ "Outbound" }).Count -ne 1 -or
        @($withGuards | Where-Object { Test-DenyRule $_ "Inbound" }).Count -ne 1) {
        throw "New runtime ACL set is incomplete; guard denies remain active."
    }
    foreach ($rule in @($withGuards | Where-Object { $_.Weight -eq $guardWeight })) {
        Remove-VMNetworkAdapterExtendedAcl -InputObject $rule
    }
}

$effective = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic)
$higherPriority = @($effective | Where-Object { $_.Weight -gt $denyWeight })
if ($higherPriority.Count -ne 1 -or -not (Test-AllowRule $higherPriority[0])) {
    throw "Unexpected higher-priority extended ACL could bypass or shadow the runtime policy."
}
if (@($effective | Where-Object { Test-DenyRule $_ "Outbound" }).Count -ne 1 -or
    @($effective | Where-Object { Test-DenyRule $_ "Inbound" }).Count -ne 1) {
    throw "The effective deny-by-default runtime policy is incomplete."
}

$report = [ordered]@{
    Name = $vm.Name
    State = [string]$vm.State
    AdapterName = $managementNic.Name
    SwitchName = $managementNic.SwitchName
    BoundaryState = "RuntimeEgressPolicyPrepared"
    ForgejoIpv4 = $ForgejoIpv4
    ForgejoTcpPort = 443
    DedicatedForgejoEndpointConfirmed = [bool]$DedicatedForgejoEndpointConfirmed
    DeniedFieldCidrs = $fieldCidrs
    DefaultIpv4Outbound = "Deny"
    DefaultIpv6Outbound = "Deny"
    UnsolicitedInbound = "Deny"
    GuestNetworkProofsCompleted = $false
    RunnerRegistrationAllowed = $false
    ExtendedAcls = @($effective | Sort-Object Weight -Descending | ForEach-Object {
        [ordered]@{
            Direction = [string]$_.Direction
            Action = [string]$_.Action
            RemoteIPAddress = [string]$_.RemoteIPAddress
            RemotePort = [string]$_.RemotePort
            Protocol = [string]$_.Protocol
            Weight = $_.Weight
            Stateful = $_.Stateful
        }
    })
}

if ($ReportPath) {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}

Write-Host "OPENAUT_CI_RUNTIME_EGRESS_PREPARED vm=$VmName state=off forgejo_tcp=443 guest_tests=pending runner_registration=blocked"
