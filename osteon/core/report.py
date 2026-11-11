"""Relatório PDF do registro (reportlab). Uma página A4 com cabeçalho do
paciente, métricas e imagens (captura das janelas e histograma)."""
from __future__ import annotations
import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.utils import ImageReader
    _HAS_RL = True
except Exception:
    _HAS_RL = False


def available() -> bool:
    return _HAS_RL


def registration_report(path, header: dict, metrics, images):
    """header: dict com chaves livres (ex. Paciente, Registro, Nascimento, Série).
    metrics: lista de (rótulo, valor). images: lista de (legenda, caminho_png)."""
    if not _HAS_RL:
        raise RuntimeError("reportlab não está instalado (pip install reportlab).")
    W, H = A4
    c = _canvas.Canvas(path, pagesize=A4)
    x = 18 * mm
    y = H - 20 * mm

    c.setFillColorRGB(0.08, 0.1, 0.13)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Relatório de Registro / Sobreposição")
    y -= 9 * mm

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.3, 0.33, 0.38)
    for k, v in header.items():
        c.drawString(x, y, f"{k}: {v}")
        y -= 5.2 * mm
    c.drawString(x, y, "Gerado em " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                 + " — Osteon Viewer (clean-room), unidades em mm")
    y -= 8 * mm

    # imagens lado a lado
    img_w = (W - 2 * x - 6 * mm) / max(1, len(images)) if images else 0
    img_h = 60 * mm
    ix = x
    for caption, png in images:
        try:
            c.drawImage(ImageReader(png), ix, y - img_h, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor='n', mask='auto')
        except Exception:
            pass
        c.setFont("Helvetica", 8); c.setFillColorRGB(0.4, 0.43, 0.48)
        c.drawString(ix, y - img_h - 4 * mm, caption)
        ix += img_w + 6 * mm
    if images:
        y -= img_h + 10 * mm

    c.setFont("Helvetica-Bold", 12); c.setFillColorRGB(0.08, 0.1, 0.13)
    c.drawString(x, y, "Métricas"); y -= 6 * mm
    c.setFont("Helvetica", 10); c.setFillColorRGB(0.25, 0.28, 0.33)
    for label, value in metrics:
        c.drawString(x, y, f"{label}: {value}")
        y -= 5.2 * mm

    c.setFont("Helvetica", 7.5); c.setFillColorRGB(0.5, 0.53, 0.58)
    c.drawString(x, 12 * mm, "Ferramenta de visualização e estudo — não é software médico certificado para diagnóstico.")
    c.showPage()
    c.save()
