# Osteon Viewer — versão Python (desktop) · v0.0.5

Reescrita do Osteon como aplicativo de desktop em **Python**, com interface
**PySide6 (Qt6)** e núcleo de imagem médica em **VTK** + numpy/scipy/scikit-image.
Gera instaladores para **Windows** (.exe) e **Linux** (AppImage).

## O que já está nesta fundação

- **Carga DICOM** (pydicom): série → volume em HU, com espaçamento, origem,
  orientação anatômica (ImageOrientationPatient) e metadados do paciente.
- **2D**: visor de cortes axiais com janelamento (arraste com botão direito) e
  navegação (scroll / slider).
- **MPR**: reconstrução multiplanar (axial/coronal/sagital) com cursor
  sincronizado, proporção física correta e janelamento.
- **Cefalometria**: projeção lateral (MIP), marcação de pontos e análises
  angulares (SNA, SNB, ANB, SN-GoGn, FMA) comparadas a valores de referência.
- **3D**: renderização volumétrica por ray casting (GPU) com função de
  transferência para osso.
- **Modelo (STL)**: isosuperfície (flying edges) por limiar HU, suavização
  Taubin, decimação, maior componente e exportação STL (binário/ASCII).
- **Segmentar / osteotomia**: cada corte cria objetos novos; **lista de objetos
  com multisseleção**, **cor por objeto**, **ocultar/mostrar**. Corte por
  **plano** (eixo + posição + duas inclinações) com **tampa sólida**
  (`vtkClipClosedSurface`, watertight) e **corte por laço**. **Operações
  booleanas** (unir/subtrair), **reposicionamento** (translação + rotação em
  torno do centroide), **medição de volume/área** (vtkMassProperties) e
  exportação STL (com a transformação aplicada) dos selecionados ou de todos.
- **Registro / Sobreposição**: importa um STL e o alinha ao modelo em duas
  janelas lado a lado — pontos correspondentes (`vtkCellPicker`), registro por
  landmarks (`vtkLandmarkTransform`, rígido ou com escala), refino **ICP**
  (`vtkIterativeClosestPointTransform`), **mapa de desvio** por distância
  ponto-superfície (`vtkImplicitPolyDataDistance`) com média/máx, ajuste manual,
  exportação do alinhado, **histograma do desvio**, **relatório PDF** e
  salvar/carregar o registro em JSON.
- **Cadastro de paciente**: nome, nascimento, nº de registro — pré-preenchido do
  DICOM e salvo localmente (JSON na pasta de dados do usuário); nomeia os
  arquivos exportados.
- **Casos**: salvar/abrir um arquivo único `.osteon` (Arquivo → Salvar/Abrir
  caso) com estado, volume e malhas — reabre o trabalho sem o DICOM original.
- **Fantoma de demonstração** para abrir sem dados.

> Paridade com o protótipo JS concluída. Próximos possíveis: planejamento de
> osteotomia (reposicionar fragmentos com números), medições de volume/espessura
> e salvar/abrir um "caso" completo.

## Rodar a partir do código (qualquer SO)

```bash
python -m pip install -r requirements.txt
python run.py            # ou:  python -m osteon
```

Requer Python 3.10+. No Linux, pacotes de sistema para o Qt/VTK podem ser
necessários (ver a seção do CI abaixo para a lista).

## Gerar os instaladores

### Windows (.exe)

```bat
pip install -r requirements.txt pyinstaller
pyinstaller packaging\osteon.spec
:: isso cria dist\Osteon\  (pasta do app)
:: instalador: precisa do Inno Setup (https://jrsoftware.org/isdl.php)
iscc packaging\osteon.iss
:: saída: dist\installer\OsteonViewer-Setup-1.0.0.exe
```

### Linux (AppImage)

```bash
pip install -r requirements.txt pyinstaller
pyinstaller packaging/osteon.spec
bash packaging/build-appimage.sh
# saída: dist/OsteonViewer-1.0.0-x86_64.AppImage
```

### Windows + Linux automaticamente (GitHub Actions)

Inclui `.github/workflows/build.yml`, que compila os dois na nuvem (runners com
internet e as ferramentas prontas): suba a pasta para um repositório GitHub,
abra **Actions → build → Run workflow** e baixe os instaladores em **Artifacts**
(`osteon-windows`, `osteon-linux`). Uma tag `v*` publica uma Release com eles.

## Estrutura

```
osteon-py/
├─ run.py                      # entry point (usado também pelo PyInstaller)
├─ pyproject.toml / requirements.txt
├─ osteon/
│  ├─ app.py                   # QApplication + janela
│  ├─ core/
│  │  ├─ dicom_io.py           # DICOM -> Volume (numpy)
│  │  └─ mesh.py               # isosuperfície + STL (VTK; reserva skimage)
│  ├─ ui/
│  │  ├─ main_window.py        # modos, menu, painel
│  │  └─ patient_panel.py      # cadastro de paciente
│  └─ viewers/
│     ├─ slice_view.py         # 2D (Qt)
│     └─ volume_view.py        # 3D/malha (VTK)
└─ packaging/
   ├─ osteon.spec              # PyInstaller
   ├─ osteon.iss               # instalador Windows (Inno Setup)
   ├─ build-appimage.sh        # AppImage Linux
   └─ icon.ico / icon.png
```

## Observações

- Ferramenta de **visualização e estudo** — não é software médico certificado
  para diagnóstico. Avalie exigências regulatórias antes de uso clínico.
- **Clean-room**: código e algoritmos próprios; sem código, recursos ou marca de
  terceiros, e sem qualquer bypass de proteção/licença.
- Os cadastros de paciente ficam **somente neste computador** (não há envio a
  servidores).
- Assinatura de código (Windows) e do pacote (Linux) seguem a mesma lógica da
  versão anterior — posso adicionar ao fluxo quando você tiver o certificado.
