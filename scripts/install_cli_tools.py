"""Download security CLI tools for the local environment.

This helper fetches the official release archives of ``gitleaks`` and
``trivy`` for the current operating system and extracts the binaries into a
directory that can be added to the ``PATH``.
"""

from __future__ import annotations

import argparse
import hashlib
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
TRIVY_VERSION = "0.51.4"


class InstallationError(RuntimeError):
    """Raised when a tool cannot be downloaded or extracted."""


@dataclass(frozen=True)
class ToolHashes:
    """Expected integrity data for an external CLI tool."""

    archive: str
    binary: str


@dataclass(frozen=True)
class ToolSpec:
    """Metadata describing how to install an external CLI tool."""

    name: str
    version: str
    url: str
    binary_name: str
    hashes: ToolHashes

    @property
    def version_file(self) -> str:
        """Return the name of the metadata file storing the installed version."""

        return f".{self.name}.version"


GITLEAKS_HASHES: dict[tuple[str, str], ToolHashes] = {
    ("darwin", "x64"): ToolHashes(
        archive="1a69e5666b13cd374889cbcb1939ed1573b63b551251283d5d2329a53cf58e2f",
        binary="3f83ea726b8f10c16dfa7ea08c73d1474ddbfe24db4a00e6764ec9abac05e19e",
    ),
    ("darwin", "arm64"): ToolHashes(
        archive="a480d8593acd8215b22402cf0f3f88b01dcd3610c63b5391db640f7767e62104",
        binary="a86787a498e702f8820fc73c219ca44ecdf1f415eed8daf922888ffd6c4cf680",
    ),
    ("linux", "x64"): ToolHashes(
        archive="ba6dbb656933921c775ee5a2d1c13a91046e7952e9d919f9bac4cec61d628e7d",
        binary="46a05260e7cce527f132cb618de59d22262b8b5eb47f66c288447b95c7a98b7e",
    ),
    ("linux", "arm64"): ToolHashes(
        archive="bf5f7f466ebfade1296c8bd32cf7d3f592c2aa78836aa9980ffbe2cadca7a861",
        binary="fc286fab02c3a0ba80670fc9f8cb1b495a2f62eb953d26113cfa3562f76b340b",
    ),
    ("windows", "x64"): ToolHashes(
        archive="9ba442ca7dda19885a2e569f43a127289feeb2b5fb0dfa251dafd277f4a0ba91",
        binary="b3ef977b1b8b3f6921e16759e7cfbd91cf738c4f6aa13e676d8e0ed264103912",
    ),
}


TRIVY_HASHES: dict[tuple[str, str], ToolHashes] = {
    ("linux", "x64"): ToolHashes(
        archive="eee127e93ed40e8f1c7bc2baa062a2635b01346a287046207d186c14b7a33af3",
        binary="ec6400c62804d83262f063f4efd3ef4c79395d2e221142b2aa238802cdb9b410",
    ),
    ("linux", "arm64"): ToolHashes(
        archive="9f8662f99478e4e13f4f20acaabd148057e60f8b7d886d7bb54bacf9793865df",
        binary="a06bd97c202fefc262d80651002a72131d845890b2b8a185d9d4ff7752d22b00",
    ),
    ("darwin", "x64"): ToolHashes(
        archive="9c04716f984308798f04292c692d8dde6d0a719dd518459538eac11fd8ea6daa",
        binary="3d679d33256a2433bdcac0904ca6462dff8db6822808980cecc2fe73cf8534bc",
    ),
    ("darwin", "arm64"): ToolHashes(
        archive="d46302eb3545b04ae8684a0f5f29d6e108ae45e094189c2e4353626f0bf1b8c6",
        binary="94e7c559e23eee37cdf137e4298816872544878d15f55f4252f7a184e998abec",
    ),
    ("windows", "x64"): ToolHashes(
        archive="194dfacd41a55d1acf60477a04603f2917fb0b78cf30c7f23a2a9aa03495ef8c",
        binary="e4f921e48df707323f2dd75916b0237f03e464220b96dc00e537c3af59e4a45d",
    ),
}


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
    try:
        hashes = GITLEAKS_HASHES[(system, arch)]
    except KeyError as exc:
        raise InstallationError(
            "Unsupported gitleaks build for the current platform"
        ) from exc

    if system == "windows":
        archive = f"gitleaks_{GITLEAKS_VERSION}_windows_{arch}.zip"
        binary = "gitleaks.exe"
    else:
        archive = f"gitleaks_{GITLEAKS_VERSION}_{system}_{arch}.tar.gz"
        binary = "gitleaks"

    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/{archive}"
    return ToolSpec("gitleaks", GITLEAKS_VERSION, url, binary, hashes)


def _trivy_spec(system: str, arch: str) -> ToolSpec:
    try:
        hashes = TRIVY_HASHES[(system, arch)]
    except KeyError as exc:
        raise InstallationError(
            "trivy binaries are only published for Linux, macOS (x64/ARM64), and Windows x64"
        ) from exc

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
            archive = f"trivy_{TRIVY_VERSION}_windows-64bit.zip"
            binary = "trivy.exe"
        case _:
            raise AssertionError("Unexpected platform combination")

    url = f"https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}/{archive}"
    return ToolSpec("trivy", TRIVY_VERSION, url, binary, hashes)


def _download(url: str, destination: Path) -> None:
    try:
        with urlopen(url) as response, destination.open("wb") as file_handle:
            shutil.copyfileobj(response, file_handle)
    except HTTPError as exc:  # pragma: no cover - requires network failure
        raise InstallationError(f"Failed to download {url}: {exc}") from exc
    except URLError as exc:  # pragma: no cover - requires network failure
        raise InstallationError(f"Unable to reach {url}: {exc}") from exc


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sha256(path: Path, expected: str, *, description: str) -> None:
    actual = _compute_sha256(path)
    if actual != expected:
        raise InstallationError(
            f"{description} checksum mismatch: expected {expected}, got {actual}"
        )


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
            _verify_sha256(
                archive_path,
                spec.hashes.archive,
                description=f"{spec.name} {spec.version} archive",
            )
            _extract_archive(archive_path, extraction_dir)

            extracted_binary = _locate_binary(extraction_dir, (spec.binary_name,))
            _verify_sha256(
                extracted_binary,
                spec.hashes.binary,
                description=f"{spec.name} {spec.version} binary",
            )
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
