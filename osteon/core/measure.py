"""Medições geométricas de malhas (volume e área) via VTK."""
from __future__ import annotations

try:
    import vtk
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


def volume_area(poly):
    """Retorna (volume_mm3, area_mm2). Requer superfície triangulada e fechada
    para o volume ser confiável (fragmentos com tampa / modelo fechado)."""
    if not _HAS_VTK:
        raise RuntimeError("VTK indisponível.")
    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(poly)
    tri.Update()
    mp = vtk.vtkMassProperties()
    mp.SetInputData(tri.GetOutput())
    mp.Update()
    return float(mp.GetVolume()), float(mp.GetSurfaceArea())
