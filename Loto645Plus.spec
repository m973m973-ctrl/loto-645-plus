# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['lotto645_app.py'],
    pathex=[],
    binaries=[],
    datas=[('analysis/archive_full.json', '.'), ('analysis/archive_6x45.json', '.'),
           ('analysis/archive_ruslotto.json', '.'), ('analysis/archive_rapido.json', '.'),
           ('analysis/archive_4x20.json', '.'), ('analysis/archive_gzhl.json', '.'),
           ('iconwork/loto.ico', '.')],
    hiddenimports=[],
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
    name='Loto645Plus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='iconwork/loto.ico',
)
