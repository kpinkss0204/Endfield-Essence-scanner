# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['endfield_essence_scanner.py'],  # ← 실제 Python 파일명에 맞게 수정하세요
    pathex=[],
    binaries=[],
    datas=[
        ('weapons_db.json', '.'),           # 무기 데이터베이스
        ('lock_template.png', '.'),         # 잠금 아이콘 템플릿
        ('lock_button_template.png', '.')   # 잠금 버튼 템플릿
    ],
    hiddenimports=[
        'PIL._tkinter_finder',  # PIL/Pillow Tkinter 호환성
        'pynput.keyboard._win32',
        'pynput.mouse._win32'
    ],
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
    console=False,  # True: 콘솔창 표시 (디버깅용) / False: 콘솔창 숨김 (배포용)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 아이콘 파일 있으면: icon='icon.ico'
)