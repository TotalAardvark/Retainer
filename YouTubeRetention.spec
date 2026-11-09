# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('ui/assets/brain_template.png', 'ui/assets'),
    ('ui/assets/app_icon.icns', 'ui/assets'),
    ('brain_reference.png', '.'),
]
binaries = []
hiddenimports = ['PyQt6.QtSvg']
tmp_ret = collect_all('google.genai')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('youtube_transcript_api')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yt_dlp')
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
    excludes=[
        'PyQt6.QtQuick',
        'PyQt6.QtQml',
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtDesigner',
        'PyQt6.QtQuick3D',
        'PyQt6.QtQuickWidgets',
        'PyQt6.QtBluetooth',
        'PyQt6.QtSensors',
        'PyQt6.QtPositioning',
        'PyQt6.QtNfc',
        'PyQt6.QtWebSockets',
        'PyQt6.QtWebChannel',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtTextToSpeech',
        'PyQt6.QtSpatialAudio',
        'PyQt6.QtSerialPort',
        'PyQt6.QtStateMachine',
        'PyQt6.QtHelp',
        'PyQt6.QtDBus',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPrintSupport',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YouTubeRetention',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeRetention',
)
app = BUNDLE(
    coll,
    name='YouTubeRetention.app',
    icon='ui/assets/app_icon.icns',
    bundle_identifier='com.retainer.app',
    info_plist={
        'CFBundleName': 'Retainer',
        'CFBundleDisplayName': 'Retainer',
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Retainer uses AppleEvents to create rich notes in Apple Notes and display macOS notifications.',
    },
)
