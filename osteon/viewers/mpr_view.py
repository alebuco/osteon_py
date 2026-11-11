"""MPR — reconstrução multiplanar (axial, coronal, sagital) com cursor
sincronizado e janelamento. Qt puro (numpy -> QImage), sem VTK.

Volume: data[z, y, x]; espaçamento (sx, sy, sz) em mm."""
from __future__ import annotations
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class _Pane(QtWidgets.QLabel):
    """Um corte (axial/coronal/sagital). Emite (plane, a, b) ao clicar."""
    clicked = QtCore.Signal(str, int, int)   # plane, col_idx, row_idx (voxels)
    scrolled = QtCore.Signal(str, int)        # plane, delta
    wl = QtCore.Signal(float, float)          # center, width (arrasto dir.)

    def __init__(self, plane, title):
        super().__init__()
        self.plane = plane
        self.title = title
        self.setMinimumSize(240, 240)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("background:#05080c;color:#789;")
        self.setMouseTracking(True)
        self._rect = (0, 0, 1, 1)   # x0,y0,w,h do pixmap desenhado
        self._native = (1, 1)       # cols, rows nativos
        self._drag_wl = None
        self._c = 0.0
        self._w = 1.0

    def set_draw(self, rect, native):
        self._rect, self._native = rect, native

    def _to_voxel(self, pos):
        x0, y0, w, h = self._rect
        cols, rows = self._native
        u = (pos.x() - x0) / max(1, w)
        v = (pos.y() - y0) / max(1, h)
        if not (0 <= u <= 1 and 0 <= v <= 1):
            return None
        return int(u * (cols - 1)), int(v * (rows - 1))

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            vx = self._to_voxel(e.position())
            if vx:
                self.clicked.emit(self.plane, vx[0], vx[1])
        elif e.button() == QtCore.Qt.RightButton:
            self._drag_wl = (e.position().x(), e.position().y(), self._w, self._c)

    def mouseMoveEvent(self, e):
        if self._drag_wl is not None:
            x0, y0, w0, c0 = self._drag_wl
            self._w = max(1.0, w0 + (e.position().x() - x0) * 4.0)
            self._c = c0 + (e.position().y() - y0) * 4.0
            self.wl.emit(self._c, self._w)
        elif e.buttons() & QtCore.Qt.LeftButton:
            vx = self._to_voxel(e.position())
            if vx:
                self.clicked.emit(self.plane, vx[0], vx[1])

    def mouseReleaseEvent(self, _e):
        self._drag_wl = None

    def wheelEvent(self, e):
        self.scrolled.emit(self.plane, 1 if e.angleDelta().y() < 0 else -1)


class MPRView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vol = None
        self.center = 400.0
        self.width = 1800.0
        self.ix = self.iy = self.iz = 0

        self.panes = {
            'ax': _Pane('ax', 'AXIAL'),
            'co': _Pane('co', 'CORONAL'),
            'sa': _Pane('sa', 'SAGITAL'),
        }
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(2)
        grid.addWidget(self._wrap(self.panes['ax']), 0, 0)
        grid.addWidget(self._wrap(self.panes['co']), 0, 1)
        grid.addWidget(self._wrap(self.panes['sa']), 1, 0)
        self.info = QtWidgets.QLabel("MPR — clique para mover o cursor; scroll troca o corte; botão direito ajusta janela.")
        self.info.setWordWrap(True); self.info.setAlignment(QtCore.Qt.AlignCenter)
        self.info.setStyleSheet("color:#9bb;background:#0a0e13;border-radius:8px;")
        grid.addWidget(self.info, 1, 1)

        for p in self.panes.values():
            p.clicked.connect(self._on_click)
            p.scrolled.connect(self._on_scroll)
            p.wl.connect(self._on_wl)

    def _wrap(self, pane):
        box = QtWidgets.QVBoxLayout()
        lab = QtWidgets.QLabel(pane.title); lab.setStyleSheet("color:#9bd;padding:2px 6px;")
        w = QtWidgets.QWidget(); w.setLayout(box)
        box.setContentsMargins(0, 0, 0, 0); box.setSpacing(0)
        box.addWidget(lab); box.addWidget(pane, 1)
        return w

    def set_volume(self, vol):
        self.vol = vol
        if vol is None:
            return
        nz, ny, nx = vol.data.shape
        self.ix, self.iy, self.iz = nx // 2, ny // 2, nz // 2
        self.render_all()

    def _on_click(self, plane, a, b):
        if plane == 'ax':   # a=x, b=y
            self.ix, self.iy = a, b
        elif plane == 'co':  # a=x, b=z
            self.ix, self.iz = a, b
        else:                # sa: a=y, b=z
            self.iy, self.iz = a, b
        self.render_all()

    def _on_scroll(self, plane, delta):
        if self.vol is None:
            return
        nz, ny, nx = self.vol.data.shape
        if plane == 'ax':
            self.iz = int(np.clip(self.iz + delta, 0, nz - 1))
        elif plane == 'co':
            self.iy = int(np.clip(self.iy + delta, 0, ny - 1))
        else:
            self.ix = int(np.clip(self.ix + delta, 0, nx - 1))
        self.render_all()

    def _on_wl(self, c, w):
        self.center, self.width = c, w
        for p in self.panes.values():
            p._c, p._w = c, w
        self.render_all()

    def resizeEvent(self, e):
        self.render_all()
        super().resizeEvent(e)

    def _slice(self, plane):
        d = self.vol.data
        if plane == 'ax':
            return d[self.iz], (self.ix, self.iy)          # (cols=x, rows=y)
        if plane == 'co':
            return d[:, self.iy, :], (self.ix, self.iz)     # (cols=x, rows=z)
        return d[:, :, self.ix], (self.iy, self.iz)         # (cols=y, rows=z)

    def _phys(self, plane):
        sx, sy, sz = self.vol.spacing
        return {'ax': (sx, sy), 'co': (sx, sz), 'sa': (sy, sz)}[plane]

    def render_all(self):
        if self.vol is None:
            return
        lo = self.center - self.width / 2.0
        for key, pane in self.panes.items():
            sl, (ca, cb) = self._slice(key)
            sl = sl.astype(np.float32)
            g = np.clip((sl - lo) / max(1.0, self.width), 0.0, 1.0)
            img8 = np.ascontiguousarray((g * 255).astype(np.uint8))
            rows, cols = img8.shape
            qimg = QtGui.QImage(img8.data, cols, rows, cols, QtGui.QImage.Format_Grayscale8)

            # proporção física
            px, py = self._phys(key)
            phys_w, phys_h = cols * px, rows * py
            avail = pane.size()
            scale = min(avail.width() / max(1e-3, phys_w), avail.height() / max(1e-3, phys_h))
            draw_w = max(1, int(phys_w * scale)); draw_h = max(1, int(phys_h * scale))

            pix = QtGui.QPixmap.fromImage(qimg).scaled(
                draw_w, draw_h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)

            # cursor
            canvas = QtGui.QPixmap(avail); canvas.fill(QtGui.QColor(5, 8, 12))
            p = QtGui.QPainter(canvas)
            x0 = (avail.width() - draw_w) // 2; y0 = (avail.height() - draw_h) // 2
            p.drawPixmap(x0, y0, pix)
            p.setPen(QtGui.QPen(QtGui.QColor(107, 214, 255, 180), 1))
            cx = x0 + int(ca / max(1, cols - 1) * draw_w)
            cy = y0 + int(cb / max(1, rows - 1) * draw_h)
            p.drawLine(cx, y0, cx, y0 + draw_h)
            p.drawLine(x0, cy, x0 + draw_w, cy)
            p.end()
            pane.setPixmap(canvas)
            pane.set_draw((x0, y0, draw_w, draw_h), (cols, rows))
        self.info.setText(f"x {self.ix}  ·  y {self.iy}  ·  z {self.iz}\n"
                          f"C {int(self.center)} / L {int(self.width)} HU")
