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
        self.assertNotRegex(script, r"C:\\Users\\")
        self.assertNotRegex(script, r"(?:192\.168|172\.\d+|10\.\d+)\.\d+\.\d+")

    def test_script_applies_and_verifies_host_acls_idempotently(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Get-VMNetworkAdapterAcl", script)
        self.assertIn("Add-VMNetworkAdapterAcl", script)
        self.assertIn('-RemoteIPAddress $cidr -Direction $direction -Action Deny', script)
        self.assertIn('@("Inbound", "Outbound")', script)
        self.assertLess(script.index("Get-VMNetworkAdapterAcl"), script.index("Add-VMNetworkAdapterAcl"))
        self.assertIn('throw "Missing $direction deny ACL', script)

    def test_script_refuses_extra_or_misplaced_adapters(self):
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("$adapters.Count -ne 1", script)
        self.assertIn('$adapters[0].Name -ne "management"', script)
        self.assertIn("$adapters[0].SwitchName -ne $ManagementSwitch", script)

    def test_docs_require_negative_and_positive_network_proofs(self):
        docs = BOUNDARY.read_text(encoding="utf-8") + RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("host-enforced deny ACL", docs)
        self.assertIn("field SSH", docs)
        self.assertIn("MQTT", docs)
        self.assertIn("Forgejo TLS", docs)
        self.assertIn("normal certificate validation", docs)
        self.assertNotIn("--insecure", docs)

    def test_docs_keep_secrets_and_machine_addresses_out(self):
        docs = BOUNDARY.read_text(encoding="utf-8") + RUNBOOK.read_text(encoding="utf-8")

        self.assertNotRegex(docs, r"(?:192\.168|172\.\d+|10\.\d+)\.\d+\.\d+")
        self.assertNotRegex(docs, re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"))
        self.assertNotIn("config.env", docs)


if __name__ == "__main__":
    unittest.main()
