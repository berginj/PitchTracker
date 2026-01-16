# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PitchTracker launcher.

Optimized for minimal bundle size by excluding unused modules.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# Data files to include
datas = [
    ('configs', 'configs'),
    ('assets', 'assets'),
    ('README_LAUNCHER.md', '.'),
    ('LICENSE', '.'),
]

# Hidden imports (needed but not auto-detected)
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'numpy',
    'cv2',
    'yaml',
    'loguru',
    'jsonschema',
]

# Modules to explicitly exclude (not used)
excludes = [
    # Testing frameworks
    'pytest',
    'unittest',
    '_pytest',

    # Data science (not used)
    'pandas',
    'matplotlib',
    'seaborn',
    'plotly',
    'bokeh',

    # Jupyter/IPython (not used)
    'jupyter',
    'jupyterlab',
    'IPython',
    'notebook',
    'ipykernel',
    'ipywidgets',

    # Alternative UI frameworks (using Qt)
    'tkinter',
    'tk',
    'Tkinter',
    'wx',
    'PyQt5',
    'PyQt6',

    # Documentation generators
    'sphinx',
    'docutils',

    # Unused stdlib modules
    'pydoc',
    'pdb',
    'doctest',
    'difflib',
    'inspect',
    'profile',
    'cProfile',
    'pstats',

    # Large optional dependencies
    'PIL.ImageQt',  # Qt image plugin (not needed)
]

# Analysis
a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate binaries
a.binaries = [x for x in a.binaries if not x[0].startswith('api-ms-win-')]

# PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PitchTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,           # Strip debug symbols (Linux/Mac)
    upx=True,             # Compress with UPX
    console=False,        # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

# Collection
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='PitchTracker'
)
