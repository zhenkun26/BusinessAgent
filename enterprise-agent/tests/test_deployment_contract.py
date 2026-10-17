"""Offline deployment contract regressions; no files, services or cleanup are created."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "deployment_contract", ROOT / "enterprise-agent/scripts/check_deployment_contract.py"
)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def model() -> dict:
    api = {
        "image": "registry.example.invalid/businessagent@sha256:" + "a" * 64,
        "volumes": [{"type": "volume", "target": "/data/hf_cache", "source": "hf_cache"}],
    }
    worker = copy.deepcopy(api)
    worker["healthcheck"] = {"disable": True}
    return {"services": {"api": api, "worker": worker}}


class DeploymentContractTests(unittest.TestCase):
    def test_repository_compose_uses_one_required_image_without_builds(self) -> None:
        # PyYAML is already pinned in requirements-prod.txt; do not install it implicitly.
        try:
            import yaml
        except ModuleNotFoundError:
            self.skipTest("Declared PyYAML dependency unavailable; parse YAML separately")
        config = yaml.safe_load((ROOT / "enterprise-agent/docker-compose.prod.yml").read_text())
        api, worker = (config["services"][name] for name in ("api", "worker"))
        self.assertTrue(api["image"].startswith("${BUSINESSAGENT_IMAGE:?"))
        self.assertEqual(api["image"], worker["image"])
        for service in (api, worker):
            self.assertNotIn("build", service)
            self.assertFalse(service.get("volumes"))  # C02 remote profile has no model mounts.
            self.assertFalse(service.get("ports"))
        self.assertIs(worker["healthcheck"]["disable"], True)

    def test_accepts_shared_digest_without_code_overlay(self) -> None:
        self.assertEqual(contract.check_contract(model())["overall_status"], "PASS")

    def test_rejects_tag_or_different_worker_image(self) -> None:
        for target, image in [("api", "repo:latest"), ("worker", "repo@sha256:" + "b" * 64)]:
            config = model()
            config["services"][target]["image"] = image
            self.assertEqual(contract.check_contract(config)["overall_status"], "FAIL")

    def test_rejects_build_source_overlay_and_exposed_api(self) -> None:
        changes = [
            ("build", {"context": "."}),
            ("volumes", [{"type": "bind", "source": "./app", "target": "/app/app"}]),
            ("volumes", [{"type": "volume", "source": "replacement", "target": "/app"}]),
            ("ports", [{"published": "8000", "target": 8000}]),
            ("network_mode", "host"), ("entrypoint", ["other-code"]),
            ("configs", [{"target": "/app/app/main.py", "source": "replacement"}]),
        ]
        for service in ("api", "worker"):
            for key, value in changes:
                with self.subTest(service=service, key=key):
                    config = model()
                    config["services"][service][key] = value
                    self.assertEqual(contract.check_contract(config)["overall_status"], "FAIL")

    def test_rejects_worker_api_probe(self) -> None:
        config = model()
        config["services"]["worker"]["healthcheck"] = {"disable": False}
        self.assertEqual(contract.check_contract(config)["overall_status"], "FAIL")

    def test_cli_never_echoes_environment_or_invalid_input(self) -> None:
        config = model()
        config["services"]["api"]["environment"] = {"SECRET": "SYNTHETIC_PRIVATE_VALUE"}
        for content, expected in [(json.dumps(config), 0), ("SYNTHETIC_PRIVATE_VALUE", 1)]:
            with patch.object(contract.sys, "stdin", io.StringIO(content)), \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(contract.main(), expected)
            self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", output.getvalue())

    def test_nginx_declares_all_product_paths_and_streaming_policy(self) -> None:
        nginx = (ROOT / "enterprise-agent/deploy/nginx.conf").read_text()
        for path in ("/health", "/ready", "/docs", "/redoc", "/openapi.json",
                     "/docs/oauth2-redirect"):
            block = re.search(r"location = " + re.escape(path) + r"\s*\{([^{}]*)\}", nginx)
            self.assertIsNotNone(block, path)
            self.assertIn("proxy_pass http://api_backend;", block[1])
        for path in ("/", "/ui"):
            block = re.search(r"location = " + re.escape(path) + r"\s*\{([^{}]*)\}", nginx)
            self.assertIsNotNone(block, path)
            self.assertIn("return 302 /ui/;", block[1])
        api = re.search(r"location /api/\s*\{([^{}]*)\}", nginx)[1]
        for directive in ("proxy_buffering off;", "proxy_cache off;", "gzip off;"):
            self.assertIn(directive, api)
        self.assertNotIn('Connection "upgrade"', nginx)
        self.assertNotIn("proxy_set_header Upgrade", nginx)
        self.assertIn('proxy_set_header Connection "";', nginx)
        self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", nginx)
        self.assertRegex(nginx, r"location /ui/\s*\{\s*proxy_pass http://api_backend;")

    def test_metrics_remain_private_and_health_has_no_prefix_match(self) -> None:
        nginx = (ROOT / "enterprise-agent/deploy/nginx.conf").read_text()
        for route in ("= /metrics", "/metrics/", "/"):
            block = re.search(r"location " + re.escape(route) + r"\s*\{([^{}]*)\}", nginx)
            self.assertIsNotNone(block, route)
            self.assertIn("return 404;", block[1])
        self.assertNotIn("location /health {", nginx)
        prometheus = (ROOT / "enterprise-agent/deploy/prometheus.yml").read_text()
        self.assertIn('targets: ["api:8000"]', prometheus)

    def test_ci_builds_packaged_application_with_production_dockerfile(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        image = (ROOT / "enterprise-agent/Dockerfile.prod").read_text()
        self.assertIn("file: enterprise-agent/Dockerfile.prod", ci)
        self.assertIn("COPY app ./app", image)
        self.assertIn("EXPOSE 8000", image)


if __name__ == "__main__":
    unittest.main(verbosity=2)
