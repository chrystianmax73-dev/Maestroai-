"""Orquestração agnóstica de UI do pipeline do Maestro."""
from __future__ import annotations
import uuid
from typing import Optional
from .pipeline_models import PerceptionSnapshot, TacticalDecision, TacticalOption
from .recording import SessionRecorder
from .tactical_engine import TacticalEngine
from .maestro_grid_env_v2 import GameState, MaestroGridEnv

class ResearchPipeline:
    def __init__(self, env: MaestroGridEnv, recorder: Optional[SessionRecorder] = None):
        self.env = env
        self.tactics = TacticalEngine(env)
        self.recorder = recorder
        self.last_perception: Optional[PerceptionSnapshot] = None

    def decide(self, state: GameState, perception: Optional[PerceptionSnapshot] = None) -> Optional[TacticalDecision]:
        candidates = self.tactics.evaluate(state, self.env)
        if not candidates:
            return None
        best = candidates[0]
        decision = TacticalDecision(
            action={"type": best.action.type.value, "actor_id": best.action.actor_id, "target_id": best.action.target_id, "target_cell": best.action.target_cell},
            label=best.label, score=best.score, rationale=best.rationale,
            alternatives=[TacticalOption(c.label, c.score, c.rationale, {"type": c.action.type.value, "actor_id": c.action.actor_id, "target_id": c.action.target_id, "target_cell": c.action.target_cell}) for c in candidates],
            decision_id=uuid.uuid4().hex,
        )
        self.last_perception = perception
        if self.recorder:
            self.recorder.record(perception=perception, game_state=state, candidates=candidates, decision=decision)
        return decision

    def observe_and_decide(self, perception: PerceptionSnapshot, state: Optional[GameState] = None) -> Optional[TacticalDecision]:
        """Ponto de entrada para um adapter Android/replay já convertido em GameState."""
        return self.decide(state, perception) if state is not None else None
