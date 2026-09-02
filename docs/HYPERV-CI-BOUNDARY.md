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
environment-specific paths, the published SHA-256 for the selected Ubuntu ISO, and every field
CIDR explicitly:

```powershell
.\scripts\setup_hyperv_ci_vm.ps1 `
  -IsoPath "<verified-ubuntu-server.iso>" `
  -IsoSha256 "<64-hex-published-sha256>" `
  -VmRoot "<hyper-v-vm-root>" `
  -ManagementSwitch "<management-switch>" `
  -DeniedFieldCidrs "<field-cidr>" `
  -ReportPath "<existing-report-directory>\openaut-ci.json"
```

The script does not recreate an existing VM. It requires exactly one adapter named `management`,
adds missing inbound and outbound deny ACLs idempotently, and fails if the effective ACL set does
not cover every supplied field CIDR.

## Verification

Inspect the host-enforced boundary:

```powershell
Get-VMNetworkAdapter -VMName openaut-ci
Get-VMNetworkAdapterAcl -VMName openaut-ci
```

From the guest, prove that representative field SSH, MQTT, database, and deployment ports time out.
Then prove that the exact Forgejo TLS hostname remains reachable with normal certificate validation.
Repeat both positive and negative checks after any Hyper-V switch, host route, VPN, or physical
adapter change.

Do not install a runner until a release authority has distributed the Forgejo CA and the TLS check
succeeds without disabling validation. Runner registration must be repository-scoped, ephemeral,
and performed with a human-generated secret that is never committed or passed to an Engineer.

The disposable PostgreSQL `case-policy` gate is tracked by openAut/main#60. Systemdatabas migrations,
roles, and grants remain tracked by openAut/main#42.
