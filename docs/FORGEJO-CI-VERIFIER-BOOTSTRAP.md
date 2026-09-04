# Forgejo CI and case-verifier bootstrap

This runbook prepares the remaining POC governance gate. It does not authorize a field deployment,
apply database migrations, merge a pull request, or install anything on an edge node.

## Required separation

Run Forgejo Actions on a dedicated CI VM, not in the Platform, Advisor, Engineer, or Security trust
domain. The CI VM must have no field-test network adapter and no route or credentials to the
Platform database, MQTT broker, Engineer, IOT2050, or any deployment endpoint.

The absence of a field-test adapter is necessary but not sufficient. A Hyper-V management/NAT
switch may still route through a host interface that is attached to the field subnet. Add a
host-enforced deny ACL for every field CIDR to the CI VM's management adapter, then prove from the
guest that representative field SSH, MQTT, and deployment ports time out while the exact Forgejo
TLS endpoint remains reachable. Do not rely only on a guest firewall: untrusted jobs or a local
container engine may be able to alter guest networking. See
[`HYPERV-CI-BOUNDARY.md`](HYPERV-CI-BOUNDARY.md) for the reusable host contract.

Do not mount the Platform Docker socket into a runner and do not run untrusted pull-request jobs in
Forgejo Runner `host` mode. A Docker-socket runner can control the host, while host mode lets job
code read the runner registration secret. The initial CI VM may use a disposable local container
engine because compromise is then bounded to that dedicated VM.

## Prerequisites

1. Expose Forgejo to the management network through its planned TLS endpoint. Keep the current
   loopback HTTP binding behind the reverse proxy; do not expose port 3000 directly.
2. Create a small dedicated CI VM from an independent Ubuntu installation. Do not clone an existing
   trust-domain identity, SSH host key, or credential.
3. During provisioning, allow only the exact Forgejo TLS hostname and approved package/image
   sources needed for patching and digest-pinned image prefetching.
4. Verify the Forgejo CA chain from the CI VM before runner registration.
5. Record the CI VM's adapter inventory and host-enforced field-subnet ACLs. Repeat the negative
   field-connectivity tests after every Hyper-V switch or host-routing change.
6. Before runner registration, implement the separate host-enforced deny-by-default runtime egress
   control tracked by openAut/main#68. Verify that Forgejo remains reachable while a field target
   and an arbitrary internet target are blocked.

The reviewed runtime implementation is
[`set_hyperv_ci_runtime_egress.ps1`](../scripts/set_hyperv_ci_runtime_egress.ps1). It uses Hyper-V
extended adapter ACLs outside the guest: one dedicated Forgejo IPv4/TCP 443 tuple and narrowly scoped
DHCP client exchange with the explicit management-switch DHCP server are the only runtime allows.
All other IPv4/IPv6 egress and unsolicited ingress are denied. Confirm that the Forgejo tuple is not a
shared virtual host, forward proxy, or CONNECT service. Do not substitute basic adapter ACLs, a guest
firewall, a hostname wildcard, or a broad management subnet allow. Provisioning access must be
removed before this policy is applied. Install a static Forgejo hostname mapping and verify clock
synchronization during provisioning because runtime DNS/NTP are not allowed. Changing either exact
management destination requires a reviewed `-ReplaceManagedPolicy` execution.

The DHCP inbound exception is stateless source-/port filtering, not server authentication. Before
confirming `-DhcpSourceSpoofingMitigated`, inventory every adapter on the management switch and prove
that no untrusted peer can spoof the configured server address, either by using an isolated switch or
host-owned DHCP guard/anti-spoofing controls on every non-server peer.

The production target is to record the DHCP server identifier and lease timers and verify cold-start
DORA, T1 unicast renewal, and T2 broadcast rebinding through the effective host ACL before runner
registration. The configured `DhcpServerIpv4` must match the actual reply source; a gateway address
inferred without lease evidence is not sufficient.

For this isolated, non-production POC only, the asset owner may explicitly accept deferral of the T1,
T2, and host-restart proofs in the pull request that introduces the exception. Before using that
exception, cold-start DORA, the actual server identifier and timers, Forgejo TLS, the complete negative
egress matrix, guest-restart persistence, and the exact effective host ACL must already be recorded.
Keep the deferred proofs tracked as hardening work. This exception does not apply to a production,
live-building, occupied-space, or safety-critical runner. It does not permit field access, deployment
credentials, a broader egress allow-list, a non-ephemeral runner, or instance/organization scope. The
runtime script defaults to `RunnerRegistrationAllowed=false`. Only the asset owner may finalize the
POC exception after verifying an `APPROVED` review tied to the exact risk-acceptance revision. Run the
same script with all `Poc*` evidence switches, `-PocRepository "openaut/system-db"`,
`-PocRunnerMode Ephemeral`, the approved 40-character `-PocRiskAcceptanceRevision`, and a report path.
The script rejects a partial exception and writes `RunnerRegistrationAllowed=true` only after it also
revalidates the exact host ACL. Preserve that report as the machine-readable exception evidence.

The bootstrap stops an existing CI VM before topology inspection or ACL changes and leaves it off.
Do not start it when adapter validation, ACL verification, or runtime network proofs fail.

Distribute the CA and make `forge.openaut.local` resolvable from every intended management client
before changing Forgejo's canonical `ROOT_URL` to HTTPS. A loopback SSH tunnel is a recovery path,
not persistent service discovery; it disappears when the workstation restarts. Private-CA clients
must trust the CA normally rather than disable certificate or revocation checking as a standing
configuration.

## Reverse-proxy lessons

- Keep the Forgejo backend on loopback/internal HTTP and publish only the TLS proxy on the management
  interface. Explicitly verify that the field interface does not listen on the TLS port.
- Do not make a Docker network `internal` when host ports are published only through that network.
  Supported Docker/Compose combinations may suppress those port bindings entirely. Use a dedicated
  ingress network plus host firewall/egress controls instead.
- Recreating a Compose network can leave an already-created service without its expected DNS alias.
  Force-recreate both proxy and upstream, then verify upstream name resolution from the proxy.
- A hardened image may carry a file capability even when configured on a high container port. Test
  the exact `cap_drop`/`cap_add` runtime combination, not only `compose config`.
- Forgejo's version API may include a build suffix. Pin and validate the allowed base version plus
  its documented suffix rather than comparing only a shortened display version.

## Runner contract

- Register the runner at repository scope for `openaut/system-db`, not instance or organization
  scope.
- Use ephemeral mode so one registration executes at most one job.
- Use a unique registration secret generated by the human release authority.
- Pin Forgejo Runner v13 by digest:
  `data.forgejo.org/forgejo/runner:13@sha256:7fb853bfe73c229be6349398359c0a7bd01fadfd17c106607b2221150b799ed2`.
- Pin every job image and action by digest or immutable commit. Do not use mutable `latest`, branch,
  or major-version references.
- Give the workflow read-only repository permission. It must not receive deployment, database,
  MQTT, SSH, PAP, or long-lived user credentials.
- Require the `case-policy` status on protected `main` before merge.

The `case-policy` job must validate all case files, run the Python unit tests, apply migrations to a
fresh disposable TimescaleDB/PostgreSQL database, execute the SQL verification files, and destroy
the disposable database after the job. It must never test against the running Platform database.
This complements openAut/main#60; Systemdatabas migrations and roles remain tracked by
openAut/main#42.

## Forge verifier contract

After the Systemdatabas migrations and bootstrap implementation tracked by openAut/main#42 have
been reviewed and applied by the release authority, the bootstrap must create:

- restricted Forgejo user `openaut-forge-verifier`;
- read-only team access to `openaut/system-db` and `openaut/control-poc-lab`;
- a `read:repository` token stored only on Platform;
- login role `forge_case_verifier` inheriting only `forge_verifier_app`;
- login role `engineer_case_client` inheriting only `engineer_app`;
- node-local libpq service/password files with mode `0600`.

The Forge verifier cannot push, review, merge, change branch protection, post CI status, or access
field equipment. The CI runner and Forge verifier are deliberately separate identities.

## Order of operations

1. Review and merge the TLS/reverse-proxy and dedicated-CI-VM configuration.
2. Apply the reviewed extended ACL policy and record positive/negative runtime network proofs after a
   guest restart. Complete openAut/main#68 before production use; the isolated POC may defer T1, T2,
   and host-restart proofs only through the explicit risk-acceptance process above.
3. Require a report with `RunnerRegistrationAllowed=true`, then register one repository-scoped
   ephemeral runner and obtain a green `case-policy` result for the exact current PR head.
4. Human reviewer approves that head; `openaut-admin` merges it.
   Before merge, the Forgejo reviews API must show `APPROVED` tied to the exact head SHA;
   `REQUEST_REVIEW` records only a pending review request and is not approval evidence.
5. Release authority applies the reviewed Systemdatabas migrations and runs their verification.
6. Release authority runs the separately reviewed case-verifier bootstrap and verifies both
   least-privilege identities.
7. Engineer creates/submits the frozen case; the verifier independently re-queries Forgejo and
   records the approval evidence.
8. Only then may Engineer start the case and request explicit deployment confirmation.

Any changed PR head invalidates the previous review and CI evidence.
An expired maintenance window must be replaced with a short future window before CI and human
approval; changing it creates a new head, so previous evidence cannot be reused.
