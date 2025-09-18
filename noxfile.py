"""Automated quality sessions for Watcher."""

from __future__ import annotations

import nox

PYTHON_VERSIONS = ["3.12"]
SOURCE_DIRECTORIES = ("app", "config", "datasets", "tests", "train.py", "plugins.toml")

nox.options.sessions = ("lint", "typecheck", "security", "tests", "build")
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
