"""Infraestrutura de visão/captura do Maestro.

A camada de visão é deliberadamente separada do núcleo do simulador.
Nesta etapa ela fornece captura de tela local e telemetria para diagnóstico;
não injeta entradas nem controla aplicativos externos.
"""

from .capture_controller import CaptureController, CaptureStatus

__all__ = ["CaptureController", "CaptureStatus"]
