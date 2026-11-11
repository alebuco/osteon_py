"""Segmentação de malhas por plano (com tampa sólida) e por laço.
Baseado em VTK; funções puras que recebem/retornam vtkPolyData."""
from __future__ import annotations
import numpy as np

try:
    import vtk
    from vtk.util import numpy_support as _nps
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


def plane_normal(axis: int, tilt_a_deg: float, tilt_b_deg: float) -> np.ndarray:
    """Normal do plano a partir de um eixo base (0=X,1=Y,2=Z) e duas inclinações."""
    base = np.eye(3)[axis].astype(float)
    ta = np.deg2rad(tilt_a_deg)
    tb = np.deg2rad(tilt_b_deg)

    def rot(ax, t):
        c, s = np.cos(t), np.sin(t)
        if ax == 0:
            return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        if ax == 1:
            return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    if axis == 0:
        R = rot(1, ta) @ rot(2, tb)
    elif axis == 1:
        R = rot(0, ta) @ rot(2, tb)
    else:
        R = rot(0, ta) @ rot(1, tb)
    n = R @ base
    n = n / (np.linalg.norm(n) or 1.0)
    return n


def plane_origin(bounds, normal, frac: float):
    """Ponto do plano: projeta os 8 cantos da bbox na normal e interpola por `frac`."""
    xs = [bounds[0], bounds[1]]; ys = [bounds[2], bounds[3]]; zs = [bounds[4], bounds[5]]
    corners = np.array([[x, y, z] for x in xs for y in ys for z in zs], float)
    d = corners @ np.asarray(normal, float)
    lo, hi = float(d.min()), float(d.max())
    dd = lo + frac * (hi - lo)
    c = corners.mean(axis=0)
    # ponto no plano mais próximo do centro
    k = dd - float(np.dot(c, normal))
    return (c + k * np.asarray(normal, float)).tolist()


def _triangulate(poly):
    tf = vtk.vtkTriangleFilter()
    tf.SetInputData(poly)
    tf.Update()
    return tf.GetOutput()


def _plane(origin, normal):
    p = vtk.vtkPlane()
    p.SetOrigin(float(origin[0]), float(origin[1]), float(origin[2]))
    p.SetNormal(float(normal[0]), float(normal[1]), float(normal[2]))
    return p


def _clip_closed(poly, origin, normal):
    """Clipa uma superfície fechada por um plano, gerando a tampa (watertight)."""
    planes = vtk.vtkPlaneCollection()
    planes.AddItem(_plane(origin, normal))
    c = vtk.vtkClipClosedSurface()
    c.SetInputData(poly)
    c.SetClippingPlanes(planes)
    c.GenerateFacesOn()
    c.GenerateOutlineOff()
    c.Update()
    return c.GetOutput()


def cut_by_plane(poly, origin, normal, cap=True):
    """Divide `poly` em dois vtkPolyData pelos dois lados do plano.
    cap=True fecha a face do corte (fragmentos sólidos)."""
    if not _HAS_VTK:
        raise RuntimeError("VTK indisponível.")
    poly = _triangulate(poly)
    n = np.asarray(normal, float)
    if cap:
        a = _clip_closed(poly, origin, n)
        b = _clip_closed(poly, origin, -n)
        return a, b
    clip = vtk.vtkClipPolyData()
    clip.SetInputData(poly)
    clip.SetClipFunction(_plane(origin, n))
    clip.GenerateClippedOutputOn()
    clip.Update()
    return clip.GetOutput(), clip.GetClippedOutput()


def largest_region(poly):
    if not _HAS_VTK:
        raise RuntimeError("VTK indisponível.")
    conn = vtk.vtkPolyDataConnectivityFilter()
    conn.SetInputData(poly)
    conn.SetExtractionModeToLargestRegion()
    conn.Update()
    return conn.GetOutput()


# ---- laço (classificação de triângulos por polígono na tela) ---------------
def poly_points_tris(poly):
    """Retorna (points Nx3, tris Mx3) de um vtkPolyData triangulado."""
    poly = _triangulate(poly)
    pts = _nps.vtk_to_numpy(poly.GetPoints().GetData()).astype(float)
    raw = _nps.vtk_to_numpy(poly.GetPolys().GetData())
    tris = raw.reshape(-1, 4)[:, 1:4].astype(np.int64)
    return pts, tris


def build_polydata(points, tris):
    """Constrói um vtkPolyData a partir de arrays numpy (points, tris)."""
    vpts = vtk.vtkPoints()
    vpts.SetData(_nps.numpy_to_vtk(np.ascontiguousarray(points, dtype=np.float32), deep=True))
    cells = np.empty((len(tris), 4), dtype=np.int64)
    cells[:, 0] = 3
    cells[:, 1:] = tris
    ca = vtk.vtkCellArray()
    ca.SetData(3, _nps.numpy_to_vtkIdTypeArray(cells.ravel(), deep=True))
    pd = vtk.vtkPolyData()
    pd.SetPoints(vpts)
    pd.SetPolys(ca)
    return pd


def split_by_mask(poly, keep_mask):
    """Divide `poly` em (dentro, fora) por uma máscara booleana de triângulos."""
    pts, tris = poly_points_tris(poly)
    keep = np.asarray(keep_mask, bool)
    return build_polydata(pts, tris[keep]), build_polydata(pts, tris[~keep])
