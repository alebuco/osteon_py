"""Salvar/abrir um 'caso' completo do Osteon num único arquivo .osteon (zip):
estado (JSON), volume (npz comprimido) e malhas (STL). Permite reabrir tudo
sem o DICOM original."""
from __future__ import annotations
import io
import json
import os
import tempfile
import zipfile
import numpy as np

from . import dicom_io

try:
    import vtk
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


def _poly_to_stl_bytes(poly) -> bytes:
    fd, p = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    try:
        w = vtk.vtkSTLWriter(); w.SetFileName(p); w.SetInputData(poly)
        w.SetFileType(vtk.VTK_BINARY); w.Write()
        with open(p, "rb") as f:
            return f.read()
    finally:
        os.remove(p)


def _stl_bytes_to_poly(data: bytes):
    fd, p = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    try:
        with open(p, "wb") as f:
            f.write(data)
        r = vtk.vtkSTLReader(); r.SetFileName(p); r.Update()
        out = vtk.vtkPolyData(); out.DeepCopy(r.GetOutput())
        return out
    finally:
        os.remove(p)


def save_case(path, state: dict, volume, meshes: dict):
    """state: dict serializável. volume: Volume ou None. meshes: {nome: vtkPolyData}."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("case.json", json.dumps(state, ensure_ascii=False, indent=1))
        if volume is not None:
            buf = io.BytesIO()
            np.savez_compressed(
                buf, data=volume.data,
                spacing=np.asarray(volume.spacing, float),
                origin=np.asarray(volume.origin, float),
                meta=json.dumps(volume.meta, ensure_ascii=False),
                orient=json.dumps(volume.orient or {}, ensure_ascii=False))
            z.writestr("volume.npz", buf.getvalue())
        if _HAS_VTK:
            for name, poly in (meshes or {}).items():
                if poly is not None:
                    z.writestr(f"meshes/{name}.stl", _poly_to_stl_bytes(poly))


def load_case(path):
    """Retorna (state, volume_or_None, meshes_dict)."""
    state, volume, meshes = {}, None, {}
    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        if "case.json" in names:
            state = json.loads(z.read("case.json").decode("utf-8"))
        if "volume.npz" in names:
            with np.load(io.BytesIO(z.read("volume.npz")), allow_pickle=False) as npz:
                meta = json.loads(str(npz["meta"]))
                orient = json.loads(str(npz["orient"])) or None
                volume = dicom_io.Volume(
                    data=npz["data"],
                    spacing=tuple(float(x) for x in npz["spacing"]),
                    origin=tuple(float(x) for x in npz["origin"]),
                    meta=meta, orient=orient)
        if _HAS_VTK:
            for n in names:
                if n.startswith("meshes/") and n.endswith(".stl"):
                    key = n[len("meshes/"):-4]
                    meshes[key] = _stl_bytes_to_poly(z.read(n))
    return state, volume, meshes
