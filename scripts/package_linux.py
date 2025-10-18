"""Helpers to build Linux installers for Watcher."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run *cmd* and raise when the command fails."""

    print(f"[package-linux] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=cwd, env=env)


def ensure_appimagetool(target_dir: Path) -> Path:
    """Download the AppImage tool used to build AppImage artifacts."""

    url = (
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/"
        "appimagetool-x86_64.AppImage"
    )
    tool_path = target_dir / "appimagetool"
    if tool_path.exists():
        return tool_path

    import urllib.request

    with urllib.request.urlopen(url) as response, tool_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    tool_path.chmod(0o755)
    return tool_path


def build_appimage(dist_root: Path, artifact_dir: Path) -> Path:
    """Create an AppImage package from the PyInstaller distribution."""

    appdir = Path(tempfile.mkdtemp(prefix="watcher-appdir-")) / "Watcher.AppDir"
    runtime = appdir / "usr" / "bin"
    runtime.mkdir(parents=True, exist_ok=True)

    binary = dist_root / "Watcher"
    if not binary.exists():
        raise SystemExit(f"Watcher binary not found in {dist_root}")

    target_bin = runtime / "watcher"
    shutil.copy2(binary, target_bin)
    target_bin.chmod(0o755)

    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    desktop_file = appdir / "usr" / "share" / "applications" / "watcher.desktop"
    desktop_file.write_text(
        """
        [Desktop Entry]
        Type=Application
        Version=1.0
        Name=Watcher
        Comment=Local-first intelligence assistant
        Exec=watcher
        Icon=watcher
        Terminal=true
        Categories=Utility;AI;
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    apprun = appdir / "AppRun"
    apprun.write_text("#!/bin/sh\nexec usr/bin/watcher \"$@\"\n", encoding="utf-8")
    apprun.chmod(0o755)

    icon_src = dist_root / "Watcher.ico"
    if icon_src.exists():
        icons_dir = appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icons_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, icons_dir / "watcher.ico")

    tool_dir = artifact_dir / "_tmp"
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool = ensure_appimagetool(tool_dir)

    appimage_path = artifact_dir / "watcher-linux.AppImage"
    if appimage_path.exists():
        appimage_path.unlink()
    run([tool.as_posix(), appdir.as_posix(), appimage_path.as_posix()])
    return appimage_path


def build_deb(dist_root: Path, artifact_dir: Path, version: str) -> Path:
    """Create a Debian package from the PyInstaller distribution."""

    pkg_root = Path(tempfile.mkdtemp(prefix="watcher-deb-"))
    deb_root = pkg_root / "watcher"
    bin_dir = deb_root / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist_root / "Watcher", bin_dir / "watcher")
    (deb_root / "usr" / "share" / "doc" / "watcher").mkdir(parents=True, exist_ok=True)
    (deb_root / "usr" / "share" / "doc" / "watcher" / "copyright").write_text(
        "Watcher © 2025 Watcher contributors\n",
        encoding="utf-8",
    )
    control_dir = deb_root / "DEBIAN"
    control_dir.mkdir(parents=True, exist_ok=True)
    control_dir.joinpath("control").write_text(
        f"Package: watcher\n"
        f"Version: {version}\n"
        "Section: utils\n"
        "Priority: optional\n"
        "Architecture: amd64\n"
        "Maintainer: Watcher Release <release@watcher.local>\n"
        "Description: Local-first intelligence assistant\n",
        encoding="utf-8",
    )
    deb_path = artifact_dir / f"watcher_{version}_amd64.deb"
    if deb_path.exists():
        deb_path.unlink()
    run(["dpkg-deb", "--build", deb_root.as_posix(), deb_path.as_posix()])
    return deb_path


def build_rpm(dist_root: Path, artifact_dir: Path, version: str) -> Path:
    """Create an RPM package."""

    rpmroot = Path(tempfile.mkdtemp(prefix="watcher-rpm-"))
    (rpmroot / "BUILD").mkdir()
    (rpmroot / "RPMS").mkdir()
    (rpmroot / "SOURCES").mkdir()
    (rpmroot / "SPECS").mkdir()
    (rpmroot / "SRPMS").mkdir()

    sources = rpmroot / "SOURCES" / "watcher.tar.gz"
    with tarfile.open(sources, "w:gz") as archive:
        archive.add(dist_root / "Watcher", arcname="watcher")

    spec = rpmroot / "SPECS" / "watcher.spec"
    spec.write_text(
        f"Name: watcher\n"
        f"Version: {version}\n"
        "Release: 1\n"
        "Summary: Local-first intelligence assistant\n"
        "License: MIT\n"
        "BuildArch: x86_64\n"
        "%description\nWatcher local-first intelligence assistant.\n"
        "%prep\n%setup -q\n"
        "%build\n"
        "%install\nmkdir -p %{buildroot}/usr/bin\n"
        "install -m 0755 watcher %{buildroot}/usr/bin/watcher\n"
        "%files\n/usr/bin/watcher\n"
        "%changelog\n* Thu Jan 01 2025 Watcher Release <release@watcher.local> - "
        f"{version}-1\n- Automated build\n",
        encoding="utf-8",
    )
    run(
        [
            "rpmbuild",
            "-bb",
            spec.as_posix(),
            f"--define=_topdir {rpmroot.as_posix()}",
        ]
    )
    built = next((rpmroot / "RPMS").rglob("*.rpm"))
    target = artifact_dir / built.name
    shutil.copy2(built, target)
    return target


def build_flatpak(dist_root: Path, artifact_dir: Path, version: str) -> Path:
    """Create a Flatpak bundle using flatpak-builder."""

    workdir = Path(tempfile.mkdtemp(prefix="watcher-flatpak-"))
    builddir = workdir / "build"
    repo = workdir / "repo"
    manifest = workdir / "dev.watcher.CLI.yaml"
    source_dir = workdir / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist_root / "Watcher", source_dir / "watcher")
    manifest.write_text(
        "app-id: dev.watcher.CLI\n"
        "runtime: org.freedesktop.Platform\n"
        "runtime-version: '23.08'\n"
        "sdk: org.freedesktop.Sdk\n"
        "command: watcher\n"
        "finish-args:\n  - --share=network\n  - --share=ipc\n  - --device=all\n"
        "modules:\n  - name: watcher\n    buildsystem: simple\n    build-commands:\n"
        "      - install -Dm755 watcher /app/bin/watcher\n"
        "    sources:\n      - type: file\n        path: watcher\n",
        encoding="utf-8",
    )
    run(
        [
            "flatpak-builder",
            "--force-clean",
            builddir.as_posix(),
            manifest.as_posix(),
        ],
        env={**os.environ, "FLATPAK_GL_DRIVERS": "host"},
        cwd=source_dir,
    )
    repo.mkdir(parents=True, exist_ok=True)
    run(["flatpak", "build-export", repo.as_posix(), builddir.as_posix()])
    bundle = artifact_dir / f"watcher-{version}.flatpak"
    run(
        [
            "flatpak",
            "build-bundle",
            repo.as_posix(),
            bundle.as_posix(),
            "dev.watcher.CLI",
            "--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo",
        ]
    )
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    args.dist_root = args.dist_root.resolve()
    args.artifact_dir = args.artifact_dir.resolve()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)

    build_appimage(args.dist_root, args.artifact_dir)
    build_deb(args.dist_root, args.artifact_dir, args.version)
    build_rpm(args.dist_root, args.artifact_dir, args.version)
    build_flatpak(args.dist_root, args.artifact_dir, args.version)


if __name__ == "__main__":
    main()
