"""Visor 3D de segmentação: fragmentos (com cor/afastamento), plano de corte
e laço (polígono na tela) para separar regiões. VTK + sobreposição Qt."""
from __future__ import annotations
import numpy as np

import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor  # noqa: E402
import vtk  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from ..core import segment as seg  # noqa: E402

PALETTE = [(0.82, 0.82, 0.88), (1.0, 0.72, 0.30), (0.45, 0.85, 0.50),
           (0.60, 0.70, 1.0), (1.0, 0.50, 0.55), (0.90, 0.80, 0.40)]


class LassoOverlay(QtWidgets.QWidget):
    """Camada transparente para desenhar o laço com o mouse."""
    finished = QtCore.Signal(list)  # lista de (x, y) em coords lógicas do widget

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.active = False
        self.pts = []

    def set_active(self, on):
        self.active = on
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, not on)
        self.pts = []
        self.update()

    def mousePressEvent(self, e):
        if self.active:
            self.pts = [(e.position().x(), e.position().y())]

    def mouseMoveEvent(self, e):
        if self.active and self.pts:
            self.pts.append((e.position().x(), e.position().y()))
            self.update()

    def mouseReleaseEvent(self, e):
        if self.active and len(self.pts) >= 3:
            self.finished.emit(list(self.pts))
        self.pts = []
        self.update()

    def paintEvent(self, _e):
        if not self.active or len(self.pts) < 2:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(107, 214, 255), 2)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(107, 214, 255, 30))
        poly = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in self.pts])
        p.drawPolygon(poly)


class SegmentView(QtWidgets.QWidget):
    lasso_done = QtCore.Signal(list)  # repassa o polígono do laço

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.ren = vtk.vtkRenderer()
        self.ren.SetBackground(0.02, 0.03, 0.04)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        self.overlay = LassoOverlay(self)
        self.overlay.finished.connect(self.lasso_done)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.vtk_widget)

        self.frag_actors = []
        self.plane_actor = None
        self._started = False

    def resizeEvent(self, e):
        self.overlay.setGeometry(self.vtk_widget.geometry())
        super().resizeEvent(e)

    def start(self):
        if not self._started:
            self.iren.Initialize()
            self._started = True

    # -- fragmentos ---------------------------------------------------------
    def set_fragments(self, frags):
        for a in self.frag_actors:
            self.ren.RemoveActor(a)
        self.frag_actors = []
        for f in frags:
            if not f.get("visible", True):
                self.frag_actors.append(None)
                continue
            m = vtk.vtkPolyDataMapper()
            m.SetInputData(f["poly"])
            m.ScalarVisibilityOff()
            a = vtk.vtkActor()
            a.SetMapper(m)
            a.GetProperty().SetColor(*f["color"])
            a.GetProperty().SetInterpolationToPhong()
            self._apply_actor_transform(a, f.get("center"), f.get("move"))
            self.ren.AddActor(a)
            self.frag_actors.append(a)
        self.ren.ResetCamera()
        self.render()

    @staticmethod
    def _apply_actor_transform(a, center, mv):
        if center is not None:
            a.SetOrigin(float(center[0]), float(center[1]), float(center[2]))
        if mv:
            a.SetOrientation(float(mv.get("rx", 0)), float(mv.get("ry", 0)), float(mv.get("rz", 0)))
            a.SetPosition(float(mv.get("tx", 0)), float(mv.get("ty", 0)), float(mv.get("tz", 0)))

    def update_transform(self, i, center, mv):
        a = self.frag_actors[i] if i < len(self.frag_actors) else None
        if a is not None:
            self._apply_actor_transform(a, center, mv)
            self.render()

    # -- plano --------------------------------------------------------------
    def set_plane(self, origin, normal, size):
        if self.plane_actor is not None:
            self.ren.RemoveActor(self.plane_actor)
            self.plane_actor = None
        src = vtk.vtkPlaneSource()
        src.SetCenter(0, 0, 0)
        src.SetNormal(float(normal[0]), float(normal[1]), float(normal[2]))
        src.SetOrigin(-size, -size, 0)
        src.SetPoint1(size, -size, 0)
        src.SetPoint2(-size, size, 0)
        src.Update()
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(src.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(0.38, 0.78, 1.0)
        a.GetProperty().SetOpacity(0.26)
        a.SetPosition(float(origin[0]), float(origin[1]), float(origin[2]))
        self.ren.AddActor(a)
        self.plane_actor = a
        self.render()

    def hide_plane(self):
        if self.plane_actor is not None:
            self.ren.RemoveActor(self.plane_actor)
            self.plane_actor = None
            self.render()

    # -- laço ---------------------------------------------------------------
    def set_lasso(self, on):
        self.overlay.setGeometry(self.vtk_widget.geometry())
        self.overlay.raise_()
        self.overlay.set_active(on)

    def classify_lasso(self, poly, offset, pts_logical):
        """Retorna máscara booleana de triângulos cujo centroide cai dentro do laço."""
        p, tris = seg.poly_points_tris(poly)
        cent = p[tris].mean(axis=1) + np.asarray(offset, float)
        dpr = self.devicePixelRatioF()
        w, h = self.vtk_widget.GetRenderWindow().GetSize()
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToWorld()
        scr = np.empty((len(cent), 2), float)
        for i, c in enumerate(cent):
            coord.SetValue(float(c[0]), float(c[1]), float(c[2]))
            dx, dy = coord.GetComputedDisplayValue(self.ren)
            scr[i, 0] = dx            # pixels, origem inferior-esquerda (VTK)
            scr[i, 1] = h - dy        # converte para origem superior (Qt)
        poly_px = np.array([(x * dpr, y * dpr) for x, y in pts_logical], float)
        return _points_in_poly(scr, poly_px)

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()


def _points_in_poly(points, poly):
    """Ray casting vetorizado: máscara de quais `points` caem dentro de `poly`."""
    n = len(poly)
    inside = np.zeros(len(points), bool)
    x, y = points[:, 0], points[:, 1]
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        cond = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi)
        inside ^= cond
        j = i
    return inside
