# -*- mode: python ; coding: utf-8 -*-
import os


bundle_version = os.environ.get("VOICE_ASSISTANT_BUNDLE_VERSION", "2.0.1")
build_version = os.environ.get("VOICE_ASSISTANT_BUILD_VERSION", "20103")

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("templates", "templates"),
        ("assets", "assets"),
    ],
    hiddenimports=[
        "engineio.async_drivers.threading",
        "socketio.client",
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
    name="VoiceInputAssistant",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VoiceInputAssistant",
)

app = BUNDLE(
    coll,
    name="语音输入助手.app",
    icon="build/macos/AppIcon.icns",
    bundle_identifier="com.fanke.voiceinputassistant",
    info_plist={
        "CFBundleName": "语音输入助手",
        "CFBundleDisplayName": "语音输入助手",
        "CFBundleShortVersionString": bundle_version,
        "CFBundleVersion": build_version,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription": "用于让同一 Wi-Fi 下的手机访问语音输入助手并传输文字、图片、视频和文件。",
    },
)
