# -*- mode: python ; coding: utf-8 -*-
from importlib.util import find_spec

hidden = ['app.trajectory_persistent_worker']
if find_spec('_pitchtracker_native') is not None:
    hidden.append('_pitchtracker_native')
a = Analysis(
    ['numerical_worker_launcher.py'], pathex=[], binaries=[], datas=[],
    hiddenimports=hidden,
    excludes=['PySide6', 'cv2', 'pytest', '_pytest', 'matplotlib', 'sklearn'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='PitchTrackerNumericalWorker', console=True, upx=False,
)
