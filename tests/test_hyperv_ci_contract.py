import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_hyperv_ci_vm.ps1"
BOUNDARY = ROOT / "docs" / "HYPERV-CI-BOUNDARY.md"
RUNBOOK = ROOT / "docs" / "FORGEJO-CI-VERIFIER-BOOTSTRAP.md"
RUNTIME_SCRIPT = ROOT / "scripts" / "set_hyperv_ci_runtime_egress.ps1"


class HyperVCiContractTests(unittest.TestCase):
    def test_script_requires_operator_supplied_boundary_inputs(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("[string[]]$DeniedFieldCidrs", script)
        self.assertIn("[string]$IsoSha256", script)
        self.assertIn("[string]$VmRoot", script)
        self.assertRegex(script, r"\[Parameter\(Mandatory\)\]\s+\[string\]\$ManagementSwitch")
        self.assertNotIn('$ManagementSwitch = "Default Switch"', script)
        self.assertNotRegex(script, r"C:\\Users\\")
        self.assertNotRegex(script, r"(?:192\.168|172\.\d+|10\.\d+)\.\d+\.\d+")

    def test_existing_vm_is_stopped_before_topology_inspection(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('if ($vm -and $vm.State -ne "Off")', script)
        self.assertIn("Stop-VM -VM $vm -TurnOff -Confirm:$false", script)
        self.assertIn("$deadline = (Get-Date).AddSeconds(30)", script)
        self.assertLess(script.index("Stop-VM -VM $vm -TurnOff"), script.index("Get-VMNetworkAdapter -VM $vm"))
        self.assertIn("could not be stopped; refusing to inspect", script)

    def test_script_applies_and_verifies_field_acls_idempotently(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Get-VMNetworkAdapterAcl", script)
        self.assertIn("Add-VMNetworkAdapterAcl", script)
        self.assertIn('-RemoteIPAddress $cidr -Direction $direction -Action Deny', script)
        self.assertIn('@("Inbound", "Outbound")', script)
        self.assertIn('throw "Missing $direction deny ACL', script)

    def test_script_requires_one_management_adapter(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("$adapters.Count -ne 1", script)
        self.assertIn("$nonManagementAdapterPresent", script)
        self.assertIn("-or $nonManagementAdapterPresent", script)

    def test_report_does_not_overstate_field_isolation(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("NonManagementAdapterPresent", script)
        self.assertIn('BoundaryState = "FieldAclPrepared"', script)
        self.assertIn("GuestNetworkProofsCompleted = $false", script)
        self.assertNotIn("    FieldAdapterPresent =", script)
        self.assertNotIn("field_adapter=absent", script)

    def test_docs_require_network_proofs_and_separate_runtime_gate(self):
        docs = BOUNDARY.read_text(encoding="utf-8") + RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("field SSH", docs)
        self.assertIn("MQTT", docs)
        self.assertIn("Forgejo TLS", docs)
        self.assertIn("normal certificate validation", docs)
        self.assertIn("openAut/main#68", docs)
        self.assertIn("Do not register a runner until #68", docs)
        self.assertNotIn("--insecure", docs)

    def test_docs_keep_secrets_and_machine_addresses_out(self):
        docs = BOUNDARY.read_text(encoding="utf-8") + RUNBOOK.read_text(encoding="utf-8")

        self.assertNotRegex(docs, r"(?:192\.168|172\.\d+|10\.\d+)\.\d+\.\d+")
        self.assertNotRegex(docs, re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"))
        self.assertNotIn("config.env", docs)

    def test_runtime_policy_is_exact_and_deny_by_default(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertRegex(script, r"\[Parameter\(Mandatory\)\]\s+\[string\]\$ForgejoIpv4")
        self.assertRegex(script, r"\[Parameter\(Mandatory\)\]\s+\[string\]\$DhcpServerIpv4")
        self.assertRegex(script, r"\[Parameter\(Mandatory\)\]\s+\[switch\]\$DedicatedForgejoEndpointConfirmed")
        self.assertRegex(script, r"\[Parameter\(Mandatory\)\]\s+\[switch\]\$DhcpSourceSpoofingMitigated")
        self.assertIn("tuple is dedicated to Forgejo", script)
        self.assertIn("Add-VMNetworkAdapterExtendedAcl", script)
        self.assertIn('-RemotePort "443" -Protocol "TCP"', script)
        self.assertIn('-Direction Outbound -RemoteIPAddress "ANY" -Weight $denyWeight', script)
        self.assertIn('-Direction Inbound -RemoteIPAddress "ANY" -Weight $denyWeight', script)
        self.assertIn("$forgejoAllowWeight = 62000", script)
        self.assertIn("$dhcpBroadcastWeight = 61900", script)
        self.assertIn("$dhcpServerOutboundWeight = 61800", script)
        self.assertIn("$dhcpServerInboundWeight = 61700", script)
        self.assertIn("$denyWeight = 61000", script)
        self.assertIn("$guardWeight = 63000", script)
        self.assertIn("$rule.Stateful -eq $true", script)
        self.assertIn("Test-AnySelector $rule.Protocol", script)
        self.assertIn("$rule.IsolationID -eq 0", script)
        self.assertIn("[uint64]4294967295", script)
        self.assertNotIn("[uint64]0xffffffff", script)
        self.assertNotRegex(script, r"(?:192\.168|172\.\d+|10\.\d+)\.\d+\.\d+")

    def test_runtime_policy_stops_vm_and_requires_field_boundary(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('if ($vm.State -ne "Off")', script)
        self.assertIn("Stop-VM -VM $vm -TurnOff -Confirm:$false", script)
        self.assertIn("Missing prerequisite $direction field deny ACL", script)
        self.assertIn("Existing unrecognized extended ACL has higher priority", script)
        self.assertIn("Unexpected higher-priority extended ACL", script)
        self.assertIn("-ReplaceManagedPolicy", script)
        self.assertIn("ForgejoIpv4 must not overlap denied field CIDR", script)
        self.assertIn("DhcpServerIpv4 must not overlap denied field CIDR", script)
        self.assertIn("DhcpServerIpv4 must be a usable unicast address", script)
        self.assertIn('$DhcpServerIpv4 -eq "255.255.255.255"', script)
        self.assertIn("DHCP source anti-spoofing or an isolated management switch", script)
        self.assertIn("Get-VMNetworkAdapter -All", script)
        self.assertIn('$_.DhcpGuard -ne "On"', script)
        self.assertIn("Management-switch VM peers lack DHCP Guard", script)
        self.assertIn("Guard denies are not effective", script)
        self.assertIn("@($DeniedFieldCidrs).Count -eq 0", script)
        self.assertIn("$outboundGuards.Count -eq 0", script)
        self.assertIn("$inboundGuards.Count -eq 0", script)

    def test_runtime_policy_allows_only_explicit_dhcp_exchange(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('Test-DhcpRule $_ "Outbound" "255.255.255.255" $dhcpBroadcastWeight', script)
        self.assertIn('Test-DhcpRule $_ "Outbound" $DhcpServerIpv4 $dhcpServerOutboundWeight', script)
        self.assertIn('Test-DhcpRule $_ "Inbound" $DhcpServerIpv4 $dhcpServerInboundWeight', script)
        self.assertIn('$rule.LocalPort -eq "68"', script)
        self.assertIn('$rule.RemotePort -eq "67"', script)
        self.assertIn('$rule.Protocol -eq "UDP"', script)
        self.assertIn("$higherPriority.Count -ne 4", script)

    def test_runtime_report_path_is_validated_before_acl_changes(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        normalize_parent = script.index('if ([string]::IsNullOrEmpty($reportParent))')
        validate_parent = script.index("Report parent does not exist", normalize_parent)
        first_acl_change = script.index("Add-VMNetworkAdapterExtendedAcl -VMNetworkAdapter")
        self.assertLess(normalize_parent, validate_parent)
        self.assertLess(validate_parent, first_acl_change)

    def test_runtime_policy_installs_guard_denies_before_final_allow(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        guard = script.index('-Direction Outbound -RemoteIPAddress "ANY" -Weight $guardWeight')
        final_deny = script.index('-Direction Outbound -RemoteIPAddress "ANY" -Weight $denyWeight')
        final_allow = script.index('-RemotePort "443" -Protocol "TCP"', final_deny)
        remove_guard = script.index("New runtime ACL set is incomplete", final_allow)
        self.assertLess(guard, final_deny)
        self.assertLess(final_deny, final_allow)
        self.assertLess(final_allow, remove_guard)

    def test_runtime_report_keeps_registration_blocked_until_guest_proofs(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('$boundaryState = "RuntimeEgressPolicyPrepared"', script)
        self.assertIn("$guestNetworkProofsCompleted = $false", script)
        self.assertIn("$runnerRegistrationAllowed = $false", script)
        self.assertIn("runner_registration=blocked", script)

    def test_poc_exception_is_exact_and_fail_closed(self):
        script = RUNTIME_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('$PocRiskAcceptanceRevision -notmatch "^[0-9a-f]{40}$"', script)
        self.assertIn('$PocRepository -cne "openaut/system-db"', script)
        self.assertIn('$PocRunnerMode -cne "Ephemeral"', script)
        for proof in (
            "PocColdStartDoraVerified",
            "PocDhcpLeaseEvidenceRecorded",
            "PocForgejoTlsVerified",
            "PocNegativeEgressVerified",
            "PocGuestRestartVerified",
        ):
            self.assertIn(f"-not ${proof}", script)
            self.assertIn(f"{proof} = [bool]${proof}", script)
        self.assertIn("-not $ReportPath", script)
        self.assertIn('$runnerRegistrationAllowed = $false', script)
        self.assertIn('$runnerRegistrationAllowed = $true', script)
        self.assertIn('BoundaryState = $boundaryState', script)
        self.assertIn('"PocRunnerRegistrationApproved"', script)

    def test_runtime_docs_require_complete_network_matrix(self):
        docs = BOUNDARY.read_text(encoding="utf-8") + RUNBOOK.read_text(encoding="utf-8")

        for expected in ("public IPv4", "IPv6", "UDP 443", "host restart", "guest restart"):
            self.assertIn(expected, docs)
        self.assertIn("normal certificate chain", docs)
        self.assertIn("Get-VMNetworkAdapterExtendedAcl", docs)
        self.assertIn("static hostname mapping", docs)
        self.assertIn("runtime DNS and NTP are intentionally not allowed", docs)
        self.assertIn("T1 unicast renewal", docs)
        self.assertIn("T2 broadcast rebinding", docs)
        self.assertIn("actual reply source", docs)
        self.assertIn("not server authentication", docs)
        self.assertIn("host-owned DHCP guard/anti-spoofing", docs)
        self.assertIn("isolated, non-production POC only", docs)
        self.assertIn("explicitly accept deferral", docs)
        self.assertIn("guest-restart persistence", docs)
        self.assertIn("RunnerRegistrationAllowed=false", docs)
        self.assertIn("RunnerRegistrationAllowed=true", docs)
        self.assertIn("does not permit field access", docs)
        self.assertIn('PocRepository "openaut/system-db"', docs)
        self.assertIn("PocRunnerMode Ephemeral", docs)
        self.assertIn("exact risk-acceptance revision", docs)
        self.assertIn("instance/organization scope", docs)


if __name__ == "__main__":
    unittest.main()
