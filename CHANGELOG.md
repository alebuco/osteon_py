# Changelog — Osteon Viewer

## 0.0.3 — 2026-11-11
- **MPR**: reconstrução multiplanar (axial/coronal/sagital) com cursor
  sincronizado, proporção física e janelamento (Qt puro).
- **Cefalometria**: projeção lateral (MIP), marcação de pontos e análises
  (SNA, SNB, ANB, SN-GoGn, FMA) com comparação a valores de referência.
- **Histograma do desvio** no módulo Registro.
- **Relatório PDF** do registro (reportlab): cabeçalho do paciente, captura das
  janelas, métricas e histograma.

## 0.0.2 — 2026-11-11
Reescrita como aplicativo desktop em Python (PySide6 + VTK).

- Carga DICOM → volume (HU, espaçamento, origem, orientação, metadados).
- **2D**: cortes axiais com janelamento e navegação.
- **3D**: renderização volumétrica (ray casting) com transferência para osso.
- **Modelo (STL)**: isosuperfície (flying edges), suavização Taubin, decimação,
  maior componente, exportação binário/ASCII.
- **Segmentar**: corte por plano com tampa sólida (watertight), laço, afastar,
  exportar fragmento/todos.
- **Registro**: landmarks (vtkLandmarkTransform), ICP, mapa de desvio, ajuste
  manual, exportar alinhado, salvar/carregar JSON.
- **Cadastro de paciente** (local) nomeando os exports.
- Empacotamento Windows (.exe/Inno Setup) e Linux (AppImage) + CI (GitHub Actions).

> Em aberto: MPR, cefalometria, histograma do desvio, relatório PDF.
