# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для сборки «ТехАрхив» в один исполняемый файл.

Сборка:  pyinstaller techarchive.spec
Результат: dist/ТехАрхив.exe

Внешние требования у конечного пользователя (не упаковываются в exe):
  - запущенный PostgreSQL (docker-compose up -d) на порту 5439;
  - установленный Tesseract OCR (C:\\Program Files\\Tesseract-OCR\\tesseract.exe).
См. README.md.
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/app_icon.ico', 'assets'),
        ('assets/app_icon.png', 'assets'),
    ],
    hiddenimports=[
        'psycopg2',
        'PyQt6.QtPdf',
        'PyQt6.QtPdfWidgets',
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
    name='ТехАрхив',
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
    icon='assets/app_icon.ico',
)
