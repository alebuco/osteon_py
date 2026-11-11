"""Visor de registro: duas janelas lado a lado (anatômico | importado) para
marcar pontos correspondentes, com sobreposição do importado transformado e
mapa de desvio na janela anatômica. VTK + PySide6."""
from __future__ import annotations

import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor  # noqa: E402
import vtk  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402


def render_histogram(dists, scale_mm, w, h, nbins=24):
    """Desenha o histograma do desvio (barras coloridas azul->vermelho) num QPixmap."""
    import numpy as np
    pix = QtGui.QPixmap(int(w), int(h)); pix.fill(QtGui.QColor(12, 17, 22))
    if dists is None or len(dists) == 0 or scale_mm <= 0:
        return pix
    edges = np.linspace(0, scale_mm, nbins + 1)
    counts, _ = np.histogram(np.clip(np.abs(dists), 0, scale_mm), bins=edges)
    mx = max(1, int(counts.max()))
    p = QtGui.QPainter(pix)
    bw = w / nbins
    for i, cnt in enumerate(counts):
        frac = (i + 0.5) / nbins
        col = QtGui.QColor.fromHsvF(max(0.0, 0.667 * (1 - frac)), 1.0, 1.0)
        bh = (cnt / mx) * (h - 2)
        p.fillRect(QtCore.QRectF(i * bw, h - bh, max(1.0, bw - 1), bh), col)
    p.end()
    return pix


class _Pane(QtWidgets.QWidget):
    picked = QtCore.Signal(tuple)

    def __init__(self, title):
        super().__init__()
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.ren = vtk.vtkRenderer()
        self.ren.SetBackground(0.02, 0.03, 0.04)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.vtk_widget.GetRenderWindow().GetInteractor()

        self.trackball = vtk.vtkInteractorStyleTrackballCamera()
        self.pickstyle = vtk.vtkInteractorStyleUser()
        self.pickstyle.AddObserver("LeftButtonPressEvent", self._on_pick)
        self.iren.SetInteractorStyle(self.trackball)

        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.001)

        self.base_actor = None
        self.overlay_actor = None
        self.markers = []
        self.pick_mode = False
        self._diag = 1.0
        self._started = False

        lab = QtWidgets.QLabel(title)
        lab.setStyleSheet("color:#9bd;padding:3px 6px;background:#0a0e13;")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(lab)
        lay.addWidget(self.vtk_widget, 1)

    def start(self):
        if not self._started:
            self.iren.Initialize()
            self._started = True

    def set_base(self, poly, color):
        if self.base_actor:
            self.ren.RemoveActor(self.base_actor)
        m = vtk.vtkPolyDataMapper(); m.SetInputData(poly); m.ScalarVisibilityOff()
        a = vtk.vtkActor(); a.SetMapper(m); a.GetProperty().SetColor(*color)
        a.GetProperty().SetInterpolationToPhong()
        self.ren.AddActor(a); self.base_actor = a
        b = poly.GetBounds()
        self._diag = max(1e-3, ((b[1]-b[0])**2+(b[3]-b[2])**2+(b[5]-b[4])**2) ** 0.5)
        self.ren.ResetCamera(); self.render()

    def set_overlay(self, poly, color, opacity, lut=None):
        if self.overlay_actor:
            self.ren.RemoveActor(self.overlay_actor); self.overlay_actor = None
        if poly is None:
            self.render(); return
        m = vtk.vtkPolyDataMapper(); m.SetInputData(poly)
        if lut is not None:
            m.SetLookupTable(lut); m.SetScalarRange(lut.GetTableRange()); m.ScalarVisibilityOn()
        else:
            m.ScalarVisibilityOff()
        a = vtk.vtkActor(); a.SetMapper(m); a.GetProperty().SetColor(*color)
        a.GetProperty().SetOpacity(opacity); a.GetProperty().SetInterpolationToPhong()
        self.ren.AddActor(a); self.overlay_actor = a; self.render()

    def set_markers(self, pts, color=(1.0, 0.85, 0.2)):
        for mk in self.markers:
            self.ren.RemoveActor(mk)
        self.markers = []
        r = max(0.4, self._diag * 0.012)
        for p in pts:
            s = vtk.vtkSphereSource(); s.SetCenter(*p); s.SetRadius(r); s.Update()
            m = vtk.vtkPolyDataMapper(); m.SetInputConnection(s.GetOutputPort())
            a = vtk.vtkActor(); a.SetMapper(m); a.GetProperty().SetColor(*color)
            self.ren.AddActor(a); self.markers.append(a)
        self.render()

    def set_pick_mode(self, on):
        self.pick_mode = on
        self.iren.SetInteractorStyle(self.pickstyle if on else self.trackball)

    def _on_pick(self, obj, _ev):
        if not self.pick_mode:
            return
        x, y = self.iren.GetEventPosition()
        if self.picker.Pick(x, y, 0, self.ren) and self.picker.GetCellId() >= 0:
            self.picked.emit(tuple(self.picker.GetPickPosition()))

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()


class RegisterView(QtWidgets.QWidget):
    landmarks_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left = _Pane("ANATÔMICO")      # referência
        self.right = _Pane("IMPORTADO")     # a alinhar
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.left, 1)
        lay.addWidget(self.right, 1)
        self.anat_lm = []
        self.imp_lm = []
        self.left.picked.connect(self._anat_pick)
        self.right.picked.connect(self._imp_pick)

    def start(self):
        self.left.start(); self.right.start()

    def set_meshes(self, anat_poly, imp_poly):
        self.left.set_base(anat_poly, (0.82, 0.82, 0.88))
        if imp_poly is not None:
            self.right.set_base(imp_poly, (1.0, 0.72, 0.30))
        self._refresh_markers()

    def set_overlay(self, imp_world_poly, color=(1.0, 0.72, 0.30), opacity=0.7, lut=None):
        self.left.set_overlay(imp_world_poly, color, opacity, lut)

    def set_pick_mode(self, on):
        self.left.set_pick_mode(on); self.right.set_pick_mode(on)

    def _anat_pick(self, p):
        self.anat_lm.append(list(p)); self._refresh_markers(); self.landmarks_changed.emit()

    def _imp_pick(self, p):
        self.imp_lm.append(list(p)); self._refresh_markers(); self.landmarks_changed.emit()

    def undo(self):
        if len(self.imp_lm) >= len(self.anat_lm) and self.imp_lm:
            self.imp_lm.pop()
        elif self.anat_lm:
            self.anat_lm.pop()
        self._refresh_markers(); self.landmarks_changed.emit()

    def clear(self):
        self.anat_lm = []; self.imp_lm = []
        self._refresh_markers(); self.landmarks_changed.emit()

    def _refresh_markers(self):
        self.left.set_markers(self.anat_lm, (0.42, 0.78, 1.0))
        self.right.set_markers(self.imp_lm, (1.0, 0.69, 0.3))
