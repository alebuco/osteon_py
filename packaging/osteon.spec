# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec do Osteon Viewer. Rode a partir da raiz do projeto:
#   pyinstaller packaging/osteon.spec
import sys
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("vtkmodules", "pydicom", "skimage"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

hiddenimports += [
    "vtkmodules.all",
    "vtkmodules.util.numpy_support",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "scipy.spatial.transform._rotation_groups",
]

icon = "packaging/icon.ico" if sys.platform == "win32" else "packaging/icon.png"

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Osteon",
    console=False,
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Osteon")
