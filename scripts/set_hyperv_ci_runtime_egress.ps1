[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ForgejoIpv4,

    [Parameter(Mandatory)]
    [string[]]$DeniedFieldCidrs,

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
if (-not $DeniedFieldCidrs -or @($DeniedFieldCidrs | Where-Object { [string]::IsNullOrWhiteSpace($_) })) {
    throw "At least one field CIDR is required."
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
$managedWeights = @($allowWeight, $denyWeight)
$existing = @(Get-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic)
$managed = @($existing | Where-Object { $_.Weight -in $managedWeights })
$unmanagedHigherPriority = @($existing | Where-Object {
    $_.Weight -gt $denyWeight -and $_.Weight -notin $managedWeights
})
if ($unmanagedHigherPriority.Count -gt 0) {
    throw "Existing unrecognized extended ACL has higher priority than the runtime deny."
}

function Test-AllowRule($rule) {
    return $rule.Action -eq "Allow" -and
        $rule.Direction -eq "Outbound" -and
        $rule.RemoteIPAddress -eq $ForgejoIpv4 -and
        $rule.RemotePort -eq "443" -and
        $rule.Protocol -eq "TCP" -and
        $rule.Weight -eq $allowWeight -and
        $rule.Stateful -eq $true
}

function Test-DenyRule($rule, [string]$direction) {
    return $rule.Action -eq "Deny" -and
        $rule.Direction -eq $direction -and
        $rule.RemoteIPAddress -eq "ANY" -and
        $rule.Weight -eq $denyWeight
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
    foreach ($rule in $managed) {
        Remove-VMNetworkAdapterExtendedAcl -InputObject $rule
    }
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Allow `
        -Direction Outbound -RemoteIPAddress $ForgejoIpv4 -RemotePort "443" -Protocol "TCP" `
        -Weight $allowWeight -Stateful $true -IdleSessionTimeout 3600
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
        -Direction Outbound -RemoteIPAddress "ANY" -Weight $denyWeight
    Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter $managementNic -Action Deny `
        -Direction Inbound -RemoteIPAddress "ANY" -Weight $denyWeight
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
    $reportParent = Split-Path -Parent $ReportPath
    if (-not (Test-Path -LiteralPath $reportParent -PathType Container)) {
        throw "Report parent does not exist: $reportParent"
    }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}

Write-Host "OPENAUT_CI_RUNTIME_EGRESS_PREPARED vm=$VmName state=off forgejo_tcp=443 guest_tests=pending runner_registration=blocked"
