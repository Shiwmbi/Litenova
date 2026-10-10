# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve()


a = Analysis(
    ["main.py"],
    pathex=[
        str(PROJECT_ROOT),
    ],
    binaries=[],
    datas=[
        (
            str(
                PROJECT_ROOT
                / "resources"
            ),
            "resources",
        ),
        (
            str(
                PROJECT_ROOT
                / "app"
                / "styles"
            ),
            "app/styles",
        ),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(
    a.pure
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Litenova",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[
        str(
            PROJECT_ROOT
            / "resources"
            / "icons"
            / "litenova.ico"
        )
    ],
    version=str(
        PROJECT_ROOT
        / "version_info.txt"
    ),
)