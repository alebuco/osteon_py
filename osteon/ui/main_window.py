"""Janela principal do Osteon: barra de modos (2D / 3D / Modelo), visor central
e painel lateral (paciente + modelo). Carrega DICOM ou o fantoma de demonstração."""
from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets

from ..core import dicom_io
from ..core import cephalometry as cephmod
from ..viewers.slice_view import SliceView
from ..viewers.mpr_view import MPRView
from ..viewers.ceph_view import CephView
from .patient_panel import PatientPanel

try:
    from ..viewers.volume_view import VolumeView
    from ..viewers.segment_view import SegmentView, PALETTE
    from ..viewers.register_view import RegisterView, render_histogram
    from ..core import mesh as meshmod
    from ..core import segment as segmod
    from ..core import register as regmod
    from ..core import report as reportmod
    import vtk as _vtk
    _HAS_VTK = True
except Exception as _e:  # VTK ausente -> 3D/Modelo/Segmentar/Registro desabilitados
    VolumeView = SegmentView = RegisterView = render_histogram = None
    meshmod = segmod = regmod = reportmod = _vtk = None
    PALETTE = [(0.82, 0.82, 0.88)]
    _HAS_VTK = False
    _VTK_ERR = str(_e)


class ModelPanel(QtWidgets.QGroupBox):
    generate = QtCore.Signal()
    export = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__("Modelo 3D (STL)", parent)
        self.hu = QtWidgets.QSpinBox(); self.hu.setRange(-500, 2500); self.hu.setValue(300); self.hu.setSingleStep(10)
        self.smooth = QtWidgets.QSpinBox(); self.smooth.setRange(0, 60); self.smooth.setValue(15)
        self.dec = QtWidgets.QDoubleSpinBox(); self.dec.setRange(0.0, 0.9); self.dec.setSingleStep(0.1); self.dec.setValue(0.0)
        self.largest = QtWidgets.QCheckBox("Manter maior componente")
        self.fmt = QtWidgets.QComboBox(); self.fmt.addItems(["Binário", "ASCII"])

        form = QtWidgets.QFormLayout()
        form.addRow("Limiar (HU)", self.hu)
        form.addRow("Suavização", self.smooth)
        form.addRow("Redução", self.dec)
        form.addRow("Formato", self.fmt)
        form.addRow(self.largest)

        b_gen = QtWidgets.QPushButton("Gerar malha")
        b_exp = QtWidgets.QPushButton("Exportar STL…")
        b_gen.clicked.connect(self.generate)
        b_exp.clicked.connect(self.export)
        self.stats = QtWidgets.QLabel("Gere a malha para ver os dados.")
        self.stats.setWordWrap(True); self.stats.setStyleSheet("color:#9bb;font-size:11px;")

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(b_gen)
        lay.addWidget(b_exp)
        lay.addWidget(self.stats)


class SegmentPanel(QtWidgets.QGroupBox):
    cut = QtCore.Signal()
    planeChanged = QtCore.Signal()
    moveChanged = QtCore.Signal()
    measure = QtCore.Signal()
    reset = QtCore.Signal()
    exportOne = QtCore.Signal()
    exportAll = QtCore.Signal()
    lassoToggled = QtCore.Signal(bool)
    fragSelected = QtCore.Signal()
    visChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__("Segmentar", parent)
        self.sel = QtWidgets.QComboBox(); self.sel.currentIndexChanged.connect(self.fragSelected)
        self.vis = QtWidgets.QCheckBox("Visível"); self.vis.setChecked(True); self.vis.toggled.connect(self.visChanged)
        self.axis = QtWidgets.QComboBox(); self.axis.addItems(["X (sagital)", "Y (coronal)", "Z (axial)"]); self.axis.setCurrentIndex(2)
        self.pos = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.pos.setRange(0, 100); self.pos.setValue(50)
        self.ta = QtWidgets.QSpinBox(); self.ta.setRange(-90, 90)
        self.tb = QtWidgets.QSpinBox(); self.tb.setRange(-90, 90)
        self.showPlane = QtWidgets.QCheckBox("Mostrar plano"); self.showPlane.setChecked(True)
        self.cap = QtWidgets.QCheckBox("Fechar face (sólido)"); self.cap.setChecked(True)
        self.mtx = self._mspin(-150, 150); self.mty = self._mspin(-150, 150); self.mtz = self._mspin(-150, 150)
        self.mrx = self._mspin(-180, 180); self.mry = self._mspin(-180, 180); self.mrz = self._mspin(-180, 180)
        self.info = QtWidgets.QLabel(""); self.info.setWordWrap(True); self.info.setStyleSheet("color:#9bb;font-size:11px;")

        for w in (self.axis,):
            w.currentIndexChanged.connect(self.planeChanged)
        for w in (self.pos,):
            w.valueChanged.connect(self.planeChanged)
        for w in (self.ta, self.tb):
            w.valueChanged.connect(self.planeChanged)
        self.showPlane.toggled.connect(self.planeChanged)
        for w in (self.mtx, self.mty, self.mtz, self.mrx, self.mry, self.mrz):
            w.valueChanged.connect(self.moveChanged)

        form = QtWidgets.QFormLayout()
        form.addRow("Fragmento", self.sel)
        form.addRow(self.vis)
        form.addRow("Eixo base", self.axis)
        form.addRow("Posição", self.pos)
        form.addRow("Inclinação A", self.ta)
        form.addRow("Inclinação B", self.tb)
        form.addRow(self.showPlane)
        form.addRow(self.cap)

        b_cut = QtWidgets.QPushButton("Cortar selecionado"); b_cut.clicked.connect(self.cut)
        self.b_lasso = QtWidgets.QPushButton("Traçado livre (laço)"); self.b_lasso.setCheckable(True)
        self.b_lasso.toggled.connect(self.lassoToggled)
        b_reset = QtWidgets.QPushButton("Resetar"); b_reset.clicked.connect(self.reset)
        b_meas = QtWidgets.QPushButton("Volume / área"); b_meas.clicked.connect(self.measure)
        b_e1 = QtWidgets.QPushButton("Exportar fragmento"); b_e1.clicked.connect(self.exportOne)
        b_e2 = QtWidgets.QPushButton("Exportar todos"); b_e2.clicked.connect(self.exportAll)

        repo = QtWidgets.QGroupBox("Reposicionar (osteotomia)")
        rf = QtWidgets.QFormLayout(repo)
        rf.addRow("Transl. X/Y/Z", self._row(self.mtx, self.mty, self.mtz))
        rf.addRow("Rot. X/Y/Z", self._row(self.mrx, self.mry, self.mrz))

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(b_cut)
        lay.addWidget(self.b_lasso)
        lay.addWidget(repo)
        lay.addWidget(b_meas)
        lay.addWidget(self.info)
        row = QtWidgets.QHBoxLayout(); row.addWidget(b_e1); row.addWidget(b_e2); lay.addLayout(row)
        lay.addWidget(b_reset)

    def _mspin(self, lo, hi):
        s = QtWidgets.QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(0.5); s.setValue(0); return s

    def _row(self, *ws):
        h = QtWidgets.QHBoxLayout()
        for w in ws:
            h.addWidget(w)
        return h

    def move(self):
        return dict(tx=self.mtx.value(), ty=self.mty.value(), tz=self.mtz.value(),
                    rx=self.mrx.value(), ry=self.mry.value(), rz=self.mrz.value())

    def set_move(self, mv):
        for key, w in (("tx", self.mtx), ("ty", self.mty), ("tz", self.mtz),
                       ("rx", self.mrx), ("ry", self.mry), ("rz", self.mrz)):
            w.blockSignals(True); w.setValue(float((mv or {}).get(key, 0))); w.blockSignals(False)


class CephPanel(QtWidgets.QGroupBox):
    pointSelected = QtCore.Signal(str)
    clearPts = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__("Cefalometria", parent)
        self.listw = QtWidgets.QListWidget()
        for sig, name in cephmod.POINTS:
            it = QtWidgets.QListWidgetItem(f"{sig} — {name}")
            it.setData(QtCore.Qt.UserRole, sig)
            self.listw.addItem(it)
        self.listw.setCurrentRow(0)
        self.listw.currentItemChanged.connect(
            lambda cur, _p: cur and self.pointSelected.emit(cur.data(QtCore.Qt.UserRole)))
        b_clear = QtWidgets.QPushButton("Limpar pontos"); b_clear.clicked.connect(self.clearPts)

        self.table = QtWidgets.QTableWidget(len(cephmod.ANALYSES), 3)
        self.table.setHorizontalHeaderLabels(["Análise", "Valor", "Normal"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for i, (name, _k, _a, _d) in enumerate(cephmod.ANALYSES):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem("—"))
            lo = cephmod.NORMS.get(name)
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{lo[0]:.0f} ± {lo[1]:.0f}" if lo else "—"))

        hint = QtWidgets.QLabel("Selecione o ponto e clique na imagem. A lista avança sozinha.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#8aa;font-size:11px;")

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(hint)
        lay.addWidget(self.listw)
        lay.addWidget(b_clear)
        lay.addWidget(self.table)

    def current_sig(self):
        it = self.listw.currentItem()
        return it.data(QtCore.Qt.UserRole) if it else cephmod.POINTS[0][0]

    def set_results(self, results):
        for i, (name, _k, _a, _d) in enumerate(cephmod.ANALYSES):
            v = results.get(name)
            cell = self.table.item(i, 1)
            if v is None or (isinstance(v, float) and v != v):
                cell.setText("—"); cell.setForeground(QtGui.QBrush(QtGui.QColor(150, 160, 170)))
                continue
            cell.setText(f"{v:.1f}°")
            lo = cephmod.NORMS.get(name)
            ok = lo and abs(v - lo[0]) <= lo[1]
            cell.setForeground(QtGui.QBrush(QtGui.QColor(120, 210, 140) if ok else QtGui.QColor(230, 170, 90)))


class RegisterPanel(QtWidgets.QGroupBox):
    importStl = QtCore.Signal()
    pickToggled = QtCore.Signal(bool)
    runLandmark = QtCore.Signal()
    runIcp = QtCore.Signal()
    devToggled = QtCore.Signal()
    manualChanged = QtCore.Signal()
    undo = QtCore.Signal()
    clear = QtCore.Signal()
    exportAligned = QtCore.Signal()
    saveJson = QtCore.Signal()
    loadJson = QtCore.Signal()
    reportPdf = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__("Registro / Sobreposição", parent)
        b_imp = QtWidgets.QPushButton("Importar STL…"); b_imp.clicked.connect(self.importStl)
        self.pick = QtWidgets.QPushButton("Marcar pontos"); self.pick.setCheckable(True)
        self.pick.toggled.connect(self.pickToggled)
        b_undo = QtWidgets.QPushButton("Desfazer"); b_undo.clicked.connect(self.undo)
        b_clr = QtWidgets.QPushButton("Limpar"); b_clr.clicked.connect(self.clear)
        self.scale = QtWidgets.QCheckBox("Permitir escala")
        b_lm = QtWidgets.QPushButton("Registrar (pontos)"); b_lm.clicked.connect(self.runLandmark)
        b_icp = QtWidgets.QPushButton("Refinar (ICP)"); b_icp.clicked.connect(self.runIcp)
        self.info = QtWidgets.QLabel(""); self.info.setWordWrap(True); self.info.setStyleSheet("color:#9bb;font-size:11px;")

        self.dev = QtWidgets.QCheckBox("Mapa de desvio"); self.dev.toggled.connect(self.devToggled)
        self.devScale = QtWidgets.QDoubleSpinBox(); self.devScale.setRange(0.5, 20); self.devScale.setValue(3.0); self.devScale.setSingleStep(0.5)
        self.devScale.valueChanged.connect(self.devToggled)

        self.tx = self._spin(-100, 100); self.ty = self._spin(-100, 100); self.tz = self._spin(-100, 100)
        self.rx = self._spin(-180, 180); self.ry = self._spin(-180, 180); self.rz = self._spin(-180, 180)
        self.sc = QtWidgets.QDoubleSpinBox(); self.sc.setRange(0.5, 2.0); self.sc.setSingleStep(0.01); self.sc.setValue(1.0); self.sc.valueChanged.connect(self.manualChanged)
        self.opa = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.opa.setRange(20, 100); self.opa.setValue(70); self.opa.valueChanged.connect(self.manualChanged)

        self.hist = QtWidgets.QLabel(); self.hist.setFixedHeight(60)
        self.hist.setStyleSheet("background:#0c1116;border-radius:6px;")
        b_exp = QtWidgets.QPushButton("Exportar alinhado…"); b_exp.clicked.connect(self.exportAligned)
        b_save = QtWidgets.QPushButton("Salvar (.json)"); b_save.clicked.connect(self.saveJson)
        b_load = QtWidgets.QPushButton("Carregar"); b_load.clicked.connect(self.loadJson)
        b_pdf = QtWidgets.QPushButton("Relatório PDF…"); b_pdf.clicked.connect(self.reportPdf)

        g = QtWidgets.QFormLayout()
        g.addRow("Transl. X/Y/Z", self._row(self.tx, self.ty, self.tz))
        g.addRow("Rot. X/Y/Z", self._row(self.rx, self.ry, self.rz))
        g.addRow("Escala", self.sc)
        g.addRow("Opacidade", self.opa)
        g.addRow("Desvio (mm)", self.devScale)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(b_imp)
        lay.addWidget(self.pick)
        lay.addLayout(self._row(b_undo, b_clr))
        lay.addWidget(self.scale)
        lay.addLayout(self._row(b_lm, b_icp))
        lay.addWidget(self.dev)
        lay.addLayout(g)
        lay.addWidget(self.hist)
        lay.addWidget(self.info)
        lay.addLayout(self._row(b_exp,))
        lay.addLayout(self._row(b_save, b_load))
        lay.addWidget(b_pdf)

    def _spin(self, lo, hi):
        s = QtWidgets.QDoubleSpinBox(); s.setRange(lo, hi); s.setSingleStep(0.5)
        s.valueChanged.connect(self.manualChanged); return s

    def _row(self, *ws):
        h = QtWidgets.QHBoxLayout()
        for w in ws:
            h.addWidget(w)
        return h

    def manual(self):
        return dict(tx=self.tx.value(), ty=self.ty.value(), tz=self.tz.value(),
                    rx=self.rx.value(), ry=self.ry.value(), rz=self.rz.value(), sc=self.sc.value())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        from .. import __version__
        self.setWindowTitle(f"Osteon Viewer {__version__}")
        self.resize(1360, 860)
        self.vol = None
        self.mesh = None
        self.frags = []          # [{poly,color,offset,dir,name,visible,amt}]
        self.seg_sel = 0
        self.seg_bounds = None
        self.reg_imp = None      # vtkPolyData importado
        self.reg_treg = regmod.identity() if _HAS_VTK else None  # 4x4
        self.reg_stats = {}      # method/rms/icp/dev
        self.reg_dists = None    # última distribuição de desvio

        # visor central
        self.slice_view = SliceView()
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.slice_view)              # índice 0 = 2D
        self.mpr_view = MPRView()
        self.stack.addWidget(self.mpr_view)                # MPR (Qt puro)
        self.ceph_view = CephView()
        self.stack.addWidget(self.ceph_view)               # Cefalometria (Qt puro)
        if _HAS_VTK:
            self.volume_view = VolumeView()
            self.stack.addWidget(self.volume_view)         # índice 1 = 3D/Modelo
            self.segment_view = SegmentView()
            self.stack.addWidget(self.segment_view)        # índice 2 = Segmentar
            self.segment_view.lasso_done.connect(self.on_seg_lasso_done)
            self.register_view = RegisterView()
            self.stack.addWidget(self.register_view)       # índice 3 = Registro
            self.register_view.landmarks_changed.connect(self.on_reg_landmarks)
        self.setCentralWidget(self.stack)

        # painel lateral
        self.patient = PatientPanel()
        self.model_panel = ModelPanel()
        self.model_panel.generate.connect(self.on_generate)
        self.model_panel.export.connect(self.on_export)
        self.segment_panel = SegmentPanel()
        self._wire_segment_panel()
        self.segment_panel.setVisible(False)
        self.register_panel = RegisterPanel()
        self._wire_register_panel()
        self.register_panel.setVisible(False)
        self.ceph_panel = CephPanel()
        self.ceph_panel.pointSelected.connect(self.ceph_view.set_current)
        self.ceph_panel.clearPts.connect(self.ceph_view.clear_points)
        self.ceph_view.changed.connect(self.update_ceph_results)
        self.ceph_panel.setVisible(False)
        side = QtWidgets.QWidget(); sl = QtWidgets.QVBoxLayout(side)
        sl.addWidget(self.patient)
        sl.addWidget(self.model_panel)
        sl.addWidget(self.segment_panel)
        sl.addWidget(self.register_panel)
        sl.addWidget(self.ceph_panel)
        sl.addStretch(1)
        dock = QtWidgets.QDockWidget("Painel", self)
        dock.setWidget(side)
        dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setMinimumWidth(300)

        self._build_toolbar()
        self._build_menu()
        self._apply_style()
        if not _HAS_VTK:
            self.statusBar().showMessage("VTK indisponível — 3D e Modelo desativados. " + _VTK_ERR)

    def _build_toolbar(self):
        tb = QtWidgets.QToolBar("Modos")
        tb.setOrientation(QtCore.Qt.Vertical)
        tb.setMovable(False)
        self.addToolBar(QtCore.Qt.LeftToolBarArea, tb)
        self.mode_group = QtGui.QActionGroup(self)
        for key, label in [("2d", "2D"), ("mpr", "MPR"), ("ceph", "Cefalo"), ("3d", "3D"), ("model", "Modelo"), ("segment", "Segmentar"), ("register", "Registro")]:
            act = QtGui.QAction(label, self, checkable=True)
            act.setData(key)
            act.triggered.connect(lambda _c, k=key: self.set_mode(k))
            if key in ("3d", "model", "segment", "register") and not _HAS_VTK:
                act.setEnabled(False)
            self.mode_group.addAction(act)
            tb.addAction(act)
        self.mode_group.actions()[0].setChecked(True)

    def _build_menu(self):
        m = self.menuBar().addMenu("Arquivo")
        a_open = QtGui.QAction("Abrir pasta DICOM…", self); a_open.triggered.connect(self.open_dicom)
        a_demo = QtGui.QAction("Abrir demonstração", self); a_demo.triggered.connect(self.open_demo)
        a_savec = QtGui.QAction("Salvar caso…", self); a_savec.triggered.connect(self.save_case)
        a_openc = QtGui.QAction("Abrir caso…", self); a_openc.triggered.connect(self.open_case)
        a_quit = QtGui.QAction("Sair", self); a_quit.triggered.connect(self.close)
        for a in (a_open, a_demo):
            m.addAction(a)
        m.addSeparator(); m.addAction(a_savec); m.addAction(a_openc)
        m.addSeparator(); m.addAction(a_quit)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow,QWidget{background:#0d1117;color:#cdd6e0;}
            QGroupBox{border:1px solid #223;border-radius:8px;margin-top:10px;padding:8px;}
            QGroupBox::title{subcontrol-origin:margin;left:8px;color:#9bd;}
            QPushButton{background:#1b2430;border:1px solid #2b3a4a;border-radius:6px;padding:6px;}
            QPushButton:hover{background:#243040;}
            QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{background:#111a22;border:1px solid #243;border-radius:5px;padding:4px;}
            QToolBar{background:#0a0e13;border:0;spacing:6px;padding:6px;}
            QToolButton{padding:8px 10px;border-radius:6px;}
            QToolButton:checked{background:#1f6feb;color:white;}
        """)

    # -- carga --------------------------------------------------------------
    def _set_volume(self, vol):
        self.vol = vol
        self.mesh = None
        self.slice_view.set_volume(vol)
        self.patient.set_from_meta(vol.meta)
        m = vol.meta
        self.statusBar().showMessage(
            f"{m.get('patient','—')} · {m.get('modality','')} · {vol.data.shape[0]} cortes")
        self.set_mode("2d")

    def open_dicom(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecione a pasta da série DICOM")
        if not d:
            return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            vol = dicom_io.load_series(d)
        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.critical(self, "Erro ao abrir DICOM", str(e))
            return
        QtWidgets.QApplication.restoreOverrideCursor()
        self._set_volume(vol)

    def open_demo(self):
        self._set_volume(dicom_io.demo_volume())

    # -- caso (salvar/abrir) ------------------------------------------------
    def save_case(self):
        from ..core import case as casemod
        default = f"caso-{self.patient.slug()}.osteon"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar caso", default, "Caso Osteon (*.osteon)")
        if not path:
            return
        import numpy as np
        state = {
            "version": 1,
            "patient": {"nome": self.patient.nome.text(), "nasc": self.patient.nasc.text(),
                        "registro": self.patient.reg.text()},
            "model_params": {"hu": self.model_panel.hu.value(), "smooth": self.model_panel.smooth.value(),
                             "dec": self.model_panel.dec.value(), "largest": self.model_panel.largest.isChecked()},
        }
        meshes = {}
        if _HAS_VTK:
            state["segment"] = {"fragments": [
                {"name": f["name"], "color": list(f["color"]), "move": f.get("move") or self._zero_move(),
                 "visible": f["visible"]} for f in self.frags]}
            state["register"] = {
                "anat_lm": self.register_view.anat_lm, "imp_lm": self.register_view.imp_lm,
                "treg": np.asarray(self.reg_treg, float).tolist(),
                "manual": self.register_panel.manual(), "scale": self.register_panel.scale.isChecked()}
            state["ceph"] = {"landmarks": {k: list(v) for k, v in self.ceph_view.landmarks.items()}}
            if self.mesh is not None:
                meshes["model"] = self.mesh
            for i, f in enumerate(self.frags):
                meshes[f"frag_{i:03d}"] = f["poly"]
            if self.reg_imp is not None:
                meshes["imported"] = self.reg_imp
        try:
            casemod.save_case(path, state, self.vol, meshes)
            self.statusBar().showMessage(f"Caso salvo: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Salvar caso", str(e))

    def open_case(self):
        from ..core import case as casemod
        import numpy as np
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Abrir caso", "", "Caso Osteon (*.osteon)")
        if not path:
            return
        try:
            state, vol, meshes = casemod.load_case(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Abrir caso", str(e))
            return
        if vol is not None:
            self.vol = vol
            self.slice_view.set_volume(vol)
        pt = state.get("patient", {})
        self.patient.nome.setText(pt.get("nome", "")); self.patient.nasc.setText(pt.get("nasc", "")); self.patient.reg.setText(pt.get("registro", ""))
        mp = state.get("model_params", {})
        if mp:
            self.model_panel.hu.setValue(int(mp.get("hu", 300)))
            self.model_panel.smooth.setValue(int(mp.get("smooth", 15)))
            self.model_panel.dec.setValue(float(mp.get("dec", 0.0)))
            self.model_panel.largest.setChecked(bool(mp.get("largest", False)))
        self.mesh = meshes.get("model")
        if _HAS_VTK:
            self.frags = []
            for i, meta in enumerate(state.get("segment", {}).get("fragments", [])):
                poly = meshes.get(f"frag_{i:03d}")
                if poly is None:
                    continue
                self.frags.append(dict(poly=poly, color=tuple(meta.get("color", PALETTE[0])),
                                       center=self._poly_center(poly), move=meta.get("move") or self._zero_move(),
                                       name=meta.get("name", f"frag {i}"), visible=meta.get("visible", True)))
            reg = state.get("register", {})
            self.reg_imp = meshes.get("imported")
            tg = reg.get("treg")
            self.reg_treg = np.asarray(tg, float) if tg else regmod.identity()
            self.register_view.anat_lm = [list(map(float, p)) for p in reg.get("anat_lm", [])]
            self.register_view.imp_lm = [list(map(float, p)) for p in reg.get("imp_lm", [])]
            self.register_view._refresh_markers()
            man = reg.get("manual", {})
            rp = self.register_panel
            for k, w in (("tx", rp.tx), ("ty", rp.ty), ("tz", rp.tz), ("rx", rp.rx), ("ry", rp.ry), ("rz", rp.rz), ("sc", rp.sc)):
                if k in man:
                    w.blockSignals(True); w.setValue(float(man[k])); w.blockSignals(False)
            rp.scale.setChecked(bool(reg.get("scale", False)))
            cl = state.get("ceph", {}).get("landmarks", {})
            self.ceph_view.landmarks = {k: (int(v[0]), int(v[1])) for k, v in cl.items()}
        self.set_mode("2d")
        self.statusBar().showMessage(f"Caso aberto: {path}")

    # -- modos --------------------------------------------------------------
    def set_mode(self, key):
        for a in self.mode_group.actions():
            a.setChecked(a.data() == key)
        self.model_panel.setVisible(key == "model")
        self.segment_panel.setVisible(key == "segment")
        self.register_panel.setVisible(key == "register")
        self.ceph_panel.setVisible(key == "ceph")
        if key == "mpr":
            self.stack.setCurrentWidget(self.mpr_view)
            if self.vol is not None:
                self.mpr_view.set_volume(self.vol)
            return
        if key == "ceph":
            self.stack.setCurrentWidget(self.ceph_view)
            self.ceph_view.set_current(self.ceph_panel.current_sig())
            if self.vol is not None:
                self.ceph_view.set_volume(self.vol)
            self.update_ceph_results()
            return
        if key == "2d" or not _HAS_VTK:
            self.stack.setCurrentIndex(0)
            return
        if key == "segment":
            self.enter_segment()
            return
        if key == "register":
            self.enter_register()
            return
        self.stack.setCurrentIndex(1)
        self.volume_view.start()
        if self.vol is None:
            return
        if key == "3d":
            self.volume_view.show_volume(self.vol)
        elif key == "model":
            if self.mesh is not None:
                self.volume_view.show_meshes([(self.mesh, (0.86, 0.86, 0.9), 1.0)])
            else:
                self.on_generate()

    # -- segmentar ----------------------------------------------------------
    def _wire_segment_panel(self):
        p = self.segment_panel
        p.cut.connect(self.on_seg_cut)
        p.planeChanged.connect(self.update_seg_plane)
        p.moveChanged.connect(self.on_seg_move)
        p.measure.connect(self.on_seg_measure)
        p.reset.connect(self.on_seg_reset)
        p.exportOne.connect(lambda: self.on_seg_export(False))
        p.exportAll.connect(lambda: self.on_seg_export(True))
        p.lassoToggled.connect(self.on_seg_lasso_toggle)
        p.fragSelected.connect(self.on_seg_frag_selected)
        p.visChanged.connect(self.on_seg_vis)

    def enter_segment(self):
        if self.vol is None:
            return
        if self.mesh is None:
            self.on_generate()
        if self.mesh is None:
            return
        self.stack.setCurrentIndex(2)
        self.segment_view.start()
        if not self.frags:
            self.frags = [dict(poly=self.mesh, color=PALETTE[0], center=self._poly_center(self.mesh),
                               move=self._zero_move(), name="Osso (original)", visible=True)]
            self.seg_sel = 0
        self.seg_bounds = self.mesh.GetBounds()
        self._seg_refresh_list()
        self.segment_view.set_fragments(self.frags)
        self.update_seg_plane()

    def _seg_refresh_list(self):
        c = self.segment_panel.sel
        c.blockSignals(True)
        c.clear()
        for i, f in enumerate(self.frags):
            c.addItem(f["name"], i)
        self.seg_sel = min(self.seg_sel, len(self.frags) - 1)
        c.setCurrentIndex(self.seg_sel)
        c.blockSignals(False)
        f = self.frags[self.seg_sel]
        self.segment_panel.vis.blockSignals(True); self.segment_panel.vis.setChecked(f["visible"]); self.segment_panel.vis.blockSignals(False)
        self.segment_panel.set_move(f.get("move"))

    def _zero_move(self):
        return dict(tx=0, ty=0, tz=0, rx=0, ry=0, rz=0)

    def _poly_center(self, poly):
        b = poly.GetBounds()
        return [(b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2]

    def _frag_transform(self, center, mv):
        # replica a transformação do ator VTK (origem = centroide; ordem Z,X,Y)
        tr = _vtk.vtkTransform(); tr.PostMultiply()
        tr.Translate(-center[0], -center[1], -center[2])
        tr.RotateZ(mv.get("rz", 0)); tr.RotateX(mv.get("rx", 0)); tr.RotateY(mv.get("ry", 0))
        tr.Translate(center[0], center[1], center[2])
        tr.Translate(mv.get("tx", 0), mv.get("ty", 0), mv.get("tz", 0))
        return tr

    def _seg_normal(self):
        return segmod.plane_normal(self.segment_panel.axis.currentIndex(),
                                   self.segment_panel.ta.value(), self.segment_panel.tb.value())

    def update_seg_plane(self):
        if self.seg_bounds is None or not _HAS_VTK:
            return
        if not self.segment_panel.showPlane.isChecked():
            self.segment_view.hide_plane(); return
        n = self._seg_normal()
        origin = segmod.plane_origin(self.seg_bounds, n, self.segment_panel.pos.value() / 100.0)
        b = self.seg_bounds
        size = 0.6 * max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
        self.segment_view.set_plane(origin, n, size)

    def on_seg_frag_selected(self):
        self.seg_sel = max(0, self.segment_panel.sel.currentIndex())
        f = self.frags[self.seg_sel]
        self.segment_panel.vis.blockSignals(True); self.segment_panel.vis.setChecked(f["visible"]); self.segment_panel.vis.blockSignals(False)
        self.segment_panel.set_move(f.get("move"))

    def on_seg_vis(self):
        self.frags[self.seg_sel]["visible"] = self.segment_panel.vis.isChecked()
        self.segment_view.set_fragments(self.frags)

    def on_seg_cut(self):
        if not self.frags:
            return
        f = self.frags[self.seg_sel]
        n = self._seg_normal()
        origin = segmod.plane_origin(self.seg_bounds, n, self.segment_panel.pos.value() / 100.0)
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            a, b = segmod.cut_by_plane(f["poly"], origin, n, cap=self.segment_panel.cap.isChecked())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if a.GetNumberOfCells() == 0 or b.GetNumberOfCells() == 0:
            self.segment_panel.info.setText("O plano não atravessa este fragmento.")
            return
        ca = PALETTE[len(self.frags) % len(PALETTE)]
        cb = PALETTE[(len(self.frags) + 1) % len(PALETTE)]
        A = dict(poly=a, color=ca, center=self._poly_center(a), move=self._zero_move(), name=f["name"] + " · A", visible=True)
        B = dict(poly=b, color=cb, center=self._poly_center(b), move=self._zero_move(), name=f["name"] + " · B", visible=True)
        self.frags[self.seg_sel:self.seg_sel + 1] = [A, B]
        self._seg_refresh_list()
        self.segment_view.set_fragments(self.frags)
        self.segment_panel.info.setText(
            f"Fragmentos: {len(self.frags)} · A {a.GetNumberOfCells():,} / B {b.GetNumberOfCells():,} tri".replace(",", "."))

    def on_seg_move(self):
        f = self.frags[self.seg_sel]
        f["move"] = self.segment_panel.move()
        self.segment_view.update_transform(self.seg_sel, f["center"], f["move"])
        mv = f["move"]
        disp = (mv["tx"] ** 2 + mv["ty"] ** 2 + mv["tz"] ** 2) ** 0.5
        self.segment_panel.info.setText(
            f"Deslocamento {disp:.1f} mm · rot ({mv['rx']:.0f}, {mv['ry']:.0f}, {mv['rz']:.0f})°")

    def on_seg_measure(self):
        if not _HAS_VTK or not self.frags:
            return
        from ..core import measure as measmod
        f = self.frags[self.seg_sel]
        try:
            vol_mm3, area_mm2 = measmod.volume_area(f["poly"])
        except Exception as e:
            self.segment_panel.info.setText(f"Falha ao medir: {e}")
            return
        self.segment_panel.info.setText(
            f"{f['name']}: volume {vol_mm3/1000.0:.2f} cm³ · área {area_mm2/100.0:.2f} cm²\n"
            f"(volume confiável só com a face fechada)")

    def on_seg_reset(self):
        self.frags = []
        self.segment_panel.info.setText("")
        self.enter_segment()

    def on_seg_lasso_toggle(self, on):
        self.segment_view.set_lasso(on)
        self.segment_panel.info.setText(
            "Laço ativo: desenhe um contorno fechado sobre o modelo." if on else "")

    def on_seg_lasso_done(self, pts):
        if not self.frags:
            return
        f = self.frags[self.seg_sel]
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            mv = f.get("move") or self._zero_move()
            mask = self.segment_view.classify_lasso(f["poly"], (mv["tx"], mv["ty"], mv["tz"]), pts)
            inside, outside = segmod.split_by_mask(f["poly"], mask)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if inside.GetNumberOfCells() == 0 or outside.GetNumberOfCells() == 0:
            self.segment_panel.info.setText("O laço não separou o fragmento.")
            return
        ca = PALETTE[len(self.frags) % len(PALETTE)]
        cb = PALETTE[(len(self.frags) + 1) % len(PALETTE)]
        A = dict(poly=inside, color=ca, center=self._poly_center(inside), move=self._zero_move(), name=f["name"] + " · dentro", visible=True)
        B = dict(poly=outside, color=cb, center=self._poly_center(outside), move=self._zero_move(), name=f["name"] + " · fora", visible=True)
        self.frags[self.seg_sel:self.seg_sel + 1] = [A, B]
        self.segment_panel.b_lasso.setChecked(False)
        self._seg_refresh_list()
        self.segment_view.set_fragments(self.frags)
        self.segment_panel.info.setText(f"Separado pelo laço · {len(self.frags)} fragmentos.")

    def _baked(self, f):
        """Aplica a transformação (reposicionamento) do fragmento à malha."""
        tf = _vtk.vtkTransformPolyDataFilter()
        tf.SetTransform(self._frag_transform(f["center"], f.get("move") or self._zero_move()))
        tf.SetInputData(f["poly"]); tf.Update()
        return tf.GetOutput()

    # -- cefalometria -------------------------------------------------------
    def update_ceph_results(self):
        self.ceph_panel.set_results(cephmod.compute(self.ceph_view.landmarks_mm()))

    # -- registro -----------------------------------------------------------
    def _wire_register_panel(self):
        p = self.register_panel
        p.importStl.connect(self.on_reg_import)
        p.pickToggled.connect(lambda on: self.register_view.set_pick_mode(on))
        p.runLandmark.connect(self.on_reg_landmark)
        p.runIcp.connect(self.on_reg_icp)
        p.devToggled.connect(self.reg_update_overlay)
        p.manualChanged.connect(self.reg_update_overlay)
        p.undo.connect(lambda: self.register_view.undo())
        p.clear.connect(lambda: self.register_view.clear())
        p.exportAligned.connect(self.on_reg_export)
        p.saveJson.connect(self.on_reg_save)
        p.loadJson.connect(self.on_reg_load)
        p.reportPdf.connect(self.on_reg_report)

    def enter_register(self):
        if self.vol is None:
            return
        if self.mesh is None:
            self.on_generate()
        if self.mesh is None:
            return
        self.stack.setCurrentIndex(3)
        self.register_view.start()
        self.register_view.set_meshes(self.mesh, self.reg_imp)
        self.reg_update_overlay()

    def _reg_center(self):
        b = self.mesh.GetBounds()
        return ((b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2)

    def _reg_final_matrix(self):
        import numpy as np
        m = self.register_panel.manual()
        cx, cy, cz = self._reg_center()
        tr = _vtk.vtkTransform(); tr.PostMultiply()
        tr.Translate(-cx, -cy, -cz)
        tr.Scale(m["sc"], m["sc"], m["sc"])
        tr.RotateZ(m["rz"]); tr.RotateY(m["ry"]); tr.RotateX(m["rx"])
        tr.Translate(cx, cy, cz)
        tr.Translate(m["tx"], m["ty"], m["tz"])
        manual = regmod.mat_to_np(tr.GetMatrix())
        return manual @ np.asarray(self.reg_treg, float)

    def reg_update_overlay(self):
        if not _HAS_VTK or self.reg_imp is None or self.stack.currentIndex() != 3:
            return
        Tf = self._reg_final_matrix()
        world = regmod.apply_matrix(self.reg_imp, Tf)
        op = self.register_panel.opa.value() / 100.0
        if self.register_panel.dev.isChecked():
            scale = self.register_panel.devScale.value()
            colored, mean, mx, d = regmod.deviation(world, self.mesh, scale)
            self.register_view.set_overlay(colored, (1, 1, 1), 1.0, lut=regmod.jet_lut(scale))
            self.reg_dists = d
            self.reg_stats["dev"] = (mean, mx, scale)
            hl = self.register_panel.hist
            self.register_panel.hist.setPixmap(
                render_histogram(d, scale, max(120, hl.width()), hl.height()))
            self.register_panel.info.setText(f"Desvio: média {mean:.2f} mm · máx {mx:.2f} mm")
        else:
            self.register_view.set_overlay(world, (1.0, 0.72, 0.30), op)
            self.register_panel.hist.clear()

    def on_reg_landmarks(self):
        self.register_panel.info.setText(
            f"Pontos: {len(self.register_view.anat_lm)} anat / {len(self.register_view.imp_lm)} imp.")

    def on_reg_import(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Importar STL", "", "STL (*.stl)")
        if not path:
            return
        self.reg_imp = regmod.read_stl(path)
        self.reg_treg = regmod.identity()
        self.register_view.imp_lm = []
        self.register_view.set_meshes(self.mesh, self.reg_imp)
        self.reg_update_overlay()
        self.register_panel.info.setText(
            f"Importado: {self.reg_imp.GetNumberOfCells():,} triângulos.".replace(",", "."))

    def on_reg_landmark(self):
        import numpy as np
        a, b = self.register_view.anat_lm, self.register_view.imp_lm
        n = min(len(a), len(b))
        if n < 3:
            self.register_panel.info.setText("Marque ao menos 3 pares de pontos.")
            return
        mat, rms = regmod.landmark_register(b[:n], a[:n], scale=self.register_panel.scale.isChecked())
        self.reg_treg = mat
        self.reg_stats["method"] = ("Landmarks (vtkLandmarkTransform)", f"RMS {rms:.2f} mm", n)
        self._reg_reset_manual()
        self.reg_update_overlay()
        self.register_panel.info.setText(f"Landmarks: RMS {rms:.2f} mm ({n} pares).")

    def on_reg_icp(self):
        if self.reg_imp is None:
            return
        import numpy as np
        pre = regmod.apply_matrix(self.reg_imp, np.asarray(self.reg_treg, float))
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            delta, meand = regmod.icp_register(pre, self.mesh, scale=self.register_panel.scale.isChecked())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.reg_treg = np.asarray(delta, float) @ np.asarray(self.reg_treg, float)
        self.reg_stats["method"] = ("ICP (vtkIterativeClosestPointTransform)", f"dist. média {meand:.2f} mm", None)
        self._reg_reset_manual()
        self.reg_update_overlay()
        self.register_panel.info.setText(f"ICP: distância média {meand:.2f} mm.")

    def _reg_reset_manual(self):
        p = self.register_panel
        for w in (p.tx, p.ty, p.tz, p.rx, p.ry, p.rz):
            w.blockSignals(True); w.setValue(0); w.blockSignals(False)
        p.sc.blockSignals(True); p.sc.setValue(1.0); p.sc.blockSignals(False)

    def on_reg_export(self):
        if self.reg_imp is None:
            return
        import numpy as np
        world = regmod.apply_matrix(self.reg_imp, self._reg_final_matrix())
        default = f"alinhado-{self.patient.slug()}.stl"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar alinhado", default, "STL (*.stl)")
        if not path:
            return
        meshmod.write_stl(world, path, binary=True)
        self.statusBar().showMessage(f"STL alinhado salvo: {path}")

    def on_reg_save(self):
        default = f"registro-{self.patient.slug()}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar registro", default, "JSON (*.json)")
        if not path:
            return
        regmod.save_json(path, self.register_view.anat_lm, self.register_view.imp_lm,
                         self.reg_treg, self.register_panel.manual(), self.register_panel.scale.isChecked())
        self.statusBar().showMessage(f"Registro salvo: {path}")

    def on_reg_load(self):
        import numpy as np
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Carregar registro", "", "JSON (*.json)")
        if not path:
            return
        d = regmod.load_json(path)
        self.register_view.anat_lm = [list(map(float, p)) for p in d.get("anat_landmarks", [])]
        self.register_view.imp_lm = [list(map(float, p)) for p in d.get("imp_landmarks", [])]
        self.register_view._refresh_markers()
        tg = d.get("treg")
        if tg:
            self.reg_treg = np.asarray(tg, float)
        man = d.get("manual", {})
        p = self.register_panel
        for k, w in (("tx", p.tx), ("ty", p.ty), ("tz", p.tz), ("rx", p.rx), ("ry", p.ry), ("rz", p.rz), ("sc", p.sc)):
            if k in man:
                w.blockSignals(True); w.setValue(float(man[k])); w.blockSignals(False)
        p.scale.setChecked(bool(d.get("scale", False)))
        self.reg_update_overlay()
        self.register_panel.info.setText("Registro carregado (importe o mesmo STL para ver a sobreposição).")

    def on_reg_report(self):
        import os, tempfile
        if not reportmod.available():
            QtWidgets.QMessageBox.information(
                self, "Relatório PDF",
                "O reportlab não está instalado. Instale com: pip install reportlab")
            return
        default = f"relatorio-{self.patient.slug()}.pdf"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Relatório PDF", default, "PDF (*.pdf)")
        if not path:
            return
        tmp = tempfile.mkdtemp(prefix="osteon_")
        images = []
        shot = os.path.join(tmp, "view.png")
        self.register_view.grab().save(shot, "PNG")
        images.append(("Sobreposição (anatômico | importado)", shot))
        if self.reg_dists is not None and "dev" in self.reg_stats:
            hp = os.path.join(tmp, "hist.png")
            scale = self.reg_stats["dev"][2]
            render_histogram(self.reg_dists, scale, 480, 150).save(hp, "PNG")
            images.append((f"Histograma do desvio (0–{scale:g} mm)", hp))
        m = self.vol.meta if self.vol else {}
        header = {
            "Paciente": self.patient.nome.text() or m.get("patient", "—"),
            "Registro": self.patient.reg.text() or m.get("patient_id", "—"),
            "Nascimento": self.patient.nasc.text() or m.get("birth", "—"),
            "Série": m.get("series", "—"),
        }
        metrics = []
        if "method" in self.reg_stats:
            meth, val, n = self.reg_stats["method"]
            metrics.append(("Método", meth))
            metrics.append(("Erro de alinhamento", val + (f" ({n} pares)" if n else "")))
        metrics.append(("Permitir escala", "sim" if self.register_panel.scale.isChecked() else "não"))
        metrics.append(("Pontos de correspondência",
                        f"{len(self.register_view.anat_lm)} anat / {len(self.register_view.imp_lm)} imp"))
        if "dev" in self.reg_stats:
            mean, mx, scale = self.reg_stats["dev"]
            metrics.append(("Desvio importado→anatômico", f"média {mean:.2f} mm · máx {mx:.2f} mm (escala {scale:g} mm)"))
        try:
            reportmod.registration_report(path, header, metrics, images)
            self.statusBar().showMessage(f"Relatório salvo: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Relatório PDF", str(e))

    def on_seg_export(self, all_frags):
        if not self.frags:
            return
        slug = self.patient.slug()
        if all_frags:
            default = f"segmentacao-{slug}.stl"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar todos", default, "STL (*.stl)")
            if not path:
                return
            app = _vtk.vtkAppendPolyData()
            for f in self.frags:
                app.AddInputData(self._baked(f))
            app.Update()
            meshmod.write_stl(app.GetOutput(), path, binary=True)
        else:
            f = self.frags[self.seg_sel]
            default = f"fragmento-{slug}.stl"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar fragmento", default, "STL (*.stl)")
            if not path:
                return
            meshmod.write_stl(self._baked(f), path, binary=True)
        self.statusBar().showMessage(f"STL salvo: {path}")

    # -- modelo -------------------------------------------------------------
    def on_generate(self):
        if self.vol is None or not _HAS_VTK:
            return
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.mesh = meshmod.generate_model(
                self.vol,
                hu=float(self.model_panel.hu.value()),
                smooth_iters=int(self.model_panel.smooth.value()),
                decimate=float(self.model_panel.dec.value()),
                keep_largest=self.model_panel.largest.isChecked())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        st = meshmod.mesh_stats(self.mesh)
        dim = st.get("dim_mm", (0, 0, 0))
        self.model_panel.stats.setText(
            f"Triângulos: {st.get('triangles',0):,}\n"
            f"Dimensões: {dim[0]:.1f} × {dim[1]:.1f} × {dim[2]:.1f} mm".replace(",", "."))
        self.stack.setCurrentIndex(1)
        self.volume_view.start()
        self.volume_view.show_meshes([(self.mesh, (0.86, 0.86, 0.9), 1.0)])
        self.set_mode("model")

    def on_export(self):
        if self.mesh is None or not _HAS_VTK:
            QtWidgets.QMessageBox.information(self, "Exportar", "Gere a malha primeiro.")
            return
        default = f"modelo-{self.patient.slug()}.stl"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar STL", default, "STL (*.stl)")
        if not path:
            return
        meshmod.write_stl(self.mesh, path, binary=(self.model_panel.fmt.currentText() == "Binário"))
        self.statusBar().showMessage(f"STL salvo: {path}")
