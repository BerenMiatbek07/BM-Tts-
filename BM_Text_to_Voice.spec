# -*- mode: python ; coding: utf-8 -*-

import shutil

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

kivy_data = collect_data_files('kivy')
omnivoice_data = collect_data_files('omnivoice', excludes=['cli/**', 'eval/**'])
curl_cffi_data = collect_data_files('curl_cffi')
curl_cffi_binaries = collect_dynamic_libs('curl_cffi')
package_metadata = []
for package_name in ('omnivoice', 'transformers', 'huggingface-hub', 'accelerate'):
    package_metadata += copy_metadata(package_name)
ffmpeg_path = shutil.which('ffmpeg')
extra_binaries = [(ffmpeg_path, '.')] if ffmpeg_path else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=extra_binaries + curl_cffi_binaries,
    datas=[
        ('assets', 'assets'),
        ('OPENVOICE_LICENSE.txt', '.'),
        ('THIRD_PARTY_NOTICES.md', '.'),
        ('OMNIVOICE_PERSONAL_NOTICE.txt', '.'),
    ] + kivy_data + omnivoice_data + curl_cffi_data + package_metadata,
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'requests',
        'urllib3',
        'websocket',
        'curl_cffi',
        'curl_cffi.requests',
        'certifi',
        'torch',
        'librosa',
        'sounddevice',
        'soundfile',
        'omnivoice',
        'omnivoice.models.omnivoice',
        'omnivoice.utils.audio',
        'omnivoice.utils.duration',
        'omnivoice.utils.lang_map',
        'omnivoice.utils.text',
        'omnivoice.utils.voice_design',
        'huggingface_hub',
        'transformers',
        'accelerate',
        'torchaudio',
        'tensorboardX',
        'webdataset',
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
    a.binaries,
    a.datas,
    [],
    name='BM_Text_to_Voice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
