"""Cefalometria: pontos e análises angulares no plano sagital (A-P × S-I).
Funções puras (sem GUI/VTK) — recebem pontos em mm e retornam ângulos em graus."""
from __future__ import annotations
import math

# Pontos suportados (sigla, nome)
POINTS = [
    ("S", "Sela"),
    ("N", "Násio"),
    ("A", "Ponto A"),
    ("B", "Ponto B"),
    ("Go", "Gônio"),
    ("Gn", "Gnátio"),
    ("Me", "Mento"),
    ("Po", "Pório"),
    ("Or", "Orbitário"),
]

# Análises: (sigla, tipo, args, descrição)
#  tipo 'vertex' -> ângulo em P1 entre P0 e P2  (args = [P0, P1, P2])
#  tipo 'lines'  -> ângulo entre as retas P0P1 e P2P3 (args = [P0,P1,P2,P3])
#  tipo 'diff'   -> diferença de duas análises (args = [nomeA, nomeB])
ANALYSES = [
    ("SNA", "vertex", ["S", "N", "A"], "Posição ântero-posterior da maxila"),
    ("SNB", "vertex", ["S", "N", "B"], "Posição ântero-posterior da mandíbula"),
    ("ANB", "diff", ["SNA", "SNB"], "Relação maxilo-mandibular"),
    ("SN-GoGn", "lines", ["S", "N", "Go", "Gn"], "Inclinação do plano mandibular (base craniana)"),
    ("FMA", "lines", ["Po", "Or", "Go", "Me"], "Plano de Frankfurt × plano mandibular"),
]


def _angle_vertex(p0, p1, p2):
    v1 = (p0[0] - p1[0], p0[1] - p1[1])
    v2 = (p2[0] - p1[0], p2[1] - p1[1])
    return _angle_vecs(v1, v2)


def _angle_lines(p0, p1, p2, p3):
    v1 = (p1[0] - p0[0], p1[1] - p0[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    a = _angle_vecs(v1, v2)
    return min(a, 180.0 - a)   # ângulo agudo entre retas


def _angle_vecs(v1, v2):
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(c))


def compute(landmarks: dict) -> dict:
    """landmarks: {sigla: (ap_mm, si_mm)}. Retorna {sigla_análise: graus}."""
    out = {}
    for name, kind, args, _desc in ANALYSES:
        try:
            if kind == "vertex":
                if all(a in landmarks for a in args):
                    out[name] = _angle_vertex(*[landmarks[a] for a in args])
            elif kind == "lines":
                if all(a in landmarks for a in args):
                    out[name] = _angle_lines(*[landmarks[a] for a in args])
            elif kind == "diff":
                a, b = args
                if a in out and b in out:
                    out[name] = out[a] - out[b]
        except Exception:
            pass
    return out


# Valores de referência (adulto, aprox.) apenas para exibição comparativa.
NORMS = {
    "SNA": (82.0, 2.0),
    "SNB": (80.0, 2.0),
    "ANB": (2.0, 2.0),
    "SN-GoGn": (32.0, 5.0),
    "FMA": (25.0, 4.0),
}
