"""Operações booleanas entre malhas (união, subtração, interseção) via VTK.
Requer malhas trianguladas e, de preferência, fechadas (use a tampa no corte)."""
from __future__ import annotations

try:
    import vtk
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


def _prep(poly):
    tri = vtk.vtkTriangleFilter(); tri.SetInputData(poly); tri.Update()
    clean = vtk.vtkCleanPolyData(); clean.SetInputConnection(tri.GetOutputPort()); clean.Update()
    return clean.GetOutput()


def boolean(op, poly_a, poly_b):
    """op: 'union' | 'difference' | 'intersection'. Retorna vtkPolyData."""
    if not _HAS_VTK:
        raise RuntimeError("VTK indisponível.")
    bf = vtk.vtkBooleanOperationPolyDataFilter()
    modes = {
        "union": bf.SetOperationToUnion,
        "difference": bf.SetOperationToDifference,
        "intersection": bf.SetOperationToIntersection,
    }
    modes[op]()
    bf.SetInputData(0, _prep(poly_a))
    bf.SetInputData(1, _prep(poly_b))
    bf.Update()
    out = vtk.vtkPolyData()
    out.DeepCopy(bf.GetOutput())
    return out
