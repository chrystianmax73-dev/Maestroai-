"""Execution boundary for Maestro-controlled environments.

The decision engine produces an Action; an Executor is responsible for
applying that action to an environment that Maestro owns and controls.
External-app input adapters are intentionally not part of this module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..maestro_grid_env_v2 import Action, MaestroGridEnv


class Executor(ABC):
    """Abstract execution boundary used by autonomous loops."""

    @abstractmethod
    def execute(self, action: Action) -> Any:
        """Apply *action* and return the environment result."""
        raise NotImplementedError


class SimulatorExecutor(Executor):
    """Executes actions directly in MaestroGridEnv."""

    def __init__(self, env: MaestroGridEnv):
        self.env = env

    def execute(self, action: Action) -> Any:
        return self.env.step(action)
