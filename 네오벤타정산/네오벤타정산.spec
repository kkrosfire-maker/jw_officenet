# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정 (onedir).

onefile 은 쓰지 않는다. Streamlit 은 static 자산이 많아서 onefile 로 묶으면
실행할 때마다 수백 MB 를 임시폴더에 풀어 매우 느리다.
"""
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = []

# Streamlit 은 static 파일·메타데이터·동적 import 가 많아 통째로 수집해야 한다.
for package in ("streamlit", "altair", "pyarrow"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# importlib.metadata 로 버전을 읽는 패키지들
for package in (
    "streamlit",
    "pandas",
    "numpy",
    "openpyxl",
    "altair",
    "pyarrow",
    "pydeck",
    "tornado",
    "packaging",
):
    try:
        datas += copy_metadata(package)
    except Exception:  # noqa: BLE001 - 없는 패키지는 건너뛴다
        pass

# Streamlit 이 디스크에서 직접 읽어 실행하는 우리 소스
datas += [
    ("app.py", "."),
    ("uihelp.py", "."),
    ("core", "core"),
    ("pages", "pages"),
    (".streamlit", ".streamlit"),
]

hiddenimports += [
    "core",
    "uihelp",
    "openpyxl",
    "openpyxl.cell._writer",
    "pandas",
    "streamlit.runtime.scriptrunner.magic_funcs",
]


a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "xlwings", "IPython"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="네오벤타정산",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 검은 콘솔창 없이 앱 창만 뜬다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="네오벤타정산",
)
