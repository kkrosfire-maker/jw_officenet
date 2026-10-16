# -*- mode: python ; coding: utf-8 -*-
# onedir 필수 (Playwright 는 onefile 에서 동작하지 않음)
import playwright
from pathlib import Path

playwright_pkg = Path(playwright.__file__).parent

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(playwright_pkg / 'driver'), 'playwright/driver'),
        ('app.ico', '.'),
    ],
    hiddenimports=[
        'playwright',
        'playwright.sync_api',
        'playwright._impl._driver',
        'playwright._impl._sync_playwright',
        'PIL._tkinter_finder',
    ],
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
    [],
    exclude_binaries=True,
    name='공지자동발행',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='공지자동발행',
)
