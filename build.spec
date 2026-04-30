# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Hypothesis Maker
# Build command: pyinstaller build.spec

import os, sys
block_cipher = None

# pymupdf package dir (contains .pyd and .dll)
import pymupdf as _pymupdf
PYMUPDF_DIR = os.path.dirname(_pymupdf.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (os.path.join(PYMUPDF_DIR, '_mupdf.pyd'),   'pymupdf'),
        (os.path.join(PYMUPDF_DIR, '_extra.pyd'),    'pymupdf'),
        (os.path.join(PYMUPDF_DIR, 'mupdfcpp64.dll'), 'pymupdf'),
    ],
    datas=[
        (PYMUPDF_DIR, 'pymupdf'),
    ],
    hiddenimports=[
        'pymupdf',
        'fitz',
        'anthropic',
        'anthropic._models',
        'anthropic.types',
        'openai',
        'openai.resources',
        'google.generativeai',
        'google.ai.generativelanguage_v1beta',
        'docx',
        'docx.oxml',
        'docx.oxml.ns',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.font',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'pandas', 'scipy', 'matplotlib',
        'PIL', 'Pillow', 'openpyxl',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HypothesisMaker',
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
    icon='icon.ico',
)
