"""Read-only CI publication-policy regression controls."""
from pathlib import Path
import itertools
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONDITION = "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && inputs.publish == true"


class PublicationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())

    def test_explicit_boolean_defaults_off(self):
        # PyYAML YAML 1.1 may resolve the GitHub 'on' key as True.
        events = self.workflow.get("on", self.workflow.get(True))
        value = events["workflow_dispatch"]["inputs"]["publish"]
        self.assertEqual(value["type"], "boolean")
        self.assertIs(value["default"], False)
        self.assertIs(value["required"], False)

    def test_login_and_push_reject_nonexplicit_events(self):
        steps = self.workflow["jobs"]["docker"]["steps"]
        login = [s for s in steps if s.get("uses", "").startswith("docker/login-action@")]
        push = [s for s in steps if "docker push " in s.get("run", "")]
        self.assertEqual(len(login), 1)
        self.assertEqual(len(push), 1)
        for step in login + push:
            self.assertEqual(step["if"], CONDITION)
        for event, ref, publish in itertools.product(
            ("pull_request", "push", "workflow_dispatch"),
            ("refs/heads/main", "refs/heads/feature", "refs/tags/v1"),
            (None, False, True),
        ):
            with self.subTest(event=event, ref=ref, publish=publish):
                # Evaluate the exact parsed condition's three fixed clauses, not
                # a second workflow policy that could drift independently.
                values = {"github.event_name": event, "github.ref": ref, "inputs.publish": publish}
                accepted = True
                for clause in CONDITION.split(" && "):
                    key, expected = clause.split(" == ")
                    target = True if expected == "true" else expected.strip("'")
                    accepted &= type(values[key]) is type(target) and values[key] == target
                self.assertEqual(accepted, (event, ref, publish) == ("workflow_dispatch", "refs/heads/main", True))

    def test_all_verification_precedes_scanned_image_publication(self):
        jobs = self.workflow["jobs"]
        docker = jobs["docker"]
        self.assertEqual(set(docker["needs"]), {"test", "c10-persistence", "synthetic-demo"})
        for job in ("c10-persistence", "synthetic-demo"):
            self.assertEqual(jobs[job]["needs"], "test")
            self.assertEqual(jobs[job]["permissions"], {"contents": "read"})
            provisioning = [s for s in jobs[job]["steps"] if "sudo apt-get install" in s.get("run", "")]
            self.assertEqual(len(provisioning), 1)
            self.assertIn("sudo apt-get install -y --no-install-recommends libpq5", provisioning[0]["run"])
            self.assertIn("dpkg-query -W", provisioning[0]["run"])
        steps = docker["steps"]
        build = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("docker/build-push-action@"))
        scan = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("aquasecurity/trivy-action@"))
        login = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("docker/login-action@"))
        push = next(i for i, s in enumerate(steps) if "docker push " in s.get("run", ""))
        self.assertLess(build, scan)
        self.assertLess(scan, login)
        self.assertLess(login, push)
        self.assertIs(steps[build]["with"]["push"], False)
        self.assertEqual(steps[scan]["with"]["exit-code"], "1")
        self.assertEqual(steps[scan]["with"]["severity"], "HIGH,CRITICAL")
        self.assertNotIn("continue-on-error", docker)
        for step in (steps[build], steps[scan], steps[login], steps[push]):
            self.assertNotIn("continue-on-error", step)
        self.assertNotIn("docker build", steps[push]["run"])


if __name__ == "__main__":
    unittest.main()
