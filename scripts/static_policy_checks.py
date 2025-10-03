#!/usr/bin/env python
"""Static validations for release, offline, and distribution policies."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    hint: str | None = None


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def ensure(condition: bool, name: str, message: str, hint: str | None = None) -> CheckResult:
    return CheckResult(name=name, passed=bool(condition), message=message, hint=hint)


def check_version_alignment() -> CheckResult:
    """Ensure the changelog version matches the project metadata."""
    import tomllib  # Python 3.11+

    pyproject = tomllib.loads(read_text("pyproject.toml"))
    version = pyproject["project"]["version"]
    changelog = read_text("CHANGELOG.md")
    match = re.search(r"^## \[(v?\d+\.\d+\.\d+)\]", changelog, flags=re.MULTILINE)
    expected = f"v{version}"
    return ensure(
        bool(match) and match.group(1) == expected,
        "Version alignment",
        f"Latest changelog entry should match project version ({expected}).",
        "Update CHANGELOG.md to point to the current pyproject version or bump the metadata.",
    )


def check_readme_offline_instructions() -> CheckResult:
    content = read_text("README.md")
    pattern = r"watcher run --offline"
    return ensure(
        re.search(pattern, content) is not None,
        "README offline quickstart",
        "README must document the offline CLI invocation.",
        "Document an offline command example (watcher run --offline --prompt ...).",
    )


def check_offline_doc_page() -> CheckResult:
    mkdocs = read_text("mkdocs.yml")
    doc_exists = (REPO_ROOT / "docs" / "offline_guide.md").exists()
    return ensure(
        "offline_guide.md" in mkdocs and doc_exists,
        "Offline guide page",
        "MkDocs configuration should expose the offline guide.",
        "Reference docs/offline_guide.md from mkdocs.yml and keep the file present.",
    )


def check_offline_e2e_test() -> CheckResult:
    tests = read_text("tests/test_e2e_offline.py")
    markers = "@pytest.mark.e2e_offline" in tests
    command = "watcher run --offline" in tests
    return ensure(
        markers and command,
        "Offline E2E test",
        "Offline pytest scenario must exist and call watcher run --offline.",
        "Add a pytest.mark.e2e_offline test covering watcher run --offline",
    )


def check_docker_multiarch() -> CheckResult:
    workflow = read_text(".github/workflows/docker.yml")
    return ensure(
        "platforms: linux/amd64,linux/arm64" in workflow,
        "Docker multi-arch",
        "Docker workflow must publish both amd64 and arm64 manifests.",
        "Configure docker/build-push-action with --platform linux/amd64,linux/arm64.",
    )


def check_release_permissions() -> CheckResult:
    workflow = read_text(".github/workflows/release.yml")
    has_contents = "contents: write" in workflow
    has_packages = "packages: write" in workflow
    has_id_token = "id-token: write" in workflow
    return ensure(
        has_contents and has_packages and has_id_token,
        "Release token permissions",
        "Release workflow should request contents, packages and id-token writes.",
        "Set permissions for contents, packages and id-token in release.yml jobs.",
    )


def check_model_hash_generation() -> CheckResult:
    script = read_text("scripts/setup-local-models.sh")
    return ensure(
        "sha256(" in script,
        "Model hashing",
        "Local model bootstrap must generate SHA256 checksums.",
        "Add a SHA256 checksum generation step to scripts/setup-local-models.sh.",
    )


def check_metrics_directory() -> CheckResult:
    exists = (REPO_ROOT / "metrics").is_dir()
    return ensure(
        exists,
        "Metrics directory",
        "metrics/ directory should exist for benchmark exports.",
        "Create a metrics/ directory committed to the repository for evaluation outputs.",
    )


def check_coverage_gate() -> CheckResult:
    tests = read_text("noxfile.py")
    return ensure(
        "--cov-fail-under=90" in tests and "DIFF_COVER_FAIL_UNDER = 100" in tests,
        "Coverage gates",
        "Nox sessions must enforce coverage >=90% and diff coverage 100%.",
        "Update noxfile.py to set --cov-fail-under=90 and DIFF_COVER_FAIL_UNDER=100.",
    )


def main() -> int:
    checks = [
        check_version_alignment(),
        check_readme_offline_instructions(),
        check_offline_doc_page(),
        check_offline_e2e_test(),
        check_docker_multiarch(),
        check_release_permissions(),
        check_model_hash_generation(),
        check_metrics_directory(),
        check_coverage_gate(),
    ]

    failures = [check for check in checks if not check.passed]

    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.message}")
        if not check.passed and check.hint:
            print(f"    Hint: {check.hint}")

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1

    print("\nAll static policy checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
