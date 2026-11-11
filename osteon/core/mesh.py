"""Geração de malha (isosuperfície) e exportação STL.

Caminho principal usa VTK (marching cubes 'flying edges', suavização Taubin,
decimação, maior componente, STL writer). Há também um caminho de reserva com
scikit-image + escritor STL em numpy, usado em testes/headless e caso o VTK
não esteja disponível.
"""
from __future__ import annotations
import numpy as np

try:
    import vtk
    from vtk.util import numpy_support as _nps
    _HAS_VTK = True
except Exception:
    vtk = None
    _HAS_VTK = False


# ----------------------------------------------------------------------------
# VTK
# ----------------------------------------------------------------------------
def build_vtk_image(vol):
    """Converte Volume -> vtkImageData (em HU), com espaçamento e origem."""
    if not _HAS_VTK:
        raise RuntimeError("VTK não está disponível.")
    nz, ny, nx = vol.data.shape
    img = vtk.vtkImageData()
    img.SetDimensions(nx, ny, nz)
    img.SetSpacing(float(vol.spacing[0]), float(vol.spacing[1]), float(vol.spacing[2]))
    img.SetOrigin(float(vol.origin[0]), float(vol.origin[1]), float(vol.origin[2]))
    flat = np.ascontiguousarray(vol.data).ravel()  # ordem C: x é o eixo mais rápido
    arr = _nps.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_SHORT)
    arr.SetName("HU")
    img.GetPointData().SetScalars(arr)
    return img


def generate_model(vol, hu=300.0, smooth_iters=10, decimate=0.0, keep_largest=False):
    """Gera vtkPolyData da isosuperfície no limiar `hu`.
    - smooth_iters: suavização Taubin (0 = sem).
    - decimate: fração 0..0.9 de redução de triângulos.
    - keep_largest: mantém só o maior componente conectado.
    """
    if not _HAS_VTK:
        raise RuntimeError("VTK não está disponível.")
    img = build_vtk_image(vol)

    surf = vtk.vtkFlyingEdges3D()
    surf.SetInputData(img)
    surf.SetValue(0, float(hu))
    surf.ComputeNormalsOn()
    out = surf

    if keep_largest:
        conn = vtk.vtkPolyDataConnectivityFilter()
        conn.SetInputConnection(out.GetOutputPort())
        conn.SetExtractionModeToLargestRegion()
        out = conn

    if decimate and decimate > 0:
        dec = vtk.vtkDecimatePro()
        dec.SetInputConnection(out.GetOutputPort())
        dec.SetTargetReduction(float(min(0.95, max(0.0, decimate))))
        dec.PreserveTopologyOn()
        out = dec

    if smooth_iters and smooth_iters > 0:
        smooth = vtk.vtkWindowedSincPolyDataFilter()  # Taubin
        smooth.SetInputConnection(out.GetOutputPort())
        smooth.SetNumberOfIterations(int(smooth_iters))
        smooth.SetPassBand(0.1)
        smooth.NonManifoldSmoothingOn()
        smooth.NormalizeCoordinatesOn()
        smooth.BoundarySmoothingOff()
        out = smooth

    norm = vtk.vtkPolyDataNormals()
    norm.SetInputConnection(out.GetOutputPort())
    norm.ConsistencyOn()
    norm.AutoOrientNormalsOn()
    norm.Update()
    return norm.GetOutput()


def write_stl(polydata, path, binary=True):
    if not _HAS_VTK:
        raise RuntimeError("VTK não está disponível.")
    w = vtk.vtkSTLWriter()
    w.SetFileName(path)
    w.SetInputData(polydata)
    w.SetFileType(vtk.VTK_BINARY if binary else vtk.VTK_ASCII)
    w.Write()


def mesh_stats(polydata):
    if not _HAS_VTK or polydata is None:
        return {}
    b = polydata.GetBounds()
    return {
        'triangles': int(polydata.GetNumberOfCells()),
        'points': int(polydata.GetNumberOfPoints()),
        'dim_mm': (b[1] - b[0], b[3] - b[2], b[5] - b[4]),
    }


# ----------------------------------------------------------------------------
# Reserva sem VTK (scikit-image + STL numpy) — usada em testes/headless
# ----------------------------------------------------------------------------
def isosurface_np(vol, hu=300.0, step=1):
    """Marching cubes via scikit-image. Retorna (verts_mm, faces)."""
    from skimage import measure
    data = vol.data
    if step > 1:
        data = data[::step, ::step, ::step]
    verts, faces, _n, _v = measure.marching_cubes(
        data.astype(np.float32), level=float(hu))
    sx, sy, sz = vol.spacing
    # verts vêm em (z, y, x) * step -> converte para mm (x, y, z)
    v = np.empty_like(verts)
    v[:, 0] = verts[:, 2] * sx * step
    v[:, 1] = verts[:, 1] * sy * step
    v[:, 2] = verts[:, 0] * sz * step
    return v, faces


def write_stl_np(verts, faces, path):
    """Escreve STL binário de (verts, faces) sem VTK."""
    import struct
    tris = verts[faces]  # (F, 3, 3)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    n = n / ln
    with open(path, 'wb') as f:
        f.write(b'\0' * 80)
        f.write(struct.pack('<I', len(faces)))
        for i in range(len(faces)):
            f.write(struct.pack('<3f', *n[i]))
            f.write(struct.pack('<3f', *a[i]))
            f.write(struct.pack('<3f', *b[i]))
            f.write(struct.pack('<3f', *c[i]))
            f.write(struct.pack('<H', 0))
