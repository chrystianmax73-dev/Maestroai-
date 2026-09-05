"""High-level orchestration for perception, tactics and controlled execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..execution import AutonomousLoop, DecisionRecord, SimulatorExecutor
from ..heuristic_agent import HeuristicAgent
from ..maestro_grid_env_v2 import GameState, MaestroGridEnv
from ..tactical_engine import TacticalCandidate, TacticalEngine
from ..vision.frame_source import Frame, FrameSource
from ..vision.screen_perception import PerceptionResult, ScreenPerception


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Read-only state suitable for UI/diagnostic consumers."""

    running: bool
    paused: bool
    step: int
    perception: Optional[PerceptionResult]
    candidates: tuple[TacticalCandidate, ...] = field(default_factory=tuple)
    last_decision: Optional[DecisionRecord] = None
    error: Optional[str] = None


class MaestroRuntime:
    """Owns the safe internal pipeline without coupling it to Kivy.

    The runtime can run the controlled simulator autonomously and can also
    inspect explicitly supplied frames through a FrameSource. It never sends
    input to another application.
    """

    def __init__(self, seed: int = 42, max_steps: int = 500, frame_source: Optional[FrameSource] = None):
        self.env = MaestroGridEnv(seed=seed, max_steps=max_steps)
        self.agent = HeuristicAgent(seed=seed)
        self.executor = SimulatorExecutor(self.env)
        self.loop = AutonomousLoop(self.env, self.agent, self.executor, on_cycle=self._on_cycle)
        self.tactics = TacticalEngine(self.env)
        self.perception = ScreenPerception()
        self.frame_source = frame_source
        self.latest_perception: Optional[PerceptionResult] = None
        self.latest_candidates: list[TacticalCandidate] = []
        self.last_decision: Optional[DecisionRecord] = None
        self.last_error: Optional[str] = None

    def start(self) -> GameState:
        self.last_error = None
        return self.loop.reset()

    def pause(self) -> None:
        self.loop.pause()

    def resume(self) -> None:
        self.loop.resume()

    def stop(self) -> None:
        self.loop.stop()
        if self.frame_source is not None:
            self.frame_source.stop()

    @property
    def running(self) -> bool:
        return not self.loop.done

    def analyze_current_state(self) -> list[TacticalCandidate]:
        if self.loop.state is None:
            self.start()
        assert self.loop.state is not None
        self.latest_candidates = self.tactics.evaluate(self.loop.state, self.env)
        return list(self.latest_candidates)

    def tick(self) -> Optional[DecisionRecord]:
        try:
            record = self.loop.tick()
            self.last_decision = record
            if self.loop.state is not None:
                self.latest_candidates = self.tactics.evaluate(self.loop.state, self.env)
            return record
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def process_frame(self, frame: Frame) -> PerceptionResult:
        """Analyze an explicitly supplied frame; no execution follows."""
        try:
            result = self.perception.analyze(frame.width, frame.height, frame.pixel_at)
            self.latest_perception = result
            self.last_error = None
            return result
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    def poll_frame_source(self) -> Optional[PerceptionResult]:
        if self.frame_source is None:
            return None
        try:
            frame = self.frame_source.get_frame()
            return self.process_frame(frame) if frame is not None else None
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def snapshot(self) -> RuntimeSnapshot:
        step = self.loop.state.time_step if self.loop.state is not None else 0
        return RuntimeSnapshot(
            running=self.running,
            paused=self.loop.paused,
            step=step,
            perception=self.latest_perception,
            candidates=tuple(self.latest_candidates),
            last_decision=self.last_decision,
            error=self.last_error,
        )

    def _on_cycle(self, record: DecisionRecord) -> None:
        self.last_decision = record
