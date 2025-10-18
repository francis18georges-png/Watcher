"""Build Windows installers (MSI and MSIX) for Watcher."""

from __future__ import annotations

import argparse
import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"[package-windows] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=cwd)


def download_wix(target: Path) -> Path:
    url = (
        "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/"
        "wix311-binaries.zip"
    )
    archive = target / "wix.zip"
    if not archive.exists():
        import urllib.request

        with urllib.request.urlopen(url) as response, archive.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    wix_dir = target / "wix"
    if not wix_dir.exists():
        shutil.unpack_archive(archive, wix_dir)
    return wix_dir


def generate_wxs(dist_root: Path, version: str, output_dir: Path) -> Path:
    component_lines: list[str] = []
    component_ids: list[int] = []
    for idx, path in enumerate(sorted(dist_root.rglob("*"))):
        if not path.is_file():
            continue
        rel = path.relative_to(dist_root)
        component_ids.append(idx)
        component_lines.append(
            f"      <Component Id=\"cmp{idx}\" Guid=\"*\">\n"
            f"        <File Id=\"file{idx}\" Name=\"{rel.name}\" Source=\"{path.as_posix()}\" KeyPath=\"yes\" />\n"
            "      </Component>"
        )

    components = "\n".join(component_lines)
    features = "\n".join(
        f"        <ComponentRef Id=\"cmp{idx}\" />" for idx in component_ids
    )

    wxs_content = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Wix xmlns=\"http://schemas.microsoft.com/wix/2006/wi\">\n"
        "  <Product Id=\"*\" Name=\"Watcher\" Language=\"1033\" Version=\""
        + version
        + "\" Manufacturer=\"Watcher\" UpgradeCode=\"6D7E77F4-4C7E-4D2A-8B2C-76FC928C6A8F\">\n"
        "    <Package InstallerVersion=\"500\" Compressed=\"yes\" InstallScope=\"perMachine\" />\n"
        "    <MediaTemplate />\n"
        "    <Directory Id=\"TARGETDIR\" Name=\"SourceDir\">\n"
        "      <Directory Id=\"ProgramFilesFolder\">\n"
        "        <Directory Id=\"INSTALLFOLDER\" Name=\"Watcher\">\n"
        + components
        + "\n        </Directory>\n"
        "      </Directory>\n"
        "    </Directory>\n"
        "    <Feature Id=\"MainFeature\" Title=\"Watcher\" Level=\"1\">\n"
        + features
        + "\n    </Feature>\n"
        "  </Product>\n"
        "</Wix>\n"
    )

    wxs_path = output_dir / "watcher.wxs"
    wxs_path.write_text(wxs_content, encoding="utf-8")
    return wxs_path


def build_msi(dist_root: Path, artifact_dir: Path, version: str) -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="watcher-windows-"))
    wix_dir = download_wix(workdir)
    wxs = generate_wxs(dist_root, version, workdir)
    candle = wix_dir / "candle.exe"
    light = wix_dir / "light.exe"
    run([candle.as_posix(), wxs.as_posix(), "-out", str(workdir / "watcher.wixobj")])
    run(
        [
            light.as_posix(),
            str(workdir / "watcher.wixobj"),
            "-ext",
            "WixUIExtension",
            "-out",
            str(workdir / "Watcher.msi"),
        ]
    )
    target = artifact_dir / f"watcher-{version}.msi"
    shutil.copy2(workdir / "Watcher.msi", target)
    return target


def build_msix(dist_root: Path, artifact_dir: Path, version: str) -> Path:
    layout = Path(tempfile.mkdtemp(prefix="watcher-msix-")) / "layout"
    shutil.copytree(dist_root, layout / "Watcher")
    manifest = layout / "AppxManifest.xml"
    manifest.write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Package xmlns=\"http://schemas.microsoft.com/appx/manifest/foundation/windows10\"\n"
        "         xmlns:uap=\"http://schemas.microsoft.com/appx/manifest/uap/windows10\"\n"
        "         IgnorableNamespaces=\"uap\">\n"
        "  <Identity Name=\"dev.watcher.cli\" Publisher=\"CN=Watcher\" Version=\""
        + version
        + ".0\"/>\n"
        "  <Properties>\n"
        "    <DisplayName>Watcher</DisplayName>\n"
        "    <PublisherDisplayName>Watcher</PublisherDisplayName>\n"
        "    <Logo>Watcher\\Watcher.ico</Logo>\n"
        "  </Properties>\n"
        "  <Resources>\n"
        "    <Resource Language=\"en-us\"/>\n"
        "  </Resources>\n"
        "  <Dependencies>\n"
        "    <TargetDeviceFamily Name=\"Windows.Desktop\" MinVersion=\"10.0.19041.0\" MaxVersionTested=\"10.0.19045.0\"/>\n"
        "  </Dependencies>\n"
        "  <Applications>\n"
        "    <Application Id=\"Watcher\" Executable=\"Watcher\\Watcher.exe\" EntryPoint=\"Windows.FullTrustApplication\">\n"
        "      <uap:VisualElements DisplayName=\"Watcher\" Description=\"Watcher\" Square150x150Logo=\"Watcher\\Watcher.ico\"/>\n"
        "    </Application>\n"
        "  </Applications>\n"
        "  <Capabilities>\n"
        "    <Capability Name=\"internetClientServer\"/>\n"
        "  </Capabilities>\n"
        "</Package>\n",
        encoding="utf-8",
    )
    msix = artifact_dir / f"watcher-{version}.msix"
    if msix.exists():
        msix.unlink()
    run([
        "MakeAppx.exe",
        "pack",
        "/d",
        str(layout),
        "/p",
        str(msix),
    ])
    return msix


def import_certificate(base64_value: str, password: str) -> Path:
    raw = base64.b64decode(base64_value)
    pfx_path = Path(tempfile.mkdtemp(prefix="watcher-cert-")) / "cert.pfx"
    pfx_path.write_bytes(raw)
    run([
        "powershell",
        "-Command",
        "Import-PfxCertificate",
        str(pfx_path),
        "Cert:\\LocalMachine\\My",
        "-Password",
        f"(ConvertTo-SecureString '{password}' -AsPlainText -Force)",
    ])
    return pfx_path


def sign_artifact(path: Path, thumbprint: str) -> None:
    run([
        "powershell",
        "-Command",
        "Set-AuthenticodeSignature",
        str(path),
        f"(Get-ChildItem Cert:\\LocalMachine\\My\n | Where-Object {{$_.Thumbprint -eq '{thumbprint}'}})"
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signing-certificate", default="")
    parser.add_argument("--signing-password", default="")
    parser.add_argument("--signing-thumbprint", default="")
    args = parser.parse_args()

    dist_root = args.dist_root.resolve()
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    msi = build_msi(dist_root, artifact_dir, args.version)
    msix = build_msix(dist_root, artifact_dir, args.version)

    if args.signing_certificate and args.signing_password and args.signing_thumbprint:
        import_certificate(args.signing_certificate, args.signing_password)
        sign_artifact(msi, args.signing_thumbprint)
        sign_artifact(msix, args.signing_thumbprint)


if __name__ == "__main__":
    main()
