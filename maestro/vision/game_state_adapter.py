"""Adaptação de percepção visual para o GameState discreto do simulador."""
from __future__ import annotations
from typing import Optional
from ..maestro_grid_env_v2 import Ball, GameState, Player
from ..pipeline_models import PerceptionSnapshot

class GameStateAdapter:
    """Mapeia coordenadas normalizadas para a grade do Maestro."""
    def __init__(self, grid_cols: int = 12, grid_rows: int = 8):
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows

    def to_state(self, perception: PerceptionSnapshot, previous: Optional[GameState] = None) -> Optional[GameState]:
        if perception.uncertain and previous is None:
            return None
        if previous is not None:
            return self._update_previous(perception, previous)
        players = list(perception.players)
        if len(players) < 2 or perception.ball is None:
            return None
        team_a, team_b = [], []
        for pid, observed in enumerate(players):
            player = Player(pid, "A" if observed.team == "A" else "B", self._cell(observed.x, observed.y))
            (team_a if player.team == "A" else team_b).append(player)
        if not team_a or not team_b:
            return None
        ball_cell = self._cell(perception.ball.x, perception.ball.y)
        owner = self._nearest_owner(ball_cell, team_a + team_b)
        return GameState(self.grid_cols, self.grid_rows, Ball(ball_cell, owner.id if owner else None), team_a, team_b, owner.team if owner else "A")

    def _update_previous(self, perception: PerceptionSnapshot, previous: GameState) -> GameState:
        ball_cell = previous.ball.cell if perception.ball is None else self._cell(perception.ball.x, perception.ball.y)
        return GameState(previous.grid_cols, previous.grid_rows, Ball(ball_cell, previous.ball.owner_id), list(previous.team_a), list(previous.team_b), previous.possession, previous.time_step, previous.half)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return (max(0, min(self.grid_cols - 1, int(float(x) * self.grid_cols))), max(0, min(self.grid_rows - 1, int(float(y) * self.grid_rows))))

    @staticmethod
    def _nearest_owner(cell, players):
        return min(players, key=lambda p: ((p.cell[0] - cell[0]) ** 2 + (p.cell[1] - cell[1]) ** 2) ** 0.5) if players else None
