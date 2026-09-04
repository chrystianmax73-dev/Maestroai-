"""Percepção visual leve e determinística para frames de futebol.

A camada não tenta "adivinhar" uma ação. Ela transforma uma imagem em
observações estruturadas: probabilidade de gramado, linhas claras, zonas com
cores de uniforme e candidato de bola. Isso permite ao Maestro saber quando
a imagem parece um campo antes de qualquer decisão do agente.

O algoritmo usa amostragem de pixels e regras de cor, sem rede e sem modelos
externos. É deliberadamente conservador: baixa confiança produz
``uncertain=True`` em vez de inventar um estado.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from typing import Callable, Dict, Tuple


@dataclass(frozen=True)
class PerceptionResult:
    width: int
    height: int
    field_confidence: float
    field_bbox: Tuple[float, float, float, float]
    white_line_ratio: float
    bright_blob_ratio: float
    dark_blob_ratio: float
    team_color_a: float
    team_color_b: float
    ball_x: float
    ball_y: float
    ball_confidence: float
    scene_confidence: float
    uncertain: bool

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["field_bbox"] = list(self.field_bbox)
        return data


class ScreenPerception:
    """Extrai sinais visuais básicos de uma imagem de futebol.

    ``pixel_at`` deve retornar ``(r, g, b)``. O mesmo algoritmo pode ser
    usado no desktop com fixtures sintéticos e no Android com ``Bitmap``.
    """

    def __init__(self, sample_cols: int = 48, sample_rows: int = 27):
        self.sample_cols = max(8, int(sample_cols))
        self.sample_rows = max(8, int(sample_rows))

    @staticmethod
    def _green(r: int, g: int, b: int) -> bool:
        return g >= 65 and g > r * 1.10 and g > b * 1.08 and (g - r) >= 12

    @staticmethod
    def _white(r: int, g: int, b: int) -> bool:
        return min(r, g, b) >= 190 and max(r, g, b) - min(r, g, b) <= 42

    @staticmethod
    def _bright(r: int, g: int, b: int) -> bool:
        return min(r, g, b) >= 205

    @staticmethod
    def _dark(r: int, g: int, b: int) -> bool:
        return max(r, g, b) <= 55

    @staticmethod
    def _color_a(r: int, g: int, b: int) -> bool:
        # Sinal genérico para uniforme quente/vermelho/laranja.
        return r >= 115 and r > g * 1.28 and r > b * 1.20

    @staticmethod
    def _color_b(r: int, g: int, b: int) -> bool:
        # Sinal genérico para uniforme frio/azul/roxo.
        return b >= 105 and b > r * 1.18 and b > g * 1.08

    def analyze(self, width: int, height: int,
                pixel_at: Callable[[int, int], Tuple[int, int, int]]) -> PerceptionResult:
        width = int(width)
        height = int(height)
        green = white = bright = dark = color_a = color_b = 0
        samples = 0
        bright_points = []
        green_points = []

        for gy in range(self.sample_rows):
            y = min(height - 1, int((gy + 0.5) * height / self.sample_rows))
            for gx in range(self.sample_cols):
                x = min(width - 1, int((gx + 0.5) * width / self.sample_cols))
                r, g, b = pixel_at(x, y)
                samples += 1
                if self._green(r, g, b):
                    green += 1
                    green_points.append((x, y))
                if self._white(r, g, b):
                    white += 1
                if self._bright(r, g, b):
                    bright += 1
                    # Candidato de bola: branco isolado dentro de uma cena
                    # predominantemente verde. A pontuação final ainda é baixa
                    # se houver branco demais (placares/menus, por exemplo).
                    bright_points.append((x, y))
                if self._dark(r, g, b):
                    dark += 1
                if self._color_a(r, g, b):
                    color_a += 1
                if self._color_b(r, g, b):
                    color_b += 1

        def ratio(n: int) -> float:
            return n / float(max(1, samples))

        field_conf = min(1.0, ratio(green) * 1.55)
        white_ratio = ratio(white)
        bright_ratio = ratio(bright)
        dark_ratio = ratio(dark)
        a_ratio = ratio(color_a)
        b_ratio = ratio(color_b)

        if green_points:
            xs = [p[0] for p in green_points]
            ys = [p[1] for p in green_points]
            bbox = (min(xs) / width, min(ys) / height,
                    max(xs) / width, max(ys) / height)
        else:
            bbox = (0.0, 0.0, 0.0, 0.0)

        # Uma bola de futebol tende a ser pequena, clara e isolada. Como a
        # amostragem é grosseira, usamos distância ao centro de outros pontos
        # claros para penalizar grandes áreas brancas.
        ball_x = ball_y = 0.0
        ball_conf = 0.0
        if bright_points and field_conf >= 0.35:
            best = None
            for x, y in bright_points:
                neighbors = 0
                for ox, oy in bright_points:
                    if abs(x - ox) <= max(1, width // 12) and abs(y - oy) <= max(1, height // 12):
                        neighbors += 1
                isolation = 1.0 / max(1, neighbors)
                score = isolation * (0.35 + field_conf * 0.65)
                if best is None or score > best[0]:
                    best = (score, x, y)
            if best is not None:
                ball_conf = min(1.0, best[0] * 2.2)
                ball_x = best[1] / width
                ball_y = best[2] / height

        # Confiança de cena: campo verde + alguma geometria clara, sem exigir
        # que todos os jogos tenham a mesma paleta.
        scene_conf = min(1.0, field_conf * 0.75 + min(1.0, white_ratio * 8.0) * 0.15 + min(1.0, (a_ratio + b_ratio) * 8.0) * 0.10)
        uncertain = scene_conf < 0.45 or field_conf < 0.30

        return PerceptionResult(
            width=width,
            height=height,
            field_confidence=round(field_conf, 4),
            field_bbox=tuple(round(v, 4) for v in bbox),
            white_line_ratio=round(white_ratio, 4),
            bright_blob_ratio=round(bright_ratio, 4),
            dark_blob_ratio=round(dark_ratio, 4),
            team_color_a=round(a_ratio, 4),
            team_color_b=round(b_ratio, 4),
            ball_x=round(ball_x, 4),
            ball_y=round(ball_y, 4),
            ball_confidence=round(ball_conf, 4),
            scene_confidence=round(scene_conf, 4),
            uncertain=uncertain,
        )
