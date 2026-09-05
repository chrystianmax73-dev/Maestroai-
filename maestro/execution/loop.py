"""Autonomous decision -> execution loop for the controlled simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..heuristic_agent import HeuristicAgent
from ..maestro_grid_env_v2 import Action, GameState, MaestroGridEnv
from .executor import Executor


@dataclass(frozen=True)
class DecisionRecord:
    """Serializable record of one autonomous cycle."""

    step: int
    action: Action
    valid: bool
    reward: float
    done: bool
    info: dict[str, Any]


class AutonomousLoop:
    """Coordinates agent decisions and an injected executor.

    The loop owns no UI state and makes no assumptions about how frames are
    obtained. This keeps Android presentation, perception and execution
    adapters replaceable without changing the decision logic.
    """

    def __init__(
        self,
        env: MaestroGridEnv,
        agent: HeuristicAgent,
        executor: Executor,
        on_cycle: Optional[Callable[[DecisionRecord], None]] = None,
    ) -> None:
        self.env = env
        self.agent = agent
        self.executor = executor
        self.on_cycle = on_cycle
        self.state: Optional[GameState] = None
        self.done = False
        self.paused = False
        self.history: list[DecisionRecord] = []

    def reset(self) -> GameState:
        self.state, _ = self.env.reset()
        self.done = False
        self.paused = False
        self.history.clear()
        return self.state

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self.done = True

    def tick(self) -> Optional[DecisionRecord]:
        """Run exactly one decision/execution cycle."""
        if self.done or self.paused:
            return None
        if self.state is None:
            self.reset()

        action = self.agent.decide(self.state, self.env)
        if action is None:
            self.done = True
            return None

        state, reward, done, info = self.executor.execute(action)
        self.state = state
        self.done = done
        record = DecisionRecord(
            step=state.time_step,
            action=action,
            valid=bool(info.get("valid", False)),
            reward=float(reward),
            done=bool(done),
            info=dict(info),
        )
        self.history.append(record)
        if self.on_cycle is not None:
            self.on_cycle(record)
        return record

    def run(self, max_cycles: Optional[int] = None) -> list[DecisionRecord]:
        """Run until done or max_cycles is reached."""
        cycles = 0
        while not self.done and not self.paused:
            if max_cycles is not None and cycles >= max_cycles:
                break
            self.tick()
            cycles += 1
        return list(self.history)
