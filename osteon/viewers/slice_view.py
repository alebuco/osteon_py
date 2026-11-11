"""Visualizador 2D de cortes axiais (Qt puro, numpy -> QImage).
Janelamento (centro/largura) e navegação por corte."""
from __future__ import annotations
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class SliceView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vol = None
        self.index = 0
        self.center = 400.0
        self.width = 1800.0
        self._drag = None

        self.canvas = QtWidgets.QLabel("Abra uma série DICOM (Arquivo → Abrir) "
                                       "ou use o fantoma de demonstração.")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(320, 320)
        self.canvas.setStyleSheet("background:#05080c;color:#8aa;")
        self.canvas.setMouseTracking(True)
        self.canvas.installEventFilter(self)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.valueChanged.connect(self._on_slice)
        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet("color:#9bb;padding:2px 6px;")

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Corte"))
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.info)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas, 1)
        lay.addLayout(bar)

    def set_volume(self, vol):
        self.vol = vol
        if vol is None:
            return
        nz = vol.data.shape[0]
        self.index = nz // 2
        self.slider.setMaximum(max(0, nz - 1))
        self.slider.setValue(self.index)
        self.render()

    def _on_slice(self, v):
        self.index = int(v)
        self.render()

    def eventFilter(self, obj, ev):
        # Arrastar com botão direito ajusta janelamento (largura = X, centro = Y)
        if obj is self.canvas and self.vol is not None:
            if ev.type() == QtCore.QEvent.MouseButtonPress and ev.button() == QtCore.Qt.RightButton:
                self._drag = (ev.position().x(), ev.position().y(), self.width, self.center)
                return True
            if ev.type() == QtCore.QEvent.MouseMove and self._drag is not None:
                x0, y0, w0, c0 = self._drag
                self.width = max(1.0, w0 + (ev.position().x() - x0) * 4.0)
                self.center = c0 + (ev.position().y() - y0) * 4.0
                self.render()
                return True
            if ev.type() == QtCore.QEvent.MouseButtonRelease:
                self._drag = None
            if ev.type() == QtCore.QEvent.Wheel:
                step = 1 if ev.angleDelta().y() < 0 else -1
                self.slider.setValue(int(np.clip(self.index + step, 0, self.slider.maximum())))
                return True
        return super().eventFilter(obj, ev)

    def resizeEvent(self, ev):
        self.render()
        super().resizeEvent(ev)

    def render(self):
        if self.vol is None:
            return
        sl = self.vol.data[self.index].astype(np.float32)
        lo = self.center - self.width / 2.0
        g = np.clip((sl - lo) / max(1.0, self.width), 0.0, 1.0)
        img8 = (g * 255).astype(np.uint8)
        h, w = img8.shape
        buf = np.ascontiguousarray(img8)
        qimg = QtGui.QImage(buf.data, w, h, w, QtGui.QImage.Format_Grayscale8)
        pix = QtGui.QPixmap.fromImage(qimg).scaled(
            self.canvas.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.canvas.setPixmap(pix)
        self.info.setText(f"{self.index+1}/{self.vol.data.shape[0]}   "
                          f"C {int(self.center)} / L {int(self.width)} HU")
