# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds Mission Control for macOS (.app) and Windows (dir).
Run from the repo root:  pyinstaller packaging/mission_control.spec

Signing (macOS): set CODESIGN_IDENTITY to a "Developer ID Application: ..."
identity and PyInstaller signs every nested binary with the hardened runtime
entitlements — required for notarization. Unset, it builds ad-hoc signed.
"""
import os
import sys

ROOT = os.path.dirname(SPECPATH)          # repo root (spec lives in packaging/)
MAC = sys.platform == "darwin"
VERSION = os.environ.get("APP_VERSION", "1.0.0").lstrip("v")   # v1.0.0 -> 1.0.0

datas = [(os.path.join(ROOT, "baseline.sample.json"), ".")]
if MAC:
    datas.append((os.path.join(ROOT, "icon.icns"), "."))

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Mission Control",
    console=False,
    icon=os.path.join(ROOT, "packaging", "icon.ico") if not MAC else None,
    codesign_identity=os.environ.get("CODESIGN_IDENTITY"),
    entitlements_file=os.path.join(ROOT, "packaging", "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Mission Control",
)

if MAC:
    app = BUNDLE(
        coll,
        name="Mission Control.app",
        icon=os.path.join(ROOT, "icon.icns"),
        bundle_identifier="com.keane.mission-control",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT License",
        },
    )
