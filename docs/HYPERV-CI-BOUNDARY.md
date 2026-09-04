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

## Runtime egress policy

Issue openAut/main#68 is implemented by a separate Hyper-V extended adapter ACL policy. Extended
ACLs are required because the basic field ACL cannot restrict protocol and port. The runtime policy
allows one exact IPv4/TCP 443 tuple with stateful return traffic plus DHCP client traffic (UDP 68 to
UDP 67) to the operator-supplied management-switch DHCP server and the IPv4 broadcast address. It
then denies all other outbound IPv4 and IPv6 traffic and all unsolicited inbound traffic except a
source-/port-filtered DHCP packet from the configured server address. This stateless ACL does not
authenticate the server and its source address can be spoofed by another peer on the same virtual
switch. Require either an isolated management switch with no untrusted peers or host-owned DHCP
guard/anti-spoofing controls on every peer that is not the real DHCP service. DHCP is required because
the Hyper-V management switch assigns a new lease after a cold VM start; omitting it leaves the guest
without an address. This is an L3/L4 boundary, not
service-identity enforcement: a compromised guest can address the Forgejo tuple directly. The
endpoint must therefore be dedicated to Forgejo, not a shared TLS virtual host, forward proxy, or
CONNECT service. A hostname is not accepted as the network allow-list: the legitimate client must
resolve the expected Forgejo TLS hostname to the operator-supplied address and validate it through the
normal certificate chain.

Apply only after the Forgejo address is stable, its CA is installed in the guest, and a release-
authority-owned static hostname mapping resolves the TLS name to that exact address. Synchronize and
verify the guest clock during provisioning; runtime DNS and NTP are intentionally not allowed by this
minimal policy.

```powershell
.\scripts\set_hyperv_ci_runtime_egress.ps1 `
  -VmName openaut-ci `
  -ForgejoIpv4 "<exact-forgejo-management-ip>" `
  -DhcpServerIpv4 "<management-switch-dhcp-ip>" `
  -DeniedFieldCidrs "<field-cidr>" `
  -DedicatedForgejoEndpointConfirmed `
  -DhcpSourceSpoofingMitigated `
  -ReportPath "<existing-report-directory>\openaut-ci-runtime.json"
```

The script stops the VM before inspection, requires the basic inbound/outbound field denies from the
bootstrap, rejects a Forgejo or DHCP-server address inside a denied field CIDR, and reserves high ACL
weights for the managed runtime policy. It refuses a partial or changed policy unless
`-ReplaceManagedPolicy` is
explicitly supplied after review. A replacement first installs still-higher temporary inbound and
outbound guard denies; they remain if any later operation fails and a later reviewed replacement can
repair a partial guard pair. Guards are removed only after the final deny/allow set is complete. The
script also refuses any unrecognized rule with higher priority than the default deny. It leaves the
VM off and reports `RunnerRegistrationAllowed=false`; applying rules is not connectivity proof.

For a shared management switch, the script also inventories every other VM adapter and requires
Hyper-V DHCP Guard to be `On`; the host vNIC that provides the real switch service is not treated as a
guest peer. The operator confirmation remains required because this deterministic check cannot prove
the absence of every non-VM spoofing path in every switch implementation.

Hyper-V requires each extended ACL to have a unique weight within a direction. The Forgejo allow,
DHCP broadcast request, DHCP server request, DHCP server reply, default denies, and temporary guards
therefore use separate reserved weights; sharing the Forgejo weight across DHCP rules is invalid.

Start the VM only for the review-evidenced test matrix. Verify DHCP assigns an address and normal
Forgejo TLS succeeds while a field target, arbitrary public IPv4 target, IPv6 target, Forgejo TCP port
other than 443, and UDP 443 all fail. Inspect `Get-VMNetworkAdapterExtendedAcl -VMName openaut-ci` to
prove the allows and denies are host-owned. Repeat after guest restart. The production target also
requires repetition after a host restart.
Record the exact policy report, guest results, lease/server address, management-switch peer inventory,
anti-spoofing evidence, and the restart evidence required for the selected assurance level. If any
negative test succeeds, stop the VM and keep runner registration blocked.

The production target requires DHCP proof beyond initial address acquisition. Record the lease's
server identifier, T1, T2, and lifetime; confirm the packet source equals `DhcpServerIpv4`; force or
observe a T1 unicast renewal; and observe a T2 broadcast rebinding while the runtime ACL remains
active. A cold-start DORA success alone is insufficient for production assurance.

The isolated, non-production POC may defer T1, T2, and host-restart proofs only through the explicit
human risk-acceptance process in `FORGEJO-CI-VERIFIER-BOOTSTRAP.md`. Cold-start DORA, the actual DHCP
server and timers, the complete network matrix, guest-restart persistence, and exact host ACL remain
mandatory before registration. The deferred proofs remain open hardening work and the exception must
not be carried into a production or live-building environment.

Before recording the positive result, inspect the allowed address/port from the management side and
prove it terminates only the Forgejo TLS service, offers no forward-proxy or CONNECT behavior, and is
not shared with another virtual host. TLS hostname validation proves the legitimate runner reached
Forgejo; it does not narrow what a compromised guest can send to the allowed L3/L4 tuple.

The disposable PostgreSQL `case-policy` gate is tracked by openAut/main#60. Systemdatabas migrations,
roles, and grants remain tracked by openAut/main#42.
