# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['endfield_essence_scanner.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('attributes_db.json', '.'),
        ('weapons_db.json', '.'),
        ('lock_template.png', '.'),
        ('lock_button_template.png', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EndField_Auto_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # False로 바꾸면 콘솔창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 아이콘 파일 있으면 경로 지정
)
