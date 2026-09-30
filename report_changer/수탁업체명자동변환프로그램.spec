# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/JW/AppData/Roaming/Python/Python314/site-packages/tkinterdnd2/tkdnd', 'tkinterdnd2/tkdnd'), ('app.ico', '.')],
    hiddenimports=['win32timezone'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'numpy', 'scipy', 'torch', 'torchvision', 'tensorflow', 'matplotlib', 'PIL', 'lxml', 'sklearn', 'cv2', 'transformers', 'keras', 'seaborn', 'plotly', 'sympy', 'numba'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='수탁업체명자동변환프로그램',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='수탁업체명자동변환프로그램',
)
