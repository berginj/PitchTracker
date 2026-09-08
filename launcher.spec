# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PitchTracker launcher.

Optimized for minimal bundle size by excluding unused modules.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# Data files to include.
#
# Keep runtime-local state out of the frozen app. The ignored files under
# configs/ such as roi.json, pitchers.json, app_state.json, locations/, and
# .first_run_done are generated on an operator machine and must not ship in the
# installer.
datas = [
    ('configs/default.yaml', 'configs'),
    ('configs/snapdragon.yaml', 'configs'),
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
    strip=False,          # Windows ships native binaries without external strip.
    upx=True,             # Compress with UPX
    console=False,        # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

# Collection
worker_analysis = Analysis(
    ['worker_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + [
        'app.camera_probe_worker',
        'app.services.capture.setup_worker_main',
        'app.services.tooling.worker_main',
        'app.trajectory_worker',
    ],
    # Tooling imports plotting/report dependencies; they must remain available
    # even when the GUI does not use them directly.
    excludes=['pytest', '_pytest', 'IPython', 'notebook', 'jupyterlab'],
    noarchive=False,
)
worker_pyz = PYZ(worker_analysis.pure)
worker_exe = EXE(
    worker_pyz, worker_analysis.scripts, [], exclude_binaries=True,
    name='PitchTrackerWorker', console=True, upx=False,
)
coll = COLLECT(
    exe,
    worker_exe,
    worker_analysis.binaries,
    worker_analysis.datas,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PitchTracker'
)
