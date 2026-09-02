import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_hyperv_ci_vm.ps1"
BOUNDARY = ROOT / "docs" / "HYPERV-CI-BOUNDARY.md"
RUNBOOK = ROOT / "docs" / "FORGEJO-CI-VERIFIER-BOOTSTRAP.md"


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


if __name__ == "__main__":
    unittest.main()
