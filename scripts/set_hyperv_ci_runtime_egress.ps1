[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ForgejoIpv4,

    [Parameter(Mandatory)]
    [string]$DhcpServerIpv4,

    [Parameter(Mandatory)]
    [string[]]$DeniedFieldCidrs,

    [Parameter(Mandatory)]
    [switch]$DedicatedForgejoEndpointConfirmed,

    [Parameter(Mandatory)]
    [switch]$DhcpSourceSpoofingMitigated,

    [string]$VmName = "openaut-ci",
    [string]$ManagementAdapterName = "management",
    [string]$ReportPath,
    [switch]$ReplaceManagedPolicy,
    [switch]$PocRiskAcceptanceApproved,
    [string]$PocRiskAcceptanceRevision,
    [string]$PocRepository,
    [ValidateSet("Ephemeral")]
    [string]$PocRunnerMode,
    [switch]$PocColdStartDoraVerified,
    [switch]$PocDhcpLeaseEvidenceRecorded,
    [switch]$PocForgejoTlsVerified,
    [switch]$PocNegativeEgressVerified,
    [switch]$PocGuestRestartVerified
)

$ErrorActionPreference = "Stop"
Import-Module Hyper-V

$parsedForgejoIp = [System.Net.IPAddress]::None
if (-not [System.Net.IPAddress]::TryParse($ForgejoIpv4, [ref]$parsedForgejoIp) -or
    $parsedForgejoIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $ForgejoIpv4 -ne $parsedForgejoIp.ToString()) {
    throw "ForgejoIpv4 must be one canonical IPv4 host address, not a hostname or CIDR."
}
$parsedDhcpServerIp = [System.Net.IPAddress]::None
if (-not [System.Net.IPAddress]::TryParse($DhcpServerIpv4, [ref]$parsedDhcpServerIp) -or
    $parsedDhcpServerIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $DhcpServerIpv4 -ne $parsedDhcpServerIp.ToString()) {
    throw "DhcpServerIpv4 must be one canonical IPv4 host address, not a hostname or CIDR."
}
$dhcpOctets = $parsedDhcpServerIp.GetAddressBytes()
if ($DhcpServerIpv4 -eq "0.0.0.0" -or
    $DhcpServerIpv4 -eq "255.255.255.255" -or
    $dhcpOctets[0] -eq 127 -or
    ($dhcpOctets[0] -eq 169 -and $dhcpOctets[1] -eq 254) -or
    $dhcpOctets[0] -ge 224) {
    throw "DhcpServerIpv4 must be a usable unicast address."
}
if (@($DeniedFieldCidrs).Count -eq 0 -or
    @($DeniedFieldCidrs | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
    throw "At least one field CIDR is required."
}
if (-not $DedicatedForgejoEndpointConfirmed) {
    throw "The operator must confirm that the allowed IPv4/TCP 443 tuple is dedicated to Forgejo."
}
if (-not $DhcpSourceSpoofingMitigated) {
    throw "The operator must confirm DHCP source anti-spoofing or an isolated management switch."
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
$pocParameterNames = @(
    "PocRiskAcceptanceApproved",
    "PocRiskAcceptanceRevision",
    "PocRepository",
    "PocRunnerMode",
    "PocColdStartDoraVerified",
    "PocDhcpLeaseEvidenceRecorded",
    "PocForgejoTlsVerified",
    "PocNegativeEgressVerified",
    "PocGuestRestartVerified"
)
$pocExceptionRequested = @($pocParameterNames | Where-Object {
    $PSBoundParameters.ContainsKey($_)
}).Count -gt 0
if ($pocExceptionRequested) {
    if (-not $PocRiskAcceptanceApproved -or
        $PocRiskAcceptanceRevision -notmatch "^[0-9a-f]{40}$" -or
        $PocRepository -cne "openaut/system-db" -or
        $PocRunnerMode -cne "Ephemeral" -or
        -not $PocColdStartDoraVerified -or
        -not $PocDhcpLeaseEvidenceRecorded -or
        -not $PocForgejoTlsVerified -or
        -not $PocNegativeEgressVerified -or
        -not $PocGuestRestartVerified -or
        -not $ReportPath) {
        throw "POC registration requires approved exact-revision risk acceptance, all POC proofs, the openaut/system-db repository, Ephemeral mode, and a report path."
    }
}

function Convert-Ipv4ToUInt32([System.Net.IPAddress]$address) {
    $bytes = $address.GetAddressBytes()
    return [uint32]($bytes[0] * 16777216 + $bytes[1] * 65536 + $bytes[2] * 256 + $bytes[3])
}

$forgejoValue = Convert-Ipv4ToUInt32 $parsedForgejoIp
$dhcpServerValue = Convert-Ipv4ToUInt32 $parsedDhcpServerIp
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
    if (($dhcpServerValue -band $mask) -eq $networkValue) {
        throw "DhcpServerIpv4 must not overlap denied field CIDR '$cidr'."
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
$managementPeers = @(Get-VMNetworkAdapter -All | Where-Object {
    $_.SwitchName -eq $managementNic.SwitchName -and
    -not [string]::IsNullOrEmpty($_.VMName) -and
    $_.VMName -ne $VmName
})
$unprotectedDhcpPeers = @($managementPeers | Where-Object { $_.DhcpGuard -ne "On" })
if ($unprotectedDhcpPeers.Count -gt 0) {
    $peerNames = @($unprotectedDhcpPeers | ForEach-Object { "$($_.VMName)/$($_.Name)" }) -join ","
    throw "Management-switch VM peers lack DHCP Guard: $peerNames"
}

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

$forgejoAllowWeight = 62000
$dhcpBroadcastWeight = 61900
$dhcpServerOutboundWeight = 61800
$dhcpServerInboundWeight = 61700
$denyWeight = 61000
$guardWeight = 63000
$managedWeights = @(
    $guardWeight,
    $forgejoAllowWeight,
    $dhcpBroadcastWeight,
    $dhcpServerOutboundWeight,
    $dhcpServerInboundWeight,
    $denyWeight
)
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

function Test-ForgejoAllowRule($rule) {
    return $rule.Action -eq "Allow" -and
        $rule.Direction -eq "Outbound" -and
        (Test-AnySelector $rule.LocalIPAddress) -and
        $rule.RemoteIPAddress -eq $ForgejoIpv4 -and
        (Test-AnySelector $rule.LocalPort) -and
        $rule.RemotePort -eq "443" -and
        $rule.Protocol -eq "TCP" -and
        $rule.Weight -eq $forgejoAllowWeight -and
        $rule.Stateful -eq $true -and
        $rule.IdleSessionTimeout -eq 3600 -and
        $rule.IsolationID -eq 0
}

function Test-DhcpRule($rule, [string]$direction, [string]$remoteAddress, [int]$weight) {
    return $rule.Action -eq "Allow" -and
        $rule.Direction -eq $direction -and
        (Test-AnySelector $rule.LocalIPAddress) -and
        $rule.RemoteIPAddress -eq $remoteAddress -and
        $rule.LocalPort -eq "68" -and
        $rule.RemotePort -eq "67" -and
        $rule.Protocol -eq "UDP" -and
        $rule.Weight -eq $weight -and
        $rule.Stateful -eq $false -and
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
    @($managed | Where-Object { Test-ForgejoAllowRule $_ }).Count -eq 1 -and
    @($managed | Where-Object { Test-DhcpRule $_ "Outbound" "255.255.255.255" $dhcpBroadcastWeight }).Count -eq 1 -and
    @($managed | Where-Object { Test-DhcpRule $_ "Outbound" $DhcpServerIpv4 $dhcpServerOutboundWeight }).Count -eq 1 -and
    @($managed | Where-Object { Test-DhcpRule $_ "Inbound" $DhcpServerIpv4 $dhcpServerInboundWeight }).Count -eq 1 -and
    @($managed | Where-Object { Test-DenyRule $_ "Outbound" }).Count -eq 1 -and
    @($managed | Where-Object { Test-DenyRule $_ "Inbound" }).Count -eq 1 -and
    $managed.Count -eq 6

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
        -Weight $forgejoAllowWeight -Stateful $true -IdleSessionTimeout 3600
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Allow `
        -Direction Outbound -RemoteIPAddress "255.255.255.255" -LocalPort "68" -RemotePort "67" `
        -Protocol "UDP" -Weight $dhcpBroadcastWeight
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Allow `
        -Direction Outbound -RemoteIPAddress $DhcpServerIpv4 -LocalPort "68" -RemotePort "67" `
        -Protocol "UDP" -Weight $dhcpServerOutboundWeight
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Allow `
        -Direction Inbound -RemoteIPAddress $DhcpServerIpv4 -LocalPort "68" -RemotePort "67" `
        -Protocol "UDP" -Weight $dhcpServerInboundWeight

    $withGuards = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic)
    if (@($withGuards | Where-Object { Test-ForgejoAllowRule $_ }).Count -ne 1 -or
        @($withGuards | Where-Object { Test-DhcpRule $_ "Outbound" "255.255.255.255" $dhcpBroadcastWeight }).Count -ne 1 -or
        @($withGuards | Where-Object { Test-DhcpRule $_ "Outbound" $DhcpServerIpv4 $dhcpServerOutboundWeight }).Count -ne 1 -or
        @($withGuards | Where-Object { Test-DhcpRule $_ "Inbound" $DhcpServerIpv4 $dhcpServerInboundWeight }).Count -ne 1 -or
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
if ($higherPriority.Count -ne 4 -or
    @($higherPriority | Where-Object { Test-ForgejoAllowRule $_ }).Count -ne 1 -or
    @($higherPriority | Where-Object { Test-DhcpRule $_ "Outbound" "255.255.255.255" $dhcpBroadcastWeight }).Count -ne 1 -or
    @($higherPriority | Where-Object { Test-DhcpRule $_ "Outbound" $DhcpServerIpv4 $dhcpServerOutboundWeight }).Count -ne 1 -or
    @($higherPriority | Where-Object { Test-DhcpRule $_ "Inbound" $DhcpServerIpv4 $dhcpServerInboundWeight }).Count -ne 1) {
    throw "Unexpected higher-priority extended ACL could bypass or shadow the runtime policy."
}
if (@($effective | Where-Object { Test-DenyRule $_ "Outbound" }).Count -ne 1 -or
    @($effective | Where-Object { Test-DenyRule $_ "Inbound" }).Count -ne 1) {
    throw "The effective deny-by-default runtime policy is incomplete."
}

$guestNetworkProofsCompleted = $false
$runnerRegistrationAllowed = $false
$boundaryState = "RuntimeEgressPolicyPrepared"
if ($pocExceptionRequested) {
    $guestNetworkProofsCompleted = $true
    $runnerRegistrationAllowed = $true
    $boundaryState = "PocRunnerRegistrationApproved"
}

$report = [ordered]@{
    Name = $vm.Name
    State = [string]$vm.State
    AdapterName = $managementNic.Name
    SwitchName = $managementNic.SwitchName
    BoundaryState = $boundaryState
    ForgejoIpv4 = $ForgejoIpv4
    ForgejoTcpPort = 443
    DhcpServerIpv4 = $DhcpServerIpv4
    DhcpClientPort = 68
    DhcpServerPort = 67
    DhcpSourceSpoofingMitigated = [bool]$DhcpSourceSpoofingMitigated
    DhcpGuardedVmPeers = @($managementPeers | ForEach-Object { "$($_.VMName)/$($_.Name)" })
    DedicatedForgejoEndpointConfirmed = [bool]$DedicatedForgejoEndpointConfirmed
    DeniedFieldCidrs = $fieldCidrs
    DefaultIpv4Outbound = "Deny"
    DefaultIpv6Outbound = "Deny"
    UnsolicitedInbound = "Deny"
    GuestNetworkProofsCompleted = $guestNetworkProofsCompleted
    RunnerRegistrationAllowed = $runnerRegistrationAllowed
    PocRiskAcceptanceApproved = [bool]$PocRiskAcceptanceApproved
    PocRiskAcceptanceRevision = $PocRiskAcceptanceRevision
    PocRepository = $PocRepository
    PocRunnerMode = $PocRunnerMode
    PocColdStartDoraVerified = [bool]$PocColdStartDoraVerified
    PocDhcpLeaseEvidenceRecorded = [bool]$PocDhcpLeaseEvidenceRecorded
    PocForgejoTlsVerified = [bool]$PocForgejoTlsVerified
    PocNegativeEgressVerified = [bool]$PocNegativeEgressVerified
    PocGuestRestartVerified = [bool]$PocGuestRestartVerified
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

if ($runnerRegistrationAllowed) {
    Write-Host "OPENAUT_CI_POC_REGISTRATION_APPROVED vm=$VmName state=off repository=$PocRepository revision=$PocRiskAcceptanceRevision runner_mode=ephemeral"
} else {
    Write-Host "OPENAUT_CI_RUNTIME_EGRESS_PREPARED vm=$VmName state=off forgejo_tcp=443 guest_tests=pending runner_registration=blocked"
}
