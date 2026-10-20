# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['blogminer_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        (
            'C:\\Users\\JW\\AppData\\Roaming\\Python\\Python314\\site-packages\\kiwipiepy_model',
            'kiwipiepy_model'
        ),
        (
            'C:\\Users\\JW\\AppData\\Roaming\\Python\\Python314\\site-packages\\kiwipiepy',
            'kiwipiepy'
        ),
        (
            'C:\\Users\\JW\\AppData\\Roaming\\Python\\Python314\\site-packages\\docx\\templates',
            'docx\\templates'
        ),
    ],
    hiddenimports=[
        'kiwipiepy', 'kiwipiepy_model',
        'lxml', 'lxml.etree', 'lxml._elementpath',
        'bs4', 'openpyxl', 'docx', 'requests',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='blogminer',
    debug=False,
    strip=False,
    upx=False,
    console=False,      # ← 콘솔 창 없음 (윈도우 앱)
    windowed=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='blogminer',
)
