"""Automated quality sessions for Watcher."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

import nox
from nox.command import CommandFailed

DEFAULT_PYTHON_VERSIONS = ("3.12",)


def _parse_python_versions(
    value: str | None, default: Iterable[str] = DEFAULT_PYTHON_VERSIONS
) -> list[str]:
    """Return a list of Python versions from a comma/space separated string."""

    if value is None:
        return list(default)

    parts = [fragment.strip() for fragment in re.split(r"[,\s]+", value) if fragment.strip()]
    return parts or list(default)


def get_python_versions() -> list[str]:
    """Resolve the Python versions to use for Nox sessions."""

    return _parse_python_versions(os.environ.get("WATCHER_NOX_PYTHON"))


PYTHON_VERSIONS = get_python_versions()
SOURCE_DIRECTORIES = (
    "app",
    "config",
    "datasets",
    "tests",
    "train.py",
    "app/plugins.toml",
)
SBOM_PATH = Path("dist/Watcher-sbom.json")
SBOM_DIRECTORY = SBOM_PATH.parent
DEFAULT_COMPARE_BRANCH = "origin/main"
DIFF_COVER_FAIL_UNDER = 80

nox.options.sessions = ("lint", "typecheck", "tests", "coverage", "build", "security")
nox.options.reuse_existing_virtualenvs = True


def install_project(session: nox.Session, *extra: str) -> None:
    """Install runtime and development dependencies."""
    session.install("--upgrade", "pip")
    session.install("-r", "requirements.txt")
    session.install("-r", "requirements-dev.txt")
    if extra:
        session.install(*extra)


@nox.session(python=PYTHON_VERSIONS)
def lint(session: nox.Session) -> None:
    """Run formatting and static analysis checks."""
    install_project(session)
    session.run("ruff", "check", *SOURCE_DIRECTORIES)
    session.run("ruff", "format", "--check", *SOURCE_DIRECTORIES)
    session.run("black", "--check", ".")


@nox.session(python=PYTHON_VERSIONS)
def typecheck(session: nox.Session) -> None:
    """Run type checking with mypy."""
    install_project(session)
    session.run("mypy", "app", "tests")


@nox.session(python=PYTHON_VERSIONS)
def security(session: nox.Session) -> None:
    """Execute security scanning tools."""
    install_dir = Path(".tools").resolve()
    session.run(
        "python",
        "scripts/install_cli_tools.py",
        "--install-dir",
        install_dir.as_posix() if os.name != "nt" else str(install_dir),
    )
    existing_path = session.env.get("PATH", "")
    install_dir_str = str(install_dir)
    session.env["PATH"] = (
        f"{install_dir_str}{os.pathsep}{existing_path}" if existing_path else install_dir_str
    )

    install_project(session)
    session.run("bandit", "-q", "-r", ".", "-c", "bandit.yml")
    session.run(
        "semgrep",
        "--quiet",
        "--error",
        "--config",
        "config/semgrep.yml",
        ".",
    )
    session.run(
        "codespell",
        "--skip=.git,.mypy_cache,.pytest_cache,.venv,build,dist,.dvc/cache",
        "-L",
        "crate",
    )
    session.run("gitleaks", "detect", "--source", ".", "--no-banner")
    session.run("pip-audit", "--strict")
    session.run(
        "python",
        "-c",
        f"from pathlib import Path; Path('{SBOM_DIRECTORY.as_posix()}').mkdir(parents=True, exist_ok=True)",
    )
    session.run(
        "trivy",
        "sbom",
        "--format",
        "cyclonedx",
        "--output",
        SBOM_PATH.as_posix(),
        ".",
    )
    session.run(
        "trivy",
        "fs",
        "--scanners",
        "vuln,secret",
        "--severity",
        "HIGH,CRITICAL",
        "--ignore-unfixed",
        "--exit-code",
        "1",
        "--no-progress",
        ".",
    )


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the unit test suite."""
    install_project(session)
    session.run("pytest", "--cov=app", "--cov=config", "--cov-report=xml")


@nox.session(python=PYTHON_VERSIONS)
def coverage(session: nox.Session) -> None:
    """Evaluate coverage on the diff against the target branch."""
    install_project(session)

    coverage_path = Path("coverage.xml")
    if not coverage_path.exists():
        session.error("coverage.xml not found. Run 'nox -s tests' first.")

    compare_branch = os.environ.get("DIFF_COVER_COMPARE_BRANCH", DEFAULT_COMPARE_BRANCH)
    fail_under = os.environ.get("DIFF_COVER_FAIL_UNDER", str(DIFF_COVER_FAIL_UNDER))

    candidates = [compare_branch]
    if compare_branch.startswith("origin/"):
        candidates.append(compare_branch.split("/", 1)[1])

    for candidate in candidates:
        try:
            session.run(
                "git",
                "rev-parse",
                "--verify",
                candidate,
                external=True,
                silent=True,
            )
        except CommandFailed:
            continue
        else:
            compare_branch = candidate
            break
    else:
        session.error(
            "Unable to locate a branch to compare against for diff coverage. "
            "Fetch the target branch or set DIFF_COVER_COMPARE_BRANCH."
        )

    session.run(
        "diff-cover",
        coverage_path.as_posix(),
        f"--fail-under={fail_under}",
        "--compare-branch",
        compare_branch,
    )


@nox.session(python=PYTHON_VERSIONS)
def build(session: nox.Session) -> None:
    """Build the project wheel and source distribution."""
    install_project(session, "build")
    session.run("python", "-m", "build")
