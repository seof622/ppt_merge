# PyInstaller 단일 EXE: Qt·Python·COM 런타임만 포함한다.
from pathlib import Path
import os

root = Path(SPECPATH).parent
theme = os.environ.get("PPT_MERGE_BUILD_THEME", "slate-blue")
runtime_hooks = ([str(root / "packaging/gruvbox_material_hook.py")]
                 if theme == "gruvbox-material" else [])
analysis = Analysis(
    [str(root / "packaging" / "entrypoint.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "assets/fonts"), "assets/fonts")] if theme == "gruvbox-material" else [],
    hiddenimports=["pythoncom", "pywintypes", "win32com.client", "win32timezone"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="PPTMerge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
