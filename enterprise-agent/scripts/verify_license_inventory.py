"""Read-only F2-09 inventory integrity check; never grants redistribution approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any

INVENTORY = "enterprise-agent/deploy/license-inventory.json"
BUILD = "enterprise-agent/deploy/build-inputs.json"
VENDOR = "enterprise-agent/app/static/vendor/manifest.json"
TREES = {
    "interview": "presentation",
    "docs/10-product-plan/research": "research",
    "enterprise-agent/eval": "evaluation",
    "enterprise-agent/tests": "test-fixtures",
    "enterprise-agent/reference_service": "reference-fixtures",
    "enterprise-agent/reference_idp": "reference-fixtures",
    ".codex/skills": "generated-tooling",
    ".kimi-code/skills": "generated-tooling",
}
IGNORED_DIRS = {"results", "__pycache__", ".pytest_cache"}
MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf", ".woff", ".woff2",
         ".ttf", ".otf", ".mp4", ".mp3", ".csv", ".jsonl", ".xlsx", ".docx"}
PENDING = "PENDING_SOURCE_REVIEW"


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def checked_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe inventory path")
    result = root / path
    if any((root / Path(*path.parts[:i])).is_symlink()
           for i in range(1, len(path.parts) + 1)):
        raise ValueError("symlink in inventory scope")
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("inventory path escaped root")
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_files(root: Path, relative: str) -> list[str]:
    base = checked_path(root, relative)
    if not base.exists():
        return []
    found = []
    def fail(error: OSError) -> None:
        raise error
    for current, directories, files in os.walk(base, followlinks=False, onerror=fail):
        directories[:] = sorted(d for d in directories if d not in IGNORED_DIRS)
        for name in directories + files:
            path = Path(current) / name
            if path.is_symlink():
                raise ValueError("symlink in inventory scope")
        found.extend(str((Path(current) / name).relative_to(root)) for name in sorted(files)
                     if not name.endswith((".pyc", ".DS_Store", ".log"))
                     and not name.startswith(".env"))
    return found


def covered_files(root: Path) -> dict[str, str]:
    """Explicit source scope; generated results and private runtime data are never read."""
    found = {name: category for tree, category in TREES.items()
             for name in walk_files(root, tree)}
    for name in walk_files(root, "docs"):
        if Path(name).suffix.lower() in MEDIA:
            found.setdefault(name, "media")
    for name in walk_files(root, "enterprise-agent/app"):
        if "/static/vendor/" in name:
            continue
        if "/static/" in name:
            found[name] = "application-ui"
        elif Path(name).suffix.lower() in MEDIA or name.endswith((".json", ".csv")):
            found[name] = "embedded-data"
        elif "/tools/" in name and name.endswith(".py"):
            found[name] = "embedded-tool-fixtures"
    for name in walk_files(root, "enterprise-agent/deploy"):
        if name.endswith(".sql"):
            found[name] = "seed-and-schema"
    return dict(sorted(found.items()))


def declarations(root: Path) -> dict[str, list[str]]:
    """Keep exact declarations, including unresolved ranges, image aliases and actions."""
    project = tomllib.loads(checked_path(root, "enterprise-agent/pyproject.toml").read_text())
    found = {"enterprise-agent/pyproject.toml": project["project"]["dependencies"]
             + [f"{group}: {item}" for group, items in
                project["project"].get("optional-dependencies", {}).items() for item in items]
             + ["build: " + item for item in project["build-system"]["requires"]]}
    candidates = walk_files(root, "enterprise-agent/deploy")
    candidates += walk_files(root, ".github/workflows")
    candidates += [str(p.relative_to(root)) for p in (root / "enterprise-agent").iterdir()
                   if p.is_file()]
    candidates += [".pre-commit-config.yaml"]
    for name in sorted(set(candidates)):
        p = Path(name)
        if (p.name.startswith(("requirements", "Dockerfile", "docker-compose"))
                or p.suffix in {".yml", ".yaml"}):
            lines = checked_path(root, name).read_text().splitlines()
            if p.name.startswith("requirements"):
                selected = [s.strip() for s in lines if s.strip() and not s.lstrip().startswith("#")]
            else:
                selected = [s.strip() for s in lines if re.search(
                    r"(?:image:|FROM |uses:|pip install|uv pip|repo:|rev:)", s)]
            found[name] = selected
    model_path = "enterprise-agent/deploy/MODEL_PROFILE.md"
    found[model_path] = [line for line in checked_path(root, model_path).read_text().splitlines()
                         if line.startswith("|") and "`" in line]
    return dict(sorted(found.items()))


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    inventory = json.loads(checked_path(root, INVENTORY).read_text())
    build = json.loads(checked_path(root, BUILD).read_text())
    vendor = json.loads(checked_path(root, VENDOR).read_text())
    if inventory["schema"] != 1 or inventory["distribution_acceptance"] != "BLOCKED":
        raise ValueError("inventory cannot grant distribution approval")
    for name in ("root_license", "build_manifest", "vendor_manifest"):
        entry = inventory[name]
        expected = {"root_license": "LICENSE", "build_manifest": BUILD,
                    "vendor_manifest": VENDOR}[name]
        if entry["path"] != expected or digest(checked_path(root, expected)) != entry["sha256"]:
            raise ValueError("evidence input drift")
    project = tomllib.loads(checked_path(root, "enterprise-agent/pyproject.toml").read_text())
    direct = {canonical_name(re.match(r"[\w.-]+", req)[0])
              for req in project["project"]["dependencies"]}
    packages = inventory["python_packages"]
    if set(packages) != set(build["packages"]):
        raise ValueError("production package coverage drift")
    for name, entry in packages.items():
        source = build["packages"][name]
        for field in ("version", "source", "metadata_sha256"):
            if entry[field] != source[field]:
                raise ValueError("package evidence drift")
        expected_role = "direct" if canonical_name(name) in direct else "transitive-or-build"
        if entry["role"] != expected_role or entry["status"] != "PUBLISHER_METADATA_ONLY":
            raise ValueError("unsupported package rights claim")
        if not isinstance(entry["license_classifiers"], list):
            raise ValueError("invalid license classifiers")
        for field in ("license_expression", "legacy_license"):
            if entry[field] is not None and not isinstance(entry[field], str):
                raise ValueError("invalid publisher license declaration")
        if entry["wheel_license_review"] != "PENDING":
            raise ValueError("wheel notices require separate evidence")
    if inventory["browser_packages"] != vendor["packages"]:
        raise ValueError("browser package inventory drift")
    expected_vendor = {VENDOR}
    for package in vendor["packages"]:
        for entry in package["files"]:
            path = "enterprise-agent/app/static/vendor/" + entry["file"]
            expected_vendor.add(path)
            if digest(checked_path(root, path)) != entry["sha256"]:
                raise ValueError("browser notice or asset drift")
    if set(walk_files(root, "enterprise-agent/app/static/vendor")) != expected_vendor:
        raise ValueError("unregistered browser distribution file")
    records = inventory["source_files"]
    scope = covered_files(root)
    if set(records) != set(scope):
        raise ValueError("source inventory coverage drift")
    for name, category in scope.items():
        entry = records[name]
        if (entry["category"] != category or entry["status"] != PENDING
                or entry["sha256"] != digest(checked_path(root, name))):
            raise ValueError("source evidence drift or unsupported rights claim")
    actual = declarations(root)
    if set(inventory["declarations"]) != set(actual):
        raise ValueError("declaration coverage drift")
    for name, items in actual.items():
        entry = inventory["declarations"][name]
        if (entry["items"] != items or entry["sha256"] != digest(checked_path(root, name))
                or entry["status"] != "CLOSURE_AND_LICENSE_REVIEW_PENDING"):
            raise ValueError("dependency declaration drift")
    return {"integrity": "PASS", "distribution_acceptance": "BLOCKED",
            "production_packages": len(packages), "browser_packages": len(vendor["packages"]),
            "pending_source_files": len(records), "declaration_files": len(actual),
            "runtime": "BLOCKED", "full_rag": "BLOCKED", "c10": "OPEN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        print(json.dumps({"integrity": "FAIL", "distribution_acceptance": "BLOCKED"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
