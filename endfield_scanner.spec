# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['endfield_essence_scanner.py'],  # ← 실제 파이썬 파일명
    pathex=[],
    binaries=[],
    datas=[
        ('weapons_db.json', '.'),
        ('lock_template.png', '.'),
        ('lock_button_template.png', '.')
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'pynput.keyboard._win32',
        'pynput.mouse._win32'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'notebook',
        'IPython',
        'jupyter',
        'sphinx',
        'setuptools',
        'distutils'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],  # ✅ 비우기 (onedir 모드)
    exclude_binaries=True,  # ✅ 필수
    name='EndField_Auto_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # ✅ 속도 최적화
    console=False,  # False: 콘솔 숨김 / True: 디버깅용
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 아이콘 있으면: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EndField_Auto_Scanner'
)