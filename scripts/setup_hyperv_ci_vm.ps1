[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$IsoPath,

    [Parameter(Mandatory)]
    [string]$IsoSha256,

    [Parameter(Mandatory)]
    [string[]]$DeniedFieldCidrs,

    [Parameter(Mandatory)]
    [string]$VmRoot,

    [Parameter(Mandatory)]
    [string]$ManagementSwitch,

    [string]$VmName = "openaut-ci",
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"
Import-Module Hyper-V

$vm = Get-VM -Name $VmName -ErrorAction SilentlyContinue
if ($vm -and $vm.State -ne "Off") {
    Stop-VM -VM $vm -TurnOff -Confirm:$false
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $vm = Get-VM -Name $VmName
    } while ($vm.State -ne "Off" -and (Get-Date) -lt $deadline)
    if ($vm.State -ne "Off") {
        throw "$VmName could not be stopped; refusing to inspect or change its network boundary."
    }
}

if (-not (Test-Path -LiteralPath $IsoPath -PathType Leaf)) {
    throw "ISO path does not exist: $IsoPath"
}
if ($IsoSha256 -notmatch "^[A-Fa-f0-9]{64}$") {
    throw "IsoSha256 must contain exactly 64 hexadecimal characters."
}
if (-not (Test-Path -LiteralPath $VmRoot -PathType Container)) {
    throw "VM root does not exist: $VmRoot"
}
if (-not $DeniedFieldCidrs -or @($DeniedFieldCidrs | Where-Object { [string]::IsNullOrWhiteSpace($_) })) {
    throw "At least one field CIDR is required."
}
if (-not (Get-VMSwitch -Name $ManagementSwitch -ErrorAction SilentlyContinue)) {
    throw "Hyper-V management switch '$ManagementSwitch' was not found."
}

$actualIsoHash = (Get-FileHash -LiteralPath $IsoPath -Algorithm SHA256).Hash
if ($actualIsoHash -ne $IsoSha256.ToUpperInvariant()) {
    throw "ISO checksum does not match the operator-supplied SHA-256."
}

$created = $false
if (-not $vm) {
    $vmPath = Join-Path $VmRoot $VmName
    $diskDirectory = Join-Path $vmPath "Virtual Hard Disks"
    $diskPath = Join-Path $diskDirectory "$VmName.vhdx"
    New-Item -ItemType Directory -Path $diskDirectory -Force | Out-Null

    $vm = New-VM -Name $VmName -Generation 2 -Path $vmPath `
        -MemoryStartupBytes 2GB -NewVHDPath $diskPath -NewVHDSizeBytes 30GB `
        -SwitchName $ManagementSwitch
    Set-VMProcessor -VM $vm -Count 2
    Set-VMMemory -VM $vm -DynamicMemoryEnabled $true -StartupBytes 2GB `
        -MinimumBytes 1GB -MaximumBytes 4GB
    Set-VM -VM $vm -AutomaticStartAction Nothing -AutomaticStopAction ShutDown `
        -CheckpointType Production
    Set-VMFirmware -VM $vm -EnableSecureBoot On `
        -SecureBootTemplate MicrosoftUEFICertificateAuthority

    $managementNic = Get-VMNetworkAdapter -VM $vm
    Rename-VMNetworkAdapter -VMNetworkAdapter $managementNic -NewName "management"
    $managementNic = Get-VMNetworkAdapter -VM $vm
    Set-VMNetworkAdapter -VMNetworkAdapter $managementNic -DhcpGuard On -RouterGuard On `
        -MacAddressSpoofing Off

    $dvd = Add-VMDvdDrive -VM $vm -Path $IsoPath -Passthru
    Set-VMFirmware -VM $vm -FirstBootDevice $dvd
    $created = $true
}

$adapters = @(Get-VMNetworkAdapter -VM $vm)
$nonManagementAdapterPresent = [bool]($adapters | Where-Object {
    $_.Name -ne "management" -or $_.SwitchName -ne $ManagementSwitch
})
if ($adapters.Count -ne 1 -or $nonManagementAdapterPresent) {
    throw "$VmName must have exactly one adapter named 'management' on '$ManagementSwitch'."
}
$managementNic = $adapters[0]

$fieldCidrs = @($DeniedFieldCidrs | Sort-Object -Unique)
foreach ($cidr in $fieldCidrs) {
    foreach ($direction in @("Inbound", "Outbound")) {
        $exists = @(Get-VMNetworkAdapterAcl -VMNetworkAdapter $managementNic) | Where-Object {
            $_.Action -eq "Deny" -and
            $_.Direction -eq $direction -and
            $_.RemoteAddress -eq $cidr
        }
        if (-not $exists) {
            Add-VMNetworkAdapterAcl -VMNetworkAdapter $managementNic `
                -RemoteIPAddress $cidr -Direction $direction -Action Deny
        }
    }
}

$effectiveAcls = @(Get-VMNetworkAdapterAcl -VMNetworkAdapter $managementNic)
foreach ($cidr in $fieldCidrs) {
    foreach ($direction in @("Inbound", "Outbound")) {
        $exists = $effectiveAcls | Where-Object {
            $_.Action -eq "Deny" -and
            $_.Direction -eq $direction -and
            $_.RemoteAddress -eq $cidr
        }
        if (-not $exists) {
            throw "Missing $direction deny ACL for field CIDR '$cidr'."
        }
    }
}

$report = [ordered]@{
    Name = $vm.Name
    Created = $created
    State = [string]$vm.State
    Generation = $vm.Generation
    AdapterCount = $adapters.Count
    AdapterName = $managementNic.Name
    SwitchName = $managementNic.SwitchName
    NonManagementAdapterPresent = $nonManagementAdapterPresent
    BoundaryState = "FieldAclPrepared"
    GuestNetworkProofsCompleted = $false
    DeniedFieldCidrs = $fieldCidrs
    Acls = @($effectiveAcls | ForEach-Object {
        [ordered]@{
            Direction = [string]$_.Direction
            Action = [string]$_.Action
            RemoteAddress = [string]$_.RemoteAddress
        }
    })
}

if ($ReportPath) {
    $reportParent = Split-Path -Parent $ReportPath
    if (-not (Test-Path -LiteralPath $reportParent -PathType Container)) {
        throw "Report parent does not exist: $reportParent"
    }
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}

$cidrSummary = $fieldCidrs -join ","
Write-Host "OPENAUT_CI_VM_FIELD_ACL_PREPARED vm=$VmName state=off guest_tests=pending denied_field_cidrs=$cidrSummary"
