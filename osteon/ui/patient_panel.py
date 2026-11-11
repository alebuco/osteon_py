"""Cadastro de paciente (nome, nascimento, nº de registro), persistido em
JSON na pasta de dados do usuário. Pré-preenche a partir dos metadados DICOM."""
from __future__ import annotations
import json
import os
import re
from PySide6 import QtCore, QtWidgets


def _data_dir() -> str:
    d = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
    os.makedirs(d, exist_ok=True)
    return d


class PatientPanel(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Paciente", parent)
        self.path = os.path.join(_data_dir(), "patients.json")
        self.patients = self._load()

        self.sel = QtWidgets.QComboBox()
        self.sel.currentIndexChanged.connect(self._on_select)
        self.nome = QtWidgets.QLineEdit()
        self.nasc = QtWidgets.QLineEdit()
        self.nasc.setPlaceholderText("AAAA-MM-DD")
        self.reg = QtWidgets.QLineEdit()
        self.reg.setPlaceholderText("Registro / prontuário")

        form = QtWidgets.QFormLayout()
        form.addRow("Cadastro", self.sel)
        form.addRow("Nome", self.nome)
        form.addRow("Nascimento", self.nasc)
        form.addRow("Nº registro", self.reg)

        b_save = QtWidgets.QPushButton("Salvar")
        b_new = QtWidgets.QPushButton("Novo")
        b_del = QtWidgets.QPushButton("Remover")
        b_save.clicked.connect(self.save)
        b_new.clicked.connect(self.new)
        b_del.clicked.connect(self.delete)
        btns = QtWidgets.QHBoxLayout()
        for b in (b_save, b_new, b_del):
            btns.addWidget(b)

        self.note = QtWidgets.QLabel("Pré-preenchido do DICOM. Salvo só neste computador.")
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#8aa;font-size:11px;")

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(btns)
        lay.addWidget(self.note)
        self._refresh_combo()

    # -- persistência -------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                a = json.load(f)
            return a if isinstance(a, list) else []
        except Exception:
            return []

    def _save_disk(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.patients, f, ensure_ascii=False, indent=1)
            return True
        except Exception as e:
            self.note.setText(f"Falha ao salvar: {e}")
            return False

    # -- UI -----------------------------------------------------------------
    def _refresh_combo(self, select_reg=None):
        self.sel.blockSignals(True)
        self.sel.clear()
        self.sel.addItem("— novo —", "")
        for p in self.patients:
            label = (p.get("nome") or "(sem nome)") + (f" — {p['registro']}" if p.get("registro") else "")
            self.sel.addItem(label, p.get("registro", ""))
        if select_reg:
            i = self.sel.findData(select_reg)
            if i >= 0:
                self.sel.setCurrentIndex(i)
        self.sel.blockSignals(False)

    def _on_select(self, _i):
        reg = self.sel.currentData()
        if not reg:
            return
        p = next((x for x in self.patients if x.get("registro") == reg), None)
        if p:
            self.nome.setText(p.get("nome", ""))
            self.nasc.setText(p.get("nasc", ""))
            self.reg.setText(p.get("registro", ""))

    def new(self):
        self.sel.setCurrentIndex(0)
        self.nome.clear(); self.nasc.clear(); self.reg.clear()
        self.note.setText("Novo cadastro — preencha os campos.")

    def save(self):
        reg = self.reg.text().strip()
        if not reg:
            self.note.setText("Informe o nº de registro para salvar.")
            return
        rec = {"nome": self.nome.text().strip(), "nasc": self.nasc.text().strip(), "registro": reg}
        i = next((k for k, x in enumerate(self.patients) if x.get("registro") == reg), -1)
        if i >= 0:
            self.patients[i] = rec
        else:
            self.patients.append(rec)
        if self._save_disk():
            self._refresh_combo(select_reg=reg)
            self.note.setText(f"Cadastro salvo: {rec['nome'] or '(sem nome)'} · {reg}.")

    def delete(self):
        reg = self.reg.text().strip()
        self.patients = [x for x in self.patients if x.get("registro") != reg]
        self._save_disk()
        self.new()
        self._refresh_combo()
        self.note.setText("Cadastro removido.")

    # -- integração ---------------------------------------------------------
    def set_from_meta(self, meta: dict):
        reg = meta.get("patient_id", "") or ""
        ex = next((x for x in self.patients if x.get("registro") == reg), None) if reg else None
        if ex:
            self._refresh_combo(select_reg=reg)
            self._on_select(0)
            self.note.setText(f"Cadastro existente carregado: {ex.get('nome','')}.")
        else:
            self.sel.setCurrentIndex(0)
            self.nome.setText(meta.get("patient", "") if meta.get("patient") != "—" else "")
            self.nasc.setText(meta.get("birth", "") or "")
            self.reg.setText(reg)
            self.note.setText("Dados do DICOM — confira e clique em Salvar.")

    def slug(self) -> str:
        s = (self.reg.text().strip() or self.nome.text().strip() or "")
        s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:40]
        return s or "paciente"
