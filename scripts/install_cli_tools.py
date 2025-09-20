"""Download security CLI tools for the local environment.

This helper fetches the official release archives of ``gitleaks`` and
``trivy`` for the current operating system and extracts the binaries into a
directory that can be added to the ``PATH``.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


GITLEAKS_VERSION = "8.18.4"
TRIVY_VERSION = "0.51.3"


class InstallationError(RuntimeError):
    """Raised when a tool cannot be downloaded or extracted."""


@dataclass(frozen=True)
class ToolSpec:
    """Metadata describing how to install an external CLI tool."""

    name: str
    version: str
    url: str
    binary_name: str

    @property
    def version_file(self) -> str:
        """Return the name of the metadata file storing the installed version."""

        return f".{self.name}.version"


def _normalize_arch(machine: str) -> str:
    normalized = machine.lower()
    if normalized in {"x86_64", "amd64"}:
        return "x64"
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    raise InstallationError(f"Unsupported CPU architecture: {machine}")


def _normalize_system(system: str) -> str:
    normalized = system.lower()
    if normalized.startswith("linux"):
        return "linux"
    if normalized.startswith("darwin"):
        return "darwin"
    if normalized.startswith("windows"):
        return "windows"
    raise InstallationError(f"Unsupported operating system: {system}")


def _gitleaks_spec(system: str, arch: str) -> ToolSpec:
    if system == "windows":
        if arch != "x64":
            raise InstallationError("gitleaks provides Windows binaries for x64 only")
        archive = f"gitleaks_{GITLEAKS_VERSION}_windows_{arch}.zip"
        binary = "gitleaks.exe"
    else:
        archive = f"gitleaks_{GITLEAKS_VERSION}_{system}_{arch}.tar.gz"
        binary = "gitleaks"

    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/{archive}"
    return ToolSpec("gitleaks", GITLEAKS_VERSION, url, binary)


def _trivy_spec(system: str, arch: str) -> ToolSpec:
    match (system, arch):
        case ("linux", "x64"):
            archive = f"trivy_{TRIVY_VERSION}_Linux-64bit.tar.gz"
            binary = "trivy"
        case ("linux", "arm64"):
            archive = f"trivy_{TRIVY_VERSION}_Linux-ARM64.tar.gz"
            binary = "trivy"
        case ("darwin", "x64"):
            archive = f"trivy_{TRIVY_VERSION}_macOS-64bit.tar.gz"
            binary = "trivy"
        case ("darwin", "arm64"):
            archive = f"trivy_{TRIVY_VERSION}_macOS-ARM64.tar.gz"
            binary = "trivy"
        case ("windows", "x64"):
            archive = f"trivy_{TRIVY_VERSION}_Windows-64bit.zip"
            binary = "trivy.exe"
        case _:
            raise InstallationError(
                "trivy binaries are only published for Linux, macOS (x64/ARM64), and Windows x64"
            )

    url = f"https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}/{archive}"
    return ToolSpec("trivy", TRIVY_VERSION, url, binary)


def _download(url: str, destination: Path) -> None:
    try:
        with urlopen(url) as response, destination.open("wb") as file_handle:
            shutil.copyfileobj(response, file_handle)
    except HTTPError as exc:  # pragma: no cover - requires network failure
        raise InstallationError(f"Failed to download {url}: {exc}") from exc
    except URLError as exc:  # pragma: no cover - requires network failure
        raise InstallationError(f"Unable to reach {url}: {exc}") from exc


def _extract_archive(archive_path: Path, destination: Path) -> None:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)
        return

    with tarfile.open(archive_path, mode="r:*") as archive:
        archive.extractall(destination)


def _locate_binary(search_root: Path, names: Iterable[str]) -> Path:
    for name in names:
        for candidate in search_root.rglob(name):
            if candidate.is_file():
                return candidate
    raise InstallationError(f"Unable to find binary after extraction: {', '.join(names)}")


def _ensure_executable(path: Path) -> None:
    if os.name == "nt":  # Windows manages executability through the extension
        return
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_tools(install_dir: Path, *, force: bool = False) -> None:
    system = _normalize_system(platform.system())
    arch = _normalize_arch(platform.machine())

    specs = (_gitleaks_spec(system, arch), _trivy_spec(system, arch))
    install_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        binary_path = install_dir / spec.binary_name
        version_file = install_dir / spec.version_file

        if not force and binary_path.exists() and version_file.exists():
            recorded_version = version_file.read_text(encoding="utf-8").strip()
            if recorded_version == spec.version:
                print(
                    f"{spec.name} {spec.version} already installed at {binary_path}",
                    file=sys.stderr,
                )
                continue

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            archive_path = temp_dir / "download"
            extraction_dir = temp_dir / "extracted"
            extraction_dir.mkdir(parents=True, exist_ok=True)

            print(f"Downloading {spec.name} {spec.version}…")
            _download(spec.url, archive_path)
            _extract_archive(archive_path, extraction_dir)

            extracted_binary = _locate_binary(extraction_dir, (spec.binary_name,))
            shutil.copy2(extracted_binary, binary_path)
            _ensure_executable(binary_path)
            version_file.write_text(spec.version, encoding="utf-8")
            print(f"Installed {spec.name} {spec.version} to {binary_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install security CLI tools")
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=Path(".tools"),
        help="Directory where the binaries should be installed",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reinstall the tools even if the requested version is already present",
    )
    parser.add_argument(
        "--add-to-path",
        action="store_true",
        help="Append the installation directory to the PATH via the GITHUB_PATH mechanism",
    )
    return parser.parse_args(argv)


def _append_to_github_path(directory: Path) -> None:
    github_path = os.environ.get("GITHUB_PATH")
    if not github_path:
        print("GITHUB_PATH is not defined; skipping PATH export", file=sys.stderr)
        return

    resolved = directory.resolve()
    with Path(github_path).open("a", encoding="utf-8") as handle:
        handle.write(str(resolved) + os.linesep)
    print(f"Added {resolved} to PATH via GITHUB_PATH")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        install_tools(args.install_dir, force=args.force)
    except InstallationError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.add_to_path:
        _append_to_github_path(args.install_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
