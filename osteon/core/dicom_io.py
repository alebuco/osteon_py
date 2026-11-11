"""Leitura de série DICOM -> volume (numpy) com espaçamento, origem,
metadados do paciente e orientação. Sem dependências de GUI."""
from __future__ import annotations
from dataclasses import dataclass, field
import os
import glob
import numpy as np

try:
    import pydicom
except Exception:  # pydicom é dependência de runtime; ausente só impede carregar DICOM
    pydicom = None


@dataclass
class Volume:
    """Volume 3D em unidades Hounsfield (quando CT). Eixos: data[z, y, x]."""
    data: np.ndarray                       # int16, shape (nz, ny, nx)
    spacing: tuple[float, float, float]    # (sx, sy, sz) em mm  -> x, y, z
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    meta: dict = field(default_factory=dict)
    orient: dict | None = None             # {'x':'L','y':'P','z':'S','real':True}

    @property
    def shape_xyz(self) -> tuple[int, int, int]:
        nz, ny, nx = self.data.shape
        return nx, ny, nz

    @property
    def is3d(self) -> bool:
        return self.data.ndim == 3 and self.data.shape[0] >= 3


def _axis_label(v):
    """Rótulo anatômico (LPS) do eixo dado pelo vetor de cossenos."""
    ax, ay, az = abs(v[0]), abs(v[1]), abs(v[2])
    if ax >= ay and ax >= az:
        return 'L' if v[0] >= 0 else 'R'
    if ay >= az:
        return 'P' if v[1] >= 0 else 'A'
    return 'S' if v[2] >= 0 else 'I'


def _gather_files(path) -> list[str]:
    if isinstance(path, (list, tuple)):
        return [p for p in path if os.path.isfile(p)]
    if os.path.isfile(path):
        return [path]
    files = []
    for root, _dirs, names in os.walk(path):
        for n in names:
            if n.lower().endswith(('.dcm', '.ima')) or '.' not in n:
                files.append(os.path.join(root, n))
    if not files:  # fallback: tudo que o pydicom conseguir ler
        files = [p for p in glob.glob(os.path.join(path, '*')) if os.path.isfile(p)]
    return files


def load_series(path) -> Volume:
    """Carrega um diretório (ou lista de arquivos) DICOM como Volume.
    Levanta RuntimeError se o pydicom não estiver instalado ou nada for lido."""
    if pydicom is None:
        raise RuntimeError("pydicom não está instalado (pip install pydicom).")

    paths = _gather_files(path)
    slices = []
    for p in paths:
        try:
            ds = pydicom.dcmread(p, force=True)
            if 'PixelData' in ds:
                slices.append(ds)
        except Exception:
            continue
    if not slices:
        raise RuntimeError("Nenhuma imagem DICOM válida encontrada.")

    s0 = slices[0]
    iop = getattr(s0, 'ImageOrientationPatient', None)
    normal = None
    if iop is not None and len(iop) == 6:
        r = np.array(iop[:3], float)
        c = np.array(iop[3:], float)
        normal = np.cross(r, c)

    def sort_key(ds):
        ipp = getattr(ds, 'ImagePositionPatient', None)
        if ipp is not None and normal is not None:
            return float(np.dot(np.array(ipp, float), normal))
        return float(getattr(ds, 'InstanceNumber', 0) or 0)

    slices.sort(key=sort_key)

    rows = int(s0.Rows)
    cols = int(s0.Columns)
    nz = len(slices)
    vol = np.zeros((nz, rows, cols), dtype=np.int16)
    for i, ds in enumerate(slices):
        arr = ds.pixel_array.astype(np.float32)
        slope = float(getattr(ds, 'RescaleSlope', 1) or 1)
        icpt = float(getattr(ds, 'RescaleIntercept', 0) or 0)
        vol[i] = np.clip(arr * slope + icpt, -32768, 32767).astype(np.int16)

    # espaçamento
    px = getattr(s0, 'PixelSpacing', [1.0, 1.0])
    sy, sx = float(px[0]), float(px[1])  # PixelSpacing = [row(y), col(x)]
    sz = 1.0
    if nz > 1:
        ipp0 = getattr(slices[0], 'ImagePositionPatient', None)
        ipp1 = getattr(slices[1], 'ImagePositionPatient', None)
        if ipp0 is not None and ipp1 is not None:
            d = np.array(ipp1, float) - np.array(ipp0, float)
            sz = float(np.linalg.norm(d)) or float(getattr(s0, 'SliceThickness', 1) or 1)
        else:
            sz = float(getattr(s0, 'SliceThickness', 1) or 1)

    origin = (0.0, 0.0, 0.0)
    ipp0 = getattr(slices[0], 'ImagePositionPatient', None)
    if ipp0 is not None and len(ipp0) == 3:
        origin = (float(ipp0[0]), float(ipp0[1]), float(ipp0[2]))

    # orientação anatômica
    orient = None
    if iop is not None and len(iop) == 6:
        r = np.array(iop[:3], float)
        c = np.array(iop[3:], float)
        nn = np.cross(r, c)
        ipp_a = getattr(slices[0], 'ImagePositionPatient', None)
        ipp_b = getattr(slices[-1], 'ImagePositionPatient', None)
        if ipp_a is not None and ipp_b is not None and nz > 1:
            dd = np.array(ipp_b, float) - np.array(ipp_a, float)
            if np.dot(dd, nn) < 0:
                nn = -nn
        orient = {'x': _axis_label(r), 'y': _axis_label(c), 'z': _axis_label(nn), 'real': True}

    pn = str(getattr(s0, 'PatientName', '') or '').replace('^', ' ').strip()
    bd = str(getattr(s0, 'PatientBirthDate', '') or '')
    birth = f"{bd[0:4]}-{bd[4:6]}-{bd[6:8]}" if len(bd) == 8 else ''
    meta = {
        'patient': pn or '—',
        'patient_id': str(getattr(s0, 'PatientID', '') or ''),
        'birth': birth,
        'modality': str(getattr(s0, 'Modality', '') or '—'),
        'series': str(getattr(s0, 'SeriesDescription', '') or '—'),
    }

    return Volume(data=vol, spacing=(sx, sy, sz), origin=origin, meta=meta, orient=orient)


def demo_volume() -> Volume:
    """Fantoma sintético (sem DICOM) para abrir o app sem dados — um bloco
    ósseo com uma cavidade, em HU aproximadas."""
    nz, ny, nx = 72, 220, 220
    zz, yy, xx = np.mgrid[0:nz, 0:ny, 0:nx]
    cx, cy, cz = nx / 2, ny / 2, nz / 2
    r = np.sqrt(((xx - cx) / 90) ** 2 + ((yy - cy) / 90) ** 2 + ((zz - cz) / 30) ** 2)
    data = np.full((nz, ny, nx), -1000, np.int16)        # ar
    data[r < 1.0] = 300                                   # osso esponjoso
    data[(r < 1.0) & (r > 0.82)] = 1200                   # cortical
    inner = np.sqrt(((xx - cx) / 40) ** 2 + ((yy - cy) / 40) ** 2 + ((zz - cz) / 16) ** 2)
    data[inner < 1.0] = -200                              # cavidade medular
    return Volume(data=data, spacing=(0.6, 0.6, 0.8),
                  meta={'patient': '— (demonstração)', 'patient_id': '', 'birth': '',
                        'modality': 'CT', 'series': 'Fantoma'},
                  orient={'x': 'L', 'y': 'P', 'z': 'S', 'real': False})
