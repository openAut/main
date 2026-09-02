[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$IsoPath,

    [Parameter(Mandatory)]
    [ValidatePattern("^[A-Fa-f0-9]{64}$")]
    [string]$IsoSha256,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string[]]$DeniedFieldCidrs,

    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string]$VmRoot,

    [string]$VmName = "openaut-ci",
    [string]$ManagementSwitch = "Default Switch",
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"
Import-Module Hyper-V

$actualIsoHash = (Get-FileHash -LiteralPath $IsoPath -Algorithm SHA256).Hash
if ($actualIsoHash -ne $IsoSha256.ToUpperInvariant()) {
    throw "ISO checksum does not match the operator-supplied SHA-256."
}
if (-not (Get-VMSwitch -Name $ManagementSwitch -ErrorAction SilentlyContinue)) {
    throw "Hyper-V management switch '$ManagementSwitch' was not found."
}

$vm = Get-VM -Name $VmName -ErrorAction SilentlyContinue
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
if ($adapters.Count -ne 1 -or $adapters[0].Name -ne "management" -or
    $adapters[0].SwitchName -ne $ManagementSwitch) {
    throw "$VmName must have exactly one adapter named 'management' on '$ManagementSwitch'."
}
$managementNic = $adapters[0]

$fieldCidrs = @($DeniedFieldCidrs | Sort-Object -Unique)
foreach ($cidr in $fieldCidrs) {
    foreach ($direction in @("Inbound", "Outbound")) {
        $acls = @(Get-VMNetworkAdapterAcl -VMNetworkAdapter $managementNic)
        $exists = $acls | Where-Object {
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
    FieldAdapterPresent = [bool]($adapters | Where-Object SwitchName -ne $ManagementSwitch)
    DeniedFieldCidrs = $fieldCidrs
    DenyAcls = @($effectiveAcls | Where-Object Action -eq "Deny" | ForEach-Object {
        [ordered]@{
            Direction = [string]$_.Direction
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
Write-Host "OPENAUT_CI_VM_PREPARED vm=$VmName field_adapter=absent denied_field_cidrs=$cidrSummary"
