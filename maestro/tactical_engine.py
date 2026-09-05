"""Tactical decision analysis for Maestro's controlled simulator.

The TacticalEngine is deliberately non-executing: it inspects a public
GameState and returns ranked candidate Actions with scores. Execution remains
owned by the simulator Executor/AutonomousLoop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .maestro_grid_env_v2 import Action, ActionType, GameState, MaestroGridEnv, Player

_FINISHING_ZONE_FACTOR = 10 / 12
_HIGH_PRESSURE = 0.55


@dataclass(frozen=True)
class TacticalCandidate:
    """One possible decision and its normalized heuristic score."""

    action: Action
    score: float
    label: str
    rationale: str


class TacticalEngine:
    """Rank possible actions without executing any of them."""

    def __init__(self, env: Optional[MaestroGridEnv] = None):
        self.env = env

    def evaluate(self, state: GameState, env: Optional[MaestroGridEnv] = None) -> list[TacticalCandidate]:
        runtime = env or self.env
        if runtime is None:
            raise ValueError("TacticalEngine.evaluate requires a MaestroGridEnv")

        owner = state.owner()
        if owner is None:
            return []

        candidates: list[TacticalCandidate] = []
        pressure = state.pressure_on(owner.id)

        if self._in_finishing_zone(state, owner) and pressure < _HIGH_PRESSURE:
            candidates.append(TacticalCandidate(
                Action(type=ActionType.FINALIZAR, actor_id=owner.id),
                self._clamp(0.90 - pressure * 0.30),
                "FINALIZAR",
                "zona de finalização com pressão controlada",
            ))

        for teammate in state.team_of(owner.id):
            if teammate.id == owner.id:
                continue
            progress = self._territorial_progress(state, owner.cell, teammate.cell)
            lane = state.passing_lane_open(owner.id, teammate.id)
            marked = state.is_marked(teammate.id)
            score = 0.35 + progress * 0.60 + (0.15 if lane else -0.20) - (0.15 if marked else 0)
            candidates.append(TacticalCandidate(
                Action(type=ActionType.PASSE, actor_id=owner.id, target_id=teammate.id),
                self._clamp(score),
                "PASSE",
                f"linha={'aberta' if lane else 'fechada'}; {'marcado' if marked else 'livre'}",
            ))

            open_space = state.open_space_around(teammate.id)
            if progress > 0 and owner.cell[1] in (0, 1, state.grid_rows - 2, state.grid_rows - 1):
                score = 0.30 + progress * 0.50 + open_space * 0.20
                candidates.append(TacticalCandidate(
                    Action(type=ActionType.CRUZAMENTO, actor_id=owner.id, target_id=teammate.id),
                    self._clamp(score),
                    "CRUZAMENTO",
                    "progressão lateral com espaço disponível",
                ))

        direction = 1 if owner.team == "A" else -1
        col, row = owner.cell
        for reach in (3, 4):
            target_col = col + direction * reach
            for delta_row in (-1, 0, 1):
                target_row = row + delta_row
                if not (0 <= target_col < state.grid_cols and 0 <= target_row < state.grid_rows):
                    continue
                progress = self._territorial_progress(state, owner.cell, (target_col, target_row))
                if progress <= 0:
                    continue
                score = 0.15 + progress * 0.55 + (0.15 if pressure > _HIGH_PRESSURE else 0)
                candidates.append(TacticalCandidate(
                    Action(type=ActionType.LANCAMENTO, actor_id=owner.id, target_cell=(target_col, target_row)),
                    self._clamp(score),
                    "LANCAMENTO",
                    "ganho territorial de longa distância",
                ))

        for delta_col, delta_row in ((direction, -1), (direction, 0), (direction, 1), (0, -1), (0, 1)):
            target = (col + delta_col, row + delta_row)
            if not (0 <= target[0] < state.grid_cols and 0 <= target[1] < state.grid_rows):
                continue
            if state.cell_distance(owner.cell, target) > runtime.MAX_DRIBBLE_DISTANCE:
                continue
            progress = self._territorial_progress(state, owner.cell, target)
            score = 0.20 + progress * 0.40 - pressure * 0.30
            candidates.append(TacticalCandidate(
                Action(type=ActionType.DRIBLE, actor_id=owner.id, target_cell=target),
                self._clamp(score),
                "DRIBLE",
                "progressão curta ajustada à pressão",
            ))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def best(self, state: GameState, env: Optional[MaestroGridEnv] = None) -> Optional[TacticalCandidate]:
        ranked = self.evaluate(state, env)
        return ranked[0] if ranked else None

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _territorial_progress(state: GameState, from_cell, to_cell) -> float:
        direction = 1 if state.possession == "A" else -1
        return ((to_cell[0] - from_cell[0]) * direction) / state.grid_cols

    @staticmethod
    def _in_finishing_zone(state: GameState, owner: Player) -> bool:
        if owner.team == "A":
            return owner.cell[0] >= state.grid_cols * _FINISHING_ZONE_FACTOR
        return owner.cell[0] <= state.grid_cols * (1 - _FINISHING_ZONE_FACTOR)
