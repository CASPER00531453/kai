# -*- mode: python ; coding: utf-8 -*-
# Casper.exe: tek dosya, konsolsuz. Derleme: build.ps1 ya da GitHub Actions (casper-exe.yml).
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("casper/ui", "casper/ui"), ("casper/knowledge", "casper/knowledge")]
binaries = []
hiddenimports = ["win32crypt", "pywintypes", "clr_loader", "pythonnet"]
hiddenimports += collect_submodules("winrt")
for pkg in ("webview", "anthropic"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Casper",
    icon="assets/casper.ico",
    console=False,
    upx=False,
)
