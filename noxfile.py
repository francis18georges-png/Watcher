"""Automated quality sessions for Watcher."""

from __future__ import annotations

import os
from pathlib import Path

import nox

DEFAULT_PYTHON_VERSION = "3.12"
PYTHON_VERSIONS = tuple(
    version.strip()
    for version in os.environ.get("WATCHER_NOX_PYTHON", DEFAULT_PYTHON_VERSION).split(","
    )
    if version.strip()
)
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

nox.options.sessions = ("lint", "typecheck", "tests", "build", "security")
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
    session.run("pytest", "-q")


@nox.session(python=PYTHON_VERSIONS)
def build(session: nox.Session) -> None:
    """Build the project wheel and source distribution."""
    install_project(session, "build")
    session.run("python", "-m", "build")
