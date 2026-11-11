"""Registro/sobreposição de malhas: landmarks (vtkLandmarkTransform),
refino ICP (vtkIterativeClosestPointTransform), mapa de desvio (distância
ponto-superfície), e I/O de STL/JSON."""
from __future__ import annotations
import json
import numpy as np

try:
    import vtk
    from vtk.util import numpy_support as _nps
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


# ---- conversões matriz ----------------------------------------------------
def mat_to_np(m) -> np.ndarray:
    return np.array([[m.GetElement(i, j) for j in range(4)] for i in range(4)], float)


def np_to_transform(a) -> "vtk.vtkTransform":
    m = vtk.vtkMatrix4x4()
    for i in range(4):
        for j in range(4):
            m.SetElement(i, j, float(a[i][j]))
    t = vtk.vtkTransform()
    t.SetMatrix(m)
    return t


def identity() -> np.ndarray:
    return np.eye(4)


# ---- STL ------------------------------------------------------------------
def read_stl(path):
    r = vtk.vtkSTLReader()
    r.SetFileName(path)
    r.Update()
    tf = vtk.vtkTriangleFilter()
    tf.SetInputData(r.GetOutput())
    tf.Update()
    return tf.GetOutput()


def apply_transform(poly, transform):
    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetTransform(transform)
    tf.SetInputData(poly)
    tf.Update()
    return tf.GetOutput()


def apply_matrix(poly, a):
    return apply_transform(poly, np_to_transform(a))


# ---- registro -------------------------------------------------------------
def _points(src):
    p = vtk.vtkPoints()
    for q in src:
        p.InsertNextPoint(float(q[0]), float(q[1]), float(q[2]))
    return p


def landmark_register(src_pts, dst_pts, scale=False):
    """Alinha src->dst por pontos correspondentes. Retorna (matriz 4x4, rms_mm)."""
    lm = vtk.vtkLandmarkTransform()
    lm.SetSourceLandmarks(_points(src_pts))
    lm.SetTargetLandmarks(_points(dst_pts))
    if scale:
        lm.SetModeToSimilarity()
    else:
        lm.SetModeToRigidBody()
    lm.Update()
    A = mat_to_np(lm.GetMatrix())
    src = np.asarray(src_pts, float)
    dst = np.asarray(dst_pts, float)
    th = (A[:3, :3] @ src.T).T + A[:3, 3]
    rms = float(np.sqrt(np.mean(np.sum((th - dst) ** 2, axis=1))))
    return A, rms


def icp_register(src_poly, dst_poly, scale=False, iters=50):
    """Refina alinhamento src->dst por ICP. Retorna (matriz 4x4, dist_media_mm)."""
    icp = vtk.vtkIterativeClosestPointTransform()
    icp.SetSource(src_poly)
    icp.SetTarget(dst_poly)
    if scale:
        icp.GetLandmarkTransform().SetModeToSimilarity()
    else:
        icp.GetLandmarkTransform().SetModeToRigidBody()
    icp.SetMaximumNumberOfIterations(int(iters))
    icp.SetMaximumNumberOfLandmarks(2000)
    icp.StartByMatchingCentroidsOff()
    icp.Modified()
    icp.Update()
    return mat_to_np(icp.GetMatrix()), float(icp.GetMeanDistance())


# ---- desvio ---------------------------------------------------------------
def deviation(imp_poly_world, anat_poly, scale_mm):
    """Colore `imp_poly_world` (já transformado) pela distância à superfície
    anatômica. Retorna (poly_colorido, mean, max, dists)."""
    dist = vtk.vtkImplicitPolyDataDistance()
    dist.SetInput(anat_poly)
    pts = _nps.vtk_to_numpy(imp_poly_world.GetPoints().GetData())
    d = np.empty(len(pts), float)
    for i, p in enumerate(pts):
        d[i] = abs(dist.EvaluateFunction(float(p[0]), float(p[1]), float(p[2])))
    arr = _nps.numpy_to_vtk(np.ascontiguousarray(d, np.float32), deep=True)
    arr.SetName("desvio_mm")
    out = vtk.vtkPolyData()
    out.DeepCopy(imp_poly_world)
    out.GetPointData().SetScalars(arr)
    return out, float(d.mean()), float(d.max()), d


def jet_lut(scale_mm):
    lut = vtk.vtkLookupTable()
    lut.SetTableRange(0.0, float(scale_mm))
    lut.SetHueRange(0.667, 0.0)   # azul -> vermelho
    lut.SetSaturationRange(1.0, 1.0)
    lut.SetValueRange(1.0, 1.0)
    lut.Build()
    return lut


# ---- JSON -----------------------------------------------------------------
def save_json(path, anat_lm, imp_lm, matrix, manual, scale):
    data = {
        "version": 1,
        "anat_landmarks": [list(map(float, p)) for p in anat_lm],
        "imp_landmarks": [list(map(float, p)) for p in imp_lm],
        "treg": np.asarray(matrix, float).tolist(),
        "manual": manual,
        "scale": bool(scale),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d
