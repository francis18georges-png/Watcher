# -*- mode: python ; coding: utf-8 -*-

import os
import pathlib

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

project_root = pathlib.Path(__file__).resolve().parent.parent

datas = [("app/plugins.toml", "app")]
for extra in ("LICENSE", "example.env"):
    candidate = project_root / extra
    if candidate.exists():
        datas.append((extra, "."))

datas += collect_data_files(
    "config",
    includes=["*.toml", "*.yml", "*.yaml", "*.json"],
)
prompt_dir = project_root / "app" / "llm" / "prompts"
if prompt_dir.exists():
    for prompt in prompt_dir.glob("*.md"):
        datas.append((prompt.relative_to(project_root).as_posix(), "app/llm/prompts"))


def _normalize_data_entries(entries):
    normalized = []
    for source, target in entries:
        src_path = pathlib.Path(source)
        if not src_path.is_absolute():
            src_path = project_root / src_path
        src_path = src_path.resolve()
        try:
            relative = src_path.relative_to(project_root)
            src_value = relative.as_posix()
        except ValueError:
            src_value = src_path.as_posix()
        normalized.append((src_value, target))
    return sorted(normalized)


datas = _normalize_data_entries(datas)

# Ensure PyInstaller does not rely on user specific cache paths when available.
pyinstaller_config_dir = os.environ.get("PYINSTALLER_CONFIG_DIR")
if pyinstaller_config_dir:
    pathlib.Path(pyinstaller_config_dir).mkdir(parents=True, exist_ok=True)


a = Analysis(
    ['app/cli.py'],
    pathex=[project_root.as_posix()],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Watcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Watcher',
)
