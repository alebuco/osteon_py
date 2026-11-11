"""Cefalometria: projeção lateral (MIP ao longo de L-R) do volume e marcação
de pontos cefalométricos. Qt puro. Converte pontos para mm no plano A-P × S-I."""
from __future__ import annotations
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..core import cephalometry as ceph


class CephView(QtWidgets.QLabel):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vol = None
        self.proj = None          # (nz, ny) MIP
        self.center = 600.0
        self.width = 2500.0
        self.landmarks = {}        # sigla -> (col=y_idx, row=z_idx)
        self.current = "S"
        self._rect = (0, 0, 1, 1)
        self._native = (1, 1)
        self.setMinimumSize(360, 420)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("background:#05080c;color:#789;")

    def set_volume(self, vol):
        self.vol = vol
        if vol is None:
            self.proj = None
            return
        self.proj = vol.data.max(axis=2)      # projeção lateral (nz, ny)
        self.render_view()

    def set_current(self, sigla):
        self.current = sigla

    def clear_points(self):
        self.landmarks = {}
        self.render_view()
        self.changed.emit()

    def landmarks_mm(self):
        if self.vol is None:
            return {}
        _sx, sy, sz = self.vol.spacing
        out = {}
        for k, (col, row) in self.landmarks.items():
            out[k] = (col * sy, -(row * sz))   # (A-P, S-I) ; S-I para cima = +
        return out

    def _to_voxel(self, pos):
        x0, y0, w, h = self._rect
        cols, rows = self._native
        u = (pos.x() - x0) / max(1, w)
        v = (pos.y() - y0) / max(1, h)
        if not (0 <= u <= 1 and 0 <= v <= 1):
            return None
        return int(u * (cols - 1)), int(v * (rows - 1))

    def mousePressEvent(self, e):
        if self.proj is None:
            return
        if e.button() == QtCore.Qt.LeftButton:
            vx = self._to_voxel(e.position())
            if vx:
                self.landmarks[self.current] = vx
                self._advance()
                self.render_view()
                self.changed.emit()

    def _advance(self):
        order = [s for s, _ in ceph.POINTS]
        rest = [s for s in order if s not in self.landmarks]
        if rest:
            self.current = rest[0]

    def resizeEvent(self, e):
        self.render_view()
        super().resizeEvent(e)

    def render_view(self):
        if self.proj is None:
            return
        lo = self.center - self.width / 2.0
        g = np.clip((self.proj.astype(np.float32) - lo) / max(1.0, self.width), 0.0, 1.0)
        img8 = np.ascontiguousarray((g * 255).astype(np.uint8))
        rows, cols = img8.shape
        qimg = QtGui.QImage(img8.data, cols, rows, cols, QtGui.QImage.Format_Grayscale8)

        _sx, sy, sz = self.vol.spacing
        phys_w, phys_h = cols * sy, rows * sz
        avail = self.size()
        scale = min(avail.width() / max(1e-3, phys_w), avail.height() / max(1e-3, phys_h))
        draw_w = max(1, int(phys_w * scale)); draw_h = max(1, int(phys_h * scale))
        pix = QtGui.QPixmap.fromImage(qimg).scaled(
            draw_w, draw_h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)

        canvas = QtGui.QPixmap(avail); canvas.fill(QtGui.QColor(5, 8, 12))
        p = QtGui.QPainter(canvas)
        x0 = (avail.width() - draw_w) // 2; y0 = (avail.height() - draw_h) // 2
        p.drawPixmap(x0, y0, pix)
        p.setFont(QtGui.QFont("", 9, QtGui.QFont.Bold))
        for sig, (col, row) in self.landmarks.items():
            px = x0 + int(col / max(1, cols - 1) * draw_w)
            py = y0 + int(row / max(1, rows - 1) * draw_h)
            p.setPen(QtGui.QPen(QtGui.QColor(107, 214, 255), 2))
            p.setBrush(QtGui.QColor(107, 214, 255))
            p.drawEllipse(QtCore.QPoint(px, py), 4, 4)
            p.setPen(QtGui.QColor(191, 233, 255))
            p.drawText(px + 6, py - 4, sig)
        p.end()
        self.setPixmap(canvas)
        self._rect = (x0, y0, draw_w, draw_h)
        self._native = (cols, rows)
