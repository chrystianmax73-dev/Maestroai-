"""
FrameSource — abstração genérica de origem de frames para a camada de
visão do Maestro.

Esta é a peça central da arquitetura pedida: `ScreenPerception` (em
`screen_perception.py`) não precisa saber de onde um frame vem — só
recebe largura, altura e uma função de acesso a pixel. `FrameSource` é
o contrato que qualquer origem de frame implementa.

Implementações fornecidas aqui são 100% offline e não dependem de
Android, jnius, MediaProjection ou qualquer captura de tela real:

- `SyntheticFrameSource`: gera frames sintéticos determinísticos
  (útil para testes e para diagnosticar a análise sem precisar de
  nenhuma imagem real).
- `FileFrameSource`: lê frames de imagens fornecidas explicitamente
  pelo usuário/desenvolvedor no disco (diagnóstico manual).

Um adapter para captura real de tela Android (`AndroidFrameSource` ou
equivalente) NÃO está implementado aqui — esse é exatamente o ponto de
integração isolado mencionado no README/ARCHITECTURE.md. Qualquer
implementação futura desse adapter deveria seguir este mesmo contrato
(`start()` / `get_frame()` / `stop()`), mas isso está fora do escopo
do que este módulo entrega hoje.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, Tuple


@dataclass(frozen=True)
class Frame:
    """Um frame genérico: dimensões + função de acesso a pixel (r, g, b)."""

    width: int
    height: int
    pixel_at: Callable[[int, int], Tuple[int, int, int]]


class FrameSource(ABC):
    """Contrato genérico de origem de frames.

    Qualquer implementação (sintética, arquivo local, ou futuramente
    uma captura real) segue este mesmo ciclo de vida simples:
    start() -> get_frame() [0..N vezes] -> stop().
    """

    @abstractmethod
    def start(self) -> None:
        """Prepara a origem para fornecer frames. Idempotente."""

    @abstractmethod
    def get_frame(self) -> Optional[Frame]:
        """Retorna o frame atual, ou None se não houver nenhum disponível."""

    @abstractmethod
    def stop(self) -> None:
        """Libera qualquer recurso. Idempotente."""

    @property
    def available(self) -> bool:
        """Se esta origem pode ser usada no ambiente atual."""
        return True


class SyntheticFrameSource(FrameSource):
    """Gera uma cena sintética determinística (campo verde + bola +
    dois blocos de cor de time), útil para testar a análise visual sem
    depender de nenhuma imagem real."""

    def __init__(self, width: int = 960, height: int = 540, seed: int = 0):
        self.width = width
        self.height = height
        self.seed = seed
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def get_frame(self) -> Optional[Frame]:
        if not self._running:
            return None

        w, h = self.width, self.height
        offset = (self.seed * 37) % 40

        def pixel_at(x: int, y: int) -> Tuple[int, int, int]:
            if 120 < x < w - 120 and 70 < y < h - 50:
                if abs(x - w // 2) < 3 or abs(y - h // 2) < 3:
                    return (235, 235, 235)  # linhas do campo
                bx, by = w // 2 + offset, h // 2 - offset // 2
                if abs(x - bx) < 9 and abs(y - by) < 9:
                    return (245, 245, 245)  # bola
                if 260 < x < 300 and 180 < y < 235:
                    return (205, 45, 35)  # time A
                if 650 < x < 690 and 330 < y < 385:
                    return (35, 75, 205)  # time B
                return (42, 145, 62)  # grama
            return (28, 30, 34)  # fora de campo

        return Frame(width=w, height=h, pixel_at=pixel_at)


class FileFrameSource(FrameSource):
    """Lê frames de uma lista de imagens fornecidas explicitamente no
    disco, para diagnóstico manual (sem nenhuma captura automática de
    tela). Requer Pillow; ausência de Pillow apenas torna a origem
    indisponível (`available == False`), nunca derruba a aplicação."""

    def __init__(self, paths: list[str]):
        self.paths = list(paths)
        self._index = 0
        self._running = False
        try:
            from PIL import Image  # noqa: F401
            self._pil_available = True
        except ImportError:
            self._pil_available = False

    @property
    def available(self) -> bool:
        return self._pil_available and bool(self.paths)

    def start(self) -> None:
        self._running = True
        self._index = 0

    def stop(self) -> None:
        self._running = False

    def get_frame(self) -> Optional[Frame]:
        if not self._running or not self.available or self._index >= len(self.paths):
            return None
        from PIL import Image

        img = Image.open(self.paths[self._index]).convert("RGB")
        self._index += 1
        pixels = img.load()
        w, h = img.size

        def pixel_at(x: int, y: int) -> Tuple[int, int, int]:
            return pixels[x, y]

        return Frame(width=w, height=h, pixel_at=pixel_at)
