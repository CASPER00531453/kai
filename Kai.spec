# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

# Kai.exe's details (Properties -> Details): who makes it, what it is, which
# version. A program that says so is less often mistaken for something else by
# the antivirus engines that only guess. The version is read from version.py.
_version = {}
exec(open("version.py", encoding="utf-8").read(), _version)
_parts = tuple(int(p) for p in (_version["VERSION"].split(".") + ["0", "0", "0"])[:4])
VERSION_INFO = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_parts, prodvers=_parts, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
    kids=[
        StringFileInfo([StringTable("041F04B0", [
            StringStruct("CompanyName", "Casper Technology"),
            StringStruct("FileDescription", "Kai - Windows için yapay zekâ asistanı"),
            StringStruct("FileVersion", _version["VERSION"]),
            StringStruct("InternalName", "Kai"),
            StringStruct("LegalCopyright", "Copyright (c) 2026 Casper Technology. All rights reserved."),
            StringStruct("OriginalFilename", "Kai.exe"),
            StringStruct("ProductName", "Kai"),
            StringStruct("ProductVersion", _version["VERSION"]),
            StringStruct("Comments", "https://casper-technology.vercel.app/"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x041F, 1200])]),
    ],
)

datas = [('models/face_detection_yunet_2023mar.onnx', 'models'), ('_coucou_ui/dist', 'island_ui')]
binaries = []
hiddenimports = ['pythoncom', 'pywintypes', 'win32com.shell.shell', 'win32file', 'win32pipe', 'winrt.windows.media.control', 'winrt.windows.storage.streams', 'winrt.windows.foundation', 'winrt.windows.foundation.collections', 'comtypes', 'PIL.ImageTk', 'menu_window', 'app_window', 'kaicalendar', 'report', 'extras', 'desktop_chat', 'vitals', 'feedback', 'taskqueue', 'usage', 'daily', 'admin', 'clr_loader', 'pythonnet']
tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('miniaudio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('uiautomation')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sherpa_onnx')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyaudiowpatch')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sentencepiece')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# Without its test suite: hundreds of modules nobody runs, and minutes of build time.
hiddenimports += collect_submodules('icalendar', filter=lambda name: '.test' not in name)
datas += collect_data_files('icalendar', excludes=['**/test/**', '**/tests/**'])
# Without its test suite: hundreds of modules nobody runs, and minutes of build time.
hiddenimports += collect_submodules('recurring_ical_events', filter=lambda name: '.test' not in name)
datas += collect_data_files('recurring_ical_events', excludes=['**/test/**', '**/tests/**'])
tmp_ret = collect_all('x_wr_timezone')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tzdata')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# One folder, not one file: a one-file Kai unpacked ~265 MB into %TEMP% for each
# of its three processes on every start (and Defender scanned it all again),
# which spun the fans up. Installed as a folder, nothing is unpacked.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kai',
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
    icon=['kai.ico'],
    version=VERSION_INFO,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Kai',
)