from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro.vision.screen_perception import ScreenPerception


def synthetic_scene(width=960, height=540):
    def pixel(x, y):
        if 120 < x < 840 and 70 < y < 490:
            if abs(x - 480) < 3 or abs(y - 280) < 3:
                return (235, 235, 235)
            if 735 < x < 752 and 260 < y < 277:
                return (245, 245, 245)
            if 260 < x < 300 and 180 < y < 235:
                return (205, 45, 35)
            if 650 < x < 690 and 330 < y < 385:
                return (35, 75, 205)
            return (42, 145, 62)
        return (28, 30, 34)
    return width, height, pixel


def test_detects_field_and_scene():
    width, height, pixel = synthetic_scene()
    result = ScreenPerception().analyze(width, height, pixel)
    assert result.field_confidence > 0.55
    assert result.scene_confidence > 0.45
    assert result.white_line_ratio > 0.0
    assert not result.uncertain


def test_detects_two_uniform_color_signals():
    width, height, pixel = synthetic_scene()
    result = ScreenPerception().analyze(width, height, pixel)
    assert result.team_color_a > 0.0
    assert result.team_color_b > 0.0


def test_is_conservative_on_non_football_scene():
    def pixel(x, y):
        return (35, 35, 40)
    result = ScreenPerception().analyze(960, 540, pixel)
    assert result.field_confidence == 0.0
    assert result.ball_confidence == 0.0
    assert result.uncertain


def test_is_deterministic():
    width, height, pixel = synthetic_scene()
    a = ScreenPerception().analyze(width, height, pixel).to_dict()
    b = ScreenPerception().analyze(width, height, pixel).to_dict()
    assert a == b


if __name__ == "__main__":
    test_detects_field_and_scene()
    test_detects_two_uniform_color_signals()
    test_is_conservative_on_non_football_scene()
    test_is_deterministic()
    print("=== TODOS OS TESTES DE PERCEPÇÃO PASSARAM ===")
