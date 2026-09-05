"""Infraestrutura de visão do Maestro.

Esta camada é deliberadamente independente da origem do frame:

    FrameSource -> ScreenPerception.analyze() -> PerceptionResult

`ScreenPerception` não sabe nada sobre Kivy, Android, MediaProjection
ou overlay — só recebe (largura, altura, pixel_at) e devolve dados.

`FrameSource` (frame_source.py) é o contrato genérico de origem de
frame, com implementações sintética e por arquivo local — nenhuma
delas depende de Android nem captura tela real.

`CaptureController` (capture_controller.py) é um adapter Android para
MediaProjection. Ele existe no repositório mas NÃO é importado pelo
app compilado nesta build (ver README/ARCHITECTURE.md) — é o ponto de
integração isolado para uma eventual origem de frame real no futuro,
implementado seguindo o mesmo contrato de FrameSource.
"""

from .screen_perception import ScreenPerception, PerceptionResult
from .frame_source import FrameSource, Frame, SyntheticFrameSource, FileFrameSource

__all__ = [
    "ScreenPerception",
    "PerceptionResult",
    "FrameSource",
    "Frame",
    "SyntheticFrameSource",
    "FileFrameSource",
]
