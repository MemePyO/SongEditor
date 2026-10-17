# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

datas = [
    ('Template.pro', '.'),
    ('GroupNames.txt', '.'),
    ('autocorrect_words.txt', '.'),
    ('dictionaries', 'dictionaries'),
] + collect_data_files('tkinterdnd2') \
  + collect_data_files('spellchecker', includes=['resources/*.json.gz']) \
  + collect_data_files('pymupdf', excludes=['mupdf-devel/**'])

binaries = collect_dynamic_libs('pymupdf')

a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'ttkbootstrap',
        'spellchecker',
        'tkinterdnd2',
        'fitz',
        'pymupdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas',
        'pyarrow',
        'numpy',
        'matplotlib',
        'scipy',
        'streamlit',
        'flask',
        'IPython',
        'pytest',
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
    [],
    exclude_binaries=True,
    name='ProPresenter7SongEditor',
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
    icon=os.path.join('assets', 'app.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ProPresenter7SongEditor',
)
