"""Execution boundary for Maestro-controlled environments.

The decision engine produces an Action; an Executor applies it to an
environment owned by Maestro. External-app input adapters are intentionally
outside this module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..maestro_grid_env_v2 import Action, MaestroGridEnv


class Executor(ABC):
    """Stable execution boundary used by autonomous loops."""

    @abstractmethod
    def execute(self, action: Action) -> Any:
        """Apply an action and return the environment result."""
        raise NotImplementedError


class SimulatorExecutor(Executor):
    """Execute actions directly in the controlled Maestro simulator."""

    def __init__(self, env: MaestroGridEnv):
        self.env = env

    def execute(self, action: Action) -> Any:
        return self.env.step(action)
