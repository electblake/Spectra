# -*- mode: python ; coding: utf-8 -*-

import platform
import tomllib


with open("pyproject.toml", "rb") as pyproject_file:
    project = tomllib.load(pyproject_file)["project"]

artifact_name = (
    f"Spectra-{project['version']}-{platform.system().lower()}-"
    f"{platform.machine().lower()}"
)

a = Analysis(
    ["app/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=artifact_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
