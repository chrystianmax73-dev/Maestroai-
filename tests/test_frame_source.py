"""Testes da abstração genérica FrameSource — sem nenhuma dependência
de Android/captura real de tela."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro.vision import ScreenPerception, SyntheticFrameSource, FileFrameSource


def test_synthetic_frame_source_produces_analyzable_frames():
    src = SyntheticFrameSource(width=640, height=360, seed=1)
    assert src.get_frame() is None, "não deve produzir frame antes de start()"
    src.start()
    frame = src.get_frame()
    assert frame is not None
    assert frame.width == 640 and frame.height == 360
    result = ScreenPerception().analyze(frame.width, frame.height, frame.pixel_at)
    assert result.field_confidence > 0.3
    src.stop()
    assert src.get_frame() is None, "não deve produzir frame depois de stop()"
    print("TESTE FRAME SOURCE 1 OK — SyntheticFrameSource integra com ScreenPerception")


def test_synthetic_frame_source_is_deterministic_per_seed():
    a = SyntheticFrameSource(seed=5)
    b = SyntheticFrameSource(seed=5)
    a.start(); b.start()
    fa, fb = a.get_frame(), b.get_frame()
    ra = ScreenPerception().analyze(fa.width, fa.height, fa.pixel_at)
    rb = ScreenPerception().analyze(fb.width, fb.height, fb.pixel_at)
    assert ra.to_dict() == rb.to_dict()
    print("TESTE FRAME SOURCE 2 OK — mesma seed produz a mesma análise")


def test_file_frame_source_unavailable_without_files_is_safe():
    src = FileFrameSource(paths=[])
    assert src.available is False
    src.start()
    assert src.get_frame() is None
    src.stop()
    print("TESTE FRAME SOURCE 3 OK — FileFrameSource sem arquivos não quebra, só fica indisponível")


def test_frame_source_is_abstract_contract():
    from maestro.vision import FrameSource
    import inspect
    assert inspect.isabstract(FrameSource)
    for method in ("start", "get_frame", "stop"):
        assert hasattr(FrameSource, method)
    print("TESTE FRAME SOURCE 4 OK — FrameSource é um contrato abstrato (start/get_frame/stop)")


if __name__ == "__main__":
    test_synthetic_frame_source_produces_analyzable_frames()
    test_synthetic_frame_source_is_deterministic_per_seed()
    test_file_frame_source_unavailable_without_files_is_safe()
    test_frame_source_is_abstract_contract()
    print("\n=== TODOS OS TESTES DE FRAME SOURCE PASSARAM ===")
