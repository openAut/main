# Hyper-V CI network boundary

The Forgejo Actions runner is supporting infrastructure, not an openAut trust domain. Pull-request
code is untrusted, so its VM must remain separate from Advisor, Engineer, Security, Platform data
services, and every field network.

## Threat model

Giving the CI VM only a management adapter is necessary but not sufficient. Hyper-V management/NAT
switches can route through host interfaces, including an interface attached to a field subnet. A
guest firewall is also insufficient as the only boundary because a compromised job or local
container engine may be able to change guest networking.

The Windows host must therefore enforce deny ACLs on the CI VM's virtual management adapter for
every field CIDR. The guest receives no field credentials, MQTT identity, database login, deployment
key, Platform Docker socket, or PAP access.

## Bootstrap

Run the script from a PowerShell session whose user belongs to `Hyper-V Administrators`. Supply
environment-specific paths, the published SHA-256 for the selected Ubuntu ISO, every field CIDR,
and the management switch explicitly:

```powershell
.\scripts\setup_hyperv_ci_vm.ps1 `
  -IsoPath "<verified-ubuntu-server.iso>" `
  -IsoSha256 "<64-hex-published-sha256>" `
  -VmRoot "<hyper-v-vm-root>" `
  -ManagementSwitch "<management-switch>" `
  -DeniedFieldCidrs "<field-cidr>" `
  -ReportPath "<existing-report-directory>\openaut-ci.json"
```

The script does not recreate an existing VM. It turns off the disposable CI VM before inspecting
its topology and leaves it off on success or failure. This may terminate an active CI job, so run
boundary changes between jobs. It requires exactly one adapter named `management`, adds missing
inbound and outbound field-deny ACLs idempotently, and fails if the effective ACL set does not cover
every supplied field CIDR.

`FieldAclPrepared` means only that the host adapter topology and field ACL entries passed. It is not
proof of complete isolation: the report deliberately leaves `GuestNetworkProofsCompleted=false`.

## Verification

Inspect the host-enforced boundary:

```powershell
Get-VMNetworkAdapter -VMName openaut-ci
Get-VMNetworkAdapterAcl -VMName openaut-ci
```

Start the VM only for verification. From the guest, prove that representative field SSH, MQTT,
database, and deployment ports time out. Then prove that the exact Forgejo TLS hostname remains
reachable with normal certificate validation. Stop the VM again if any expected allow or deny fails.
Repeat both checks after any Hyper-V switch, host route, VPN, or physical adapter change.

Field ACLs do not make general runtime egress deny-by-default. That separate host-enforced control
is tracked by openAut/main#68. Do not register a runner until #68 is review-evidenced and its runtime
network proofs pass. Runner registration must remain repository-scoped and ephemeral, using a
human-generated secret that is never committed or passed to an Engineer.

The disposable PostgreSQL `case-policy` gate is tracked by openAut/main#60. Systemdatabas migrations,
roles, and grants remain tracked by openAut/main#42.
