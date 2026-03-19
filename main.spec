# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

python_home = r'C:\Users\CristopherMoralesRod\AppData\Local\Programs\Python\Python313'
user_venv   = r'C:\Users\CristopherMoralesRod\PycharmProjects\RxScrapper\.venv'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (os.path.join(python_home, 'DLLs', '_tkinter.pyd'), '.'),
        (os.path.join(python_home, 'DLLs', 'tcl86t.dll'),   '.'),
        (os.path.join(python_home, 'DLLs', 'tk86t.dll'),    '.'),
        (os.path.join(python_home, 'python313.dll'),         '.'),
        # ✅ img se movió a datas, no va aquí
    ],
    datas=[
        (os.path.join(user_venv,   'Lib', 'site-packages', 'customtkinter'), 'customtkinter'),
        (os.path.join(python_home, 'Lib', 'tkinter'),    'tkinter'),
        (os.path.join(python_home, 'tcl', 'tcl8.6'), '_tcl_data'),
        (os.path.join(python_home, 'tcl', 'tk8.6'),  '_tk_data'),
        ('ffmpeg', 'ffmpeg'),
        ('img', 'img'),   # ✅ acá va la carpeta de imágenes
    ],
    hiddenimports=['tkinter', '_tkinter', 'tkinter.ttk', 'paramiko', 'paramiko.transport'],
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
    [],
    exclude_binaries=True,
    name='RxScrapper',
    icon='img/icono.ico',   # ✅ .ico en lugar de .png
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # ✅ False reduce falsos positivos en antivirus
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,              # ✅ consistente con el exe
    upx_exclude=[],
    name='RxScrapper_Pro',
)