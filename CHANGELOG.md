# Changelog — Osteon Viewer

## 0.0.5 — 2026-11-11
- Segmentar: lista de **objetos com multisseleção**, cada corte gera objetos
  novos independentes.
- **Operações booleanas**: unir e subtrair objetos selecionados
  (vtkBooleanOperationPolyDataFilter), aplicadas já na posição atual.
- **Cor por objeto** (seletor de cor) e **ocultar/mostrar** objetos
  selecionados (e por caixa de seleção na lista).
- Exportar exporta os objetos selecionados (um ou vários).

## 0.0.4 — 2026-11-11
- **Planejamento de osteotomia**: reposicionamento de cada fragmento por
  translação (X/Y/Z) e rotação (X/Y/Z) em torno do próprio centroide, com
  leitura do deslocamento; exportação já com a transformação aplicada.
- **Medições**: volume (cm³) e área (cm²) por fragmento via vtkMassProperties.
- **Casos**: salvar/abrir um arquivo único `.osteon` (zip) com estado (JSON),
  volume (npz comprimido) e malhas (STL) — reabre tudo sem o DICOM original.

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
