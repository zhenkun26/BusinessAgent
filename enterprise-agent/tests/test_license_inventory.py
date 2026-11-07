"""Inventory integrity is separate from a license or data-rights approval."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "license_inventory", ROOT / "enterprise-agent/scripts/verify_license_inventory.py"
)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def save(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def record(root: Path, name: str) -> dict:
    return {"path": name, "sha256": inventory.digest(root / name)}


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "source"
    save(root, "LICENSE", "Test-only license placeholder, not a license grant.")
    save(root, "enterprise-agent/pyproject.toml",
         '[project]\ndependencies=["demo>=1"]\n[build-system]\nrequires=["builder"]\n')
    save(root, ".pre-commit-config.yaml", "repos: []\n")
    save(root, "enterprise-agent/deploy/MODEL_PROFILE.md", "| Model | `example` |\n")
    save(root, "enterprise-agent/eval/sample_docs/policy.md", "Synthetic test fixture.")
    save(root, "enterprise-agent/app/static/vendor/demo/LICENSE", "Test notice.")
    source = {"version": "1.0", "source": "https://pypi.org/pypi/demo/1.0/json",
              "metadata_sha256": "a" * 64}
    save(root, inventory.BUILD, json.dumps({"packages": {"demo": source}}))
    browser = [{"name": "demo", "version": "1.0", "license": "UNKNOWN",
                "files": [{"file": "demo/LICENSE", "sha256": inventory.digest(
                    root / "enterprise-agent/app/static/vendor/demo/LICENSE")}]}]
    save(root, inventory.VENDOR, json.dumps({"packages": browser}))
    data = {
        "schema": 1, "distribution_acceptance": "BLOCKED",
        "root_license": record(root, "LICENSE"),
        "build_manifest": record(root, inventory.BUILD),
        "vendor_manifest": record(root, inventory.VENDOR),
        "python_packages": {"demo": {**source, "role": "direct",
            "status": "PUBLISHER_METADATA_ONLY", "wheel_license_review": "PENDING",
            "license_expression": None, "legacy_license": None, "license_classifiers": []}},
        "browser_packages": browser,
        "source_files": {name: {"category": category, "status": inventory.PENDING,
            "sha256": inventory.digest(root / name)}
            for name, category in inventory.covered_files(root).items()},
        "declarations": {name: {"items": items, "sha256": inventory.digest(root / name),
            "status": "CLOSURE_AND_LICENSE_REVIEW_PENDING"}
            for name, items in inventory.declarations(root).items()},
    }
    save(root, inventory.INVENTORY, json.dumps(data))
    return root, data


def test_repository_inventory() -> None:
    result = inventory.verify(ROOT)
    assert result["production_packages"] == 98
    assert result["browser_packages"] == 3
    assert result["distribution_acceptance"] == "BLOCKED"
    assert result["c10"] == "OPEN"


def test_unknown_license_is_not_invented(repository: tuple[Path, dict]) -> None:
    root, data = repository
    assert data["python_packages"]["demo"]["license_expression"] is None
    assert inventory.verify(root)["integrity"] == "PASS"
    assert inventory.verify(root)["distribution_acceptance"] == "BLOCKED"


@pytest.mark.parametrize("field,value", [
    ("version", "2.0"), ("source", "https://example.invalid/other"),
    ("metadata_sha256", "b" * 64), ("role", "transitive-or-build"),
    ("status", "APPROVED"), ("wheel_license_review", "PASS"),
    ("license_classifiers", "MIT"), ("license_expression", 3), ("legacy_license", []),
])
def test_reject_package_evidence_drift(repository: tuple[Path, dict], field, value) -> None:
    root, data = repository
    data["python_packages"]["demo"][field] = value
    save(root, inventory.INVENTORY, json.dumps(data))
    with pytest.raises(ValueError):
        inventory.verify(root)


@pytest.mark.parametrize("name", [
    "LICENSE", "enterprise-agent/app/static/vendor/demo/LICENSE",
    "enterprise-agent/eval/sample_docs/policy.md", "enterprise-agent/pyproject.toml",
    "enterprise-agent/deploy/MODEL_PROFILE.md",
])
def test_reject_changed_file(repository: tuple[Path, dict], name: str) -> None:
    root, _ = repository
    with (root / name).open("a") as handle:
        handle.write("\n# changed")
    with pytest.raises(ValueError):
        inventory.verify(root)


@pytest.mark.parametrize("name,content", [
    ("interview/fonts/new.woff2", "font"),
    ("enterprise-agent/eval/sample_docs/new.md", "new sample"),
    ("enterprise-agent/tests/new_test.py", "# fixture"),
    ("enterprise-agent/deploy/requirements-extra.txt", "other==1"),
    ("enterprise-agent/deploy/docker-compose.extra.yml", "image: other:1"),
    ("docs/assets/new.png", "image"),
    ("enterprise-agent/app/static/vendor/new.js", "// new dependency"),
    ("enterprise-agent/app/static/extra.html", "<p>New content</p>"),
])
def test_reject_unregistered_inputs(repository: tuple[Path, dict], name, content) -> None:
    root, _ = repository
    save(root, name, content)
    with pytest.raises(ValueError):
        inventory.verify(root)


@pytest.mark.parametrize("change", [
    "clearance", "missing-package", "extra-package", "browser-version", "source-approval",
    "missing-source", "declaration-approval", "missing-declaration", "root-license-path",
])
def test_reject_unsubstantiated_inventory(repository: tuple[Path, dict], change: str) -> None:
    root, data = repository
    if change == "clearance":
        data["distribution_acceptance"] = "PASS"
    elif change == "missing-package":
        data["python_packages"].pop("demo")
    elif change == "extra-package":
        data["python_packages"]["extra"] = deepcopy(data["python_packages"]["demo"])
    elif change == "browser-version":
        data["browser_packages"][0]["version"] = "2"
    elif change == "source-approval":
        next(iter(data["source_files"].values()))["status"] = "APPROVED"
    elif change == "missing-source":
        data["source_files"].clear()
    elif change == "declaration-approval":
        next(iter(data["declarations"].values()))["status"] = "CLEARED"
    elif change == "missing-declaration":
        data["declarations"].pop("enterprise-agent/pyproject.toml")
    else:
        data["root_license"]["path"] = "../LICENSE"
    save(root, inventory.INVENTORY, json.dumps(data))
    with pytest.raises(ValueError):
        inventory.verify(root)


def test_generated_results_are_outside_inventory(repository: tuple[Path, dict]) -> None:
    root, _ = repository
    save(root, "enterprise-agent/eval/results/private-output.json", "not inspected")
    assert inventory.verify(root)["integrity"] == "PASS"


def test_private_environment_is_not_read(repository: tuple[Path, dict], monkeypatch) -> None:
    root, _ = repository
    original = Path.read_bytes
    original_walk = inventory.os.walk

    def walk_with_private_name(*args, **kwargs):
        for current, directories, files in original_walk(*args, **kwargs):
            yield current, directories, files + [".env.local"]

    def guarded_read(path: Path) -> bytes:
        assert not path.name.startswith(".env")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    monkeypatch.setattr(inventory.os, "walk", walk_with_private_name)
    assert inventory.verify(root)["integrity"] == "PASS"


def test_symlink_escape_is_rejected(repository: tuple[Path, dict]) -> None:
    root, _ = repository
    (root / "enterprise-agent/eval/external").symlink_to(root.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        inventory.verify(root)
