# -*- mode: python ; coding: utf-8 -*-
# onedir 필수: Playwright 드라이버를 _internal/playwright/driver에 넣는다.
from pathlib import Path
import playwright

playwright_pkg = Path(playwright.__file__).parent

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(str(playwright_pkg / 'driver'), 'playwright/driver')],
    hiddenimports=['win32crypt', 'openpyxl', 'xlrd'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'pytest', 'torch', 'torchvision', 'scipy',
              'pyarrow', 'PIL', 'sklearn', 'numba', 'sqlalchemy', 'lxml', 'cryptography', 'Pythonwin'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='한진택배정산',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='한진택배정산',
)
