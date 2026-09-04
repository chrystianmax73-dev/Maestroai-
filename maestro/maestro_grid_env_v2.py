"""
MaestroGridEnv (v2)
====================
Ambiente de simulação de futebol em grade discreta, interface estilo
Gym (reset/step). Autocontido — nenhuma interação com processos
externos, jogos, captura de tela ou dispositivos.

Mudanças em relação à v1, após revisão de consistência:
1. Fonte única de verdade para posse: `_set_owner()` é o ÚNICO lugar
   que altera ball.owner_id, ball.cell e state.possession — sempre
   em conjunto. Nenhum resolver mexe nesses campos diretamente.
2. `_turnover_to_nearest_opponent()` usa a mesma `_set_owner()`.
3. DRIBLE tem limite explícito de distância (MAX_DRIBBLE_DISTANCE).
   Uma tentativa de drible além do limite é uma ação INVÁLIDA, não é
   silenciosamente recortada nem executada.
4. Todo step() registra `state_before` e `state_after` (snapshot leve
   e serializável) no info.
5. `evaluation_metrics()` agora distingue progressão BRUTA (soma dos
   deltas por step, pode se cancelar com posse alternando) de
   progressão LÍQUIDA (posição final da bola vs. posição inicial,
   medida uma única vez, não acumulada).
6. Ações inválidas (ator sem posse, alvo inválido, célula fora da
   grade, drible acima do limite) são detectadas ANTES de qualquer
   mutação de estado, sinalizadas explicitamente em info
   (`valid: False`, `reason: ...`), e não alteram o GameState.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

Cell = tuple[int, int]  # (col, row)


class ActionType(str, Enum):
    PASSE = "PASSE"
    LANCAMENTO = "LANCAMENTO"
    DRIBLE = "DRIBLE"
    FINALIZAR = "FINALIZAR"
    CRUZAMENTO = "CRUZAMENTO"


@dataclass
class Player:
    id: int
    team: str  # "A" ou "B"
    cell: Cell


@dataclass
class Ball:
    cell: Cell
    owner_id: Optional[int] = None


@dataclass
class GameState:
    grid_cols: int
    grid_rows: int
    ball: Ball
    team_a: list[Player]
    team_b: list[Player]
    possession: str
    time_step: int = 0
    half: int = 1

    def all_players(self) -> list[Player]:
        return self.team_a + self.team_b

    def player_by_id(self, pid: int) -> Player:
        for p in self.all_players():
            if p.id == pid:
                return p
        raise KeyError(f"player id {pid} não encontrado")

    def team_of(self, pid: int) -> list[Player]:
        p = self.player_by_id(pid)
        return self.team_a if p.team == "A" else self.team_b

    def opponents_of(self, pid: int) -> list[Player]:
        p = self.player_by_id(pid)
        return self.team_b if p.team == "A" else self.team_a

    def owner(self) -> Optional[Player]:
        if self.ball.owner_id is None:
            return None
        return self.player_by_id(self.ball.owner_id)

    @staticmethod
    def cell_distance(a: Cell, b: Cell) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def pressure_on(self, pid: int, radius: float = 2.0) -> float:
        p = self.player_by_id(pid)
        opps = self.opponents_of(pid)
        if not opps:
            return 0.0
        nearby = [self.cell_distance(p.cell, o.cell) for o in opps]
        nearby = [d for d in nearby if d <= radius]
        if not nearby:
            return 0.0
        closest = min(nearby)
        intensidade = max(0.0, 1.0 - (closest / radius))
        fator_quantidade = min(1.0, len(nearby) / 3)
        return round(min(1.0, intensidade * 0.7 + fator_quantidade * 0.3), 3)

    def is_marked(self, pid: int, threshold: float = 1.5) -> bool:
        p = self.player_by_id(pid)
        return any(
            self.cell_distance(p.cell, o.cell) <= threshold
            for o in self.opponents_of(pid)
        )

    def passing_lane_open(
        self, from_id: int, to_id: int, corridor_width: float = 0.75
    ) -> bool:
        a = self.player_by_id(from_id).cell
        b = self.player_by_id(to_id).cell
        opps = self.opponents_of(from_id)
        for o in opps:
            if self._point_segment_distance(o.cell, a, b) <= corridor_width:
                return False
        return True

    @staticmethod
    def _point_segment_distance(p: Cell, a: Cell, b: Cell) -> float:
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return GameState.cell_distance(p, a)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj = (ax + t * dx, ay + t * dy)
        return GameState.cell_distance(p, proj)

    def open_space_around(self, pid: int, radius: float = 2.0) -> float:
        p = self.player_by_id(pid)
        opps = self.opponents_of(pid)
        if not opps:
            return 1.0
        closest = min(self.cell_distance(p.cell, o.cell) for o in opps)
        return round(min(1.0, closest / radius), 3)


@dataclass
class Action:
    type: ActionType
    actor_id: int
    target_id: Optional[int] = None
    target_cell: Optional[Cell] = None


FINALIZACAO_COL_MIN_FACTOR = 10 / 12


class MaestroGridEnv:
    """Ambiente de futebol em grade discreta.

    Uso:
        env = MaestroGridEnv(seed=42)
        obs, info = env.reset()
        obs, reward, done, info = env.step(action)
    """

    MAX_DRIBBLE_DISTANCE = 1.5  # permite 1 célula ortogonal ou diagonal

    def __init__(
        self,
        grid_cols: int = 12,
        grid_rows: int = 8,
        players_per_team: int = 4,
        max_steps: int = 200,
        seed: Optional[int] = None,
    ):
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.players_per_team = players_per_team
        self.max_steps = max_steps
        self._rng = random.Random(seed)
        self.state: Optional[GameState] = None
        self._episode_stats = self._empty_stats()
        self._initial_ball_col: Optional[int] = None

    # -- API pública -------------------------------------------------------

    def seed(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def reset(self) -> tuple[GameState, dict]:
        self.state = self._build_initial_state()
        self._episode_stats = self._empty_stats()
        self._initial_ball_col = self.state.ball.cell[0]
        info = {"event": "reset"}
        return self.state, info

    def step(self, action: Action) -> tuple[GameState, float, bool, dict]:
        if self.state is None:
            raise RuntimeError("chame reset() antes de step()")

        state_before = self._snapshot()
        valid, reason = self._validate_action(action)

        if not valid:
            self.state.time_step += 1
            info = {
                "action": action.type.value,
                "actor": action.actor_id,
                "valid": False,
                "reason": reason,
                "state_before": state_before,
                "state_after": self._snapshot(),
            }
            self._update_stats(
                action, info, valid=False, decision_team=state_before["possession"]
            )
            info["episode_stats"] = dict(self._episode_stats)
            done = self.state.time_step >= self.max_steps
            return self.state, -0.02, done, info

        resolver = {
            ActionType.PASSE: self._resolve_passe,
            ActionType.LANCAMENTO: self._resolve_lancamento,
            ActionType.DRIBLE: self._resolve_drible,
            ActionType.FINALIZAR: self._resolve_finalizar,
            ActionType.CRUZAMENTO: self._resolve_cruzamento,
        }[action.type]

        reward, info = resolver(action)
        info["valid"] = True
        self.state.time_step += 1
        info["state_before"] = state_before

        # PARTIDA COMPLETA: gol não encerra mais o episódio.
        scoring_team = info.get("goal")
        if scoring_team in ("A", "B") and self.state.time_step < self.max_steps:
            conceding_team = "B" if scoring_team == "A" else "A"
            self._kickoff(conceding_team)
            info["kickoff_after_goal"] = conceding_team

        info["state_after"] = self._snapshot()
        done = self.state.time_step >= self.max_steps
        self._update_stats(
            action, info, valid=True, decision_team=state_before["possession"]
        )
        info["episode_stats"] = dict(self._episode_stats)
        return self.state, reward, done, info

    def evaluation_metrics(self) -> dict:
        """posse_pct_time_a/b: percentual de steps em que cada time
        estava com a bola no INÍCIO da decisão daquele step.
        finalizacao_sucesso_equivale_a_gol: contrato explícito deste
        ambiente — em FINALIZAR, success=True É, por definição, um gol.
        """
        s = self._episode_stats
        total_posse_steps = s["posse_steps_a"] + s["posse_steps_b"]
        posse_pct = (
            round(100 * s["posse_steps_a"] / total_posse_steps, 1)
            if total_posse_steps
            else 0.0
        )
        net_col_diff = self.state.ball.cell[0] - (self._initial_ball_col or 0)
        progressao_liquida = round(net_col_diff / self.grid_cols, 3)
        return {
            "posse_pct_time_a": posse_pct,
            "gols_marcados": s["gols_a"],
            "gols_sofridos": s["gols_b"],
            "perdas_de_posse": s["perdas_posse"],
            "chances_criadas": s["chances_criadas"],
            "acoes_invalidas": s["acoes_invalidas"],
            "progressao_territorial_liquida": progressao_liquida,
            "progressao_territorial_bruta_soma": round(
                s["progressao_territorial_soma"], 3
            ),
            "finalizacao_sucesso_equivale_a_gol": True,
        }

    # -- Construção de estado inicial ------------------------------------

    def _kickoff(self, possession_team: str) -> None:
        """Reinicia posições após um gol (kickoff), sem encerrar o
        episódio. Time que sofreu o gol fica com a bola.
        """
        s = self.state
        for p in s.team_a:
            p.cell = (
                self._rng.randrange(0, self.grid_cols // 2),
                self._rng.randrange(self.grid_rows),
            )
        for p in s.team_b:
            p.cell = (
                self._rng.randrange(self.grid_cols // 2, self.grid_cols),
                self._rng.randrange(self.grid_rows),
            )
        squad = s.team_a if possession_team == "A" else s.team_b
        new_owner = squad[0]
        s.ball.cell = new_owner.cell
        s.ball.owner_id = new_owner.id
        s.possession = possession_team

    def _build_initial_state(self) -> GameState:
        team_a, team_b = [], []
        pid = 0
        cols_a = self._rng.sample(
            range(0, self.grid_cols // 2),
            min(self.players_per_team, self.grid_cols // 2),
        )
        for c in cols_a:
            row = self._rng.randrange(self.grid_rows)
            team_a.append(Player(id=pid, team="A", cell=(c, row)))
            pid += 1
        cols_b = self._rng.sample(
            range(self.grid_cols // 2, self.grid_cols),
            min(self.players_per_team, self.grid_cols // 2),
        )
        for c in cols_b:
            row = self._rng.randrange(self.grid_rows)
            team_b.append(Player(id=pid, team="B", cell=(c, row)))
            pid += 1
        owner = team_a[0]
        ball = Ball(cell=owner.cell, owner_id=owner.id)
        return GameState(
            grid_cols=self.grid_cols,
            grid_rows=self.grid_rows,
            ball=ball,
            team_a=team_a,
            team_b=team_b,
            possession="A",
        )

    # -- Validação centralizada (ponto 6) --------------------------------

    def _cell_in_bounds(self, cell: Cell) -> bool:
        c, r = cell
        return 0 <= c < self.grid_cols and 0 <= r < self.grid_rows

    @staticmethod
    def _is_integer_cell(cell: Cell) -> bool:
        c, r = cell
        return isinstance(c, int) and isinstance(r, int)

    def _validate_action(self, action: Action) -> tuple[bool, str]:
        s = self.state
        try:
            actor = s.player_by_id(action.actor_id)
        except KeyError:
            return False, "ator inexistente"

        if action.actor_id != s.ball.owner_id:
            return False, "ator não possui a bola"

        if action.type in (ActionType.PASSE, ActionType.CRUZAMENTO):
            if action.target_id is None:
                return False, "sem jogador alvo"
            if action.target_id == actor.id:
                return False, "alvo igual ao ator"
            try:
                target = s.player_by_id(action.target_id)
            except KeyError:
                return False, "alvo inexistente"
            if target.team != actor.team:
                return False, "alvo não é companheiro de time"
        elif action.type == ActionType.LANCAMENTO:
            if action.target_cell is None:
                return False, "sem célula alvo"
            if not self._is_integer_cell(action.target_cell):
                return False, "célula alvo deve ter coordenadas inteiras"
            if not self._cell_in_bounds(action.target_cell):
                return False, "célula alvo fora da grade"
        elif action.type == ActionType.DRIBLE:
            if action.target_cell is None:
                return False, "sem célula alvo"
            if not self._is_integer_cell(action.target_cell):
                return False, "célula alvo deve ter coordenadas inteiras"
            if not self._cell_in_bounds(action.target_cell):
                return False, "célula alvo fora da grade"
            dist = s.cell_distance(actor.cell, action.target_cell)
            if dist > self.MAX_DRIBBLE_DISTANCE:
                return False, (
                    f"distância de drible excede limite "
                    f"({dist:.2f} > {self.MAX_DRIBBLE_DISTANCE})"
                )
        elif action.type == ActionType.FINALIZAR:
            pass  # sem alvo necessário

        return True, "ok"

    # -- Fonte única de verdade para posse (pontos 1 e 2) ----------------

    def _set_owner(self, player: Player) -> None:
        """Único ponto do código que altera ball.owner_id, ball.cell e
        state.possession. Chamar sempre em conjunto evita que os três
        campos fiquem inconsistentes entre si."""
        self.state.ball.cell = player.cell
        self.state.ball.owner_id = player.id
        self.state.possession = player.team

    def _turnover_to_nearest_opponent(self, cell: Cell) -> None:
        s = self.state
        current_owner = s.owner()
        opp_team = "B" if (current_owner and current_owner.team == "A") else "A"
        squad = s.team_a if opp_team == "A" else s.team_b
        new_owner = min(squad, key=lambda p: s.cell_distance(p.cell, cell))
        self._set_owner(new_owner)

    # -- Resolução de ações (assumem ação já validada) --------------------

    def _resolve_passe(self, action: Action) -> tuple[float, dict]:
        s = self.state
        actor = s.player_by_id(action.actor_id)
        target = s.player_by_id(action.target_id)
        dist = s.cell_distance(actor.cell, target.cell)
        pressure = s.pressure_on(action.actor_id)
        lane_open = s.passing_lane_open(action.actor_id, action.target_id)
        interception_risk = self._clamp(
            0.10 + pressure * 0.35 + (0.0 if lane_open else 0.45) + dist * 0.02
        )
        p_success = self._clamp(1.0 - interception_risk)
        success = self._rng.random() < p_success
        territorial_progress = self._territorial_progress(
            actor.cell, target.cell, s.possession
        )
        info = {
            "action": "PASSE",
            "actor": actor.id,
            "target": target.id,
            "success_probability": round(p_success, 3),
            "success": success,
            "pressure": pressure,
            "interception_risk": round(interception_risk, 3),
            "territorial_progress": round(territorial_progress, 3),
        }
        if success:
            self._set_owner(target)
            reward = 0.01 + max(0.0, territorial_progress) * 0.05
        else:
            self._turnover_to_nearest_opponent(target.cell)
            reward = -0.15
            info["turnover"] = True
        return reward, info

    def _resolve_lancamento(self, action: Action) -> tuple[float, dict]:
        s = self.state
        actor = s.player_by_id(action.actor_id)
        target_cell = action.target_cell
        dist = s.cell_distance(actor.cell, target_cell)
        pressure = s.pressure_on(action.actor_id)
        interception_risk = self._clamp(0.25 + pressure * 0.25 + dist * 0.035)
        p_success = self._clamp(1.0 - interception_risk)
        success = self._rng.random() < p_success
        territorial_progress = self._territorial_progress(
            actor.cell, target_cell, s.possession
        )
        info = {
            "action": "LANCAMENTO",
            "actor": actor.id,
            "target_cell": target_cell,
            "success_probability": round(p_success, 3),
            "success": success,
            "pressure": pressure,
            "interception_risk": round(interception_risk, 3),
            "territorial_progress": round(territorial_progress, 3),
        }
        if success:
            receiver = self._nearest_teammate(target_cell, actor.team)
            if receiver:
                self._set_owner(receiver)
                reward = 0.02 + max(0.0, territorial_progress) * 0.08
            else:
                self._turnover_to_nearest_opponent(target_cell)
                reward = -0.1
                info["turnover"] = True
                info["success"] = False
        else:
            self._turnover_to_nearest_opponent(target_cell)
            reward = -0.2
            info["turnover"] = True
        return reward, info

    def _resolve_drible(self, action: Action) -> tuple[float, dict]:
        s = self.state
        actor = s.player_by_id(action.actor_id)
        target_cell = action.target_cell
        pressure = s.pressure_on(action.actor_id)
        p_success = self._clamp(0.85 - pressure * 0.5)
        success = self._rng.random() < p_success
        territorial_progress = self._territorial_progress(
            actor.cell, target_cell, s.possession
        )
        info = {
            "action": "DRIBLE",
            "actor": actor.id,
            "target_cell": target_cell,
            "success_probability": round(p_success, 3),
            "success": success,
            "pressure": pressure,
            "territorial_progress": round(territorial_progress, 3),
        }
        if success:
            actor.cell = target_cell
            self._set_owner(actor)
            reward = 0.005 + max(0.0, territorial_progress) * 0.03
        else:
            self._turnover_to_nearest_opponent(actor.cell)
            reward = -0.12
            info["turnover"] = True
        return reward, info

    def _resolve_finalizar(self, action: Action) -> tuple[float, dict]:
        s = self.state
        actor = s.player_by_id(action.actor_id)
        pressure = s.pressure_on(action.actor_id)
        in_zone = self._in_finishing_zone(actor.cell, actor.team)
        base_p = 0.35 if in_zone else 0.08
        p_success = self._clamp(base_p - pressure * 0.2)
        success = self._rng.random() < p_success
        info = {
            "action": "FINALIZAR",
            "actor": actor.id,
            "success_probability": round(p_success, 3),
            "success": success,
            "pressure": pressure,
            "in_finishing_zone": in_zone,
            "chance_created": True,
        }
        if success:
            reward = 1.0
            info["goal"] = actor.team
        else:
            reward = -0.1
            self._turnover_to_nearest_opponent(actor.cell)
            info["turnover"] = True
        return reward, info

    def _resolve_cruzamento(self, action: Action) -> tuple[float, dict]:
        s = self.state
        actor = s.player_by_id(action.actor_id)
        target = s.player_by_id(action.target_id)
        is_lateral = actor.cell[1] in (0, 1, self.grid_rows - 2, self.grid_rows - 1)
        pressure = s.pressure_on(action.actor_id)
        base_p = 0.5 if is_lateral else 0.25
        interception_risk = self._clamp(0.2 + pressure * 0.3)
        p_success = self._clamp(base_p - interception_risk * 0.4)
        success = self._rng.random() < p_success
        info = {
            "action": "CRUZAMENTO",
            "actor": actor.id,
            "target": target.id,
            "success_probability": round(p_success, 3),
            "success": success,
            "pressure": pressure,
            "interception_risk": round(interception_risk, 3),
            "is_lateral": is_lateral,
        }
        if success:
            self._set_owner(target)
            reward = 0.03
            info["chance_created"] = True
        else:
            self._turnover_to_nearest_opponent(target.cell)
            reward = -0.15
            info["turnover"] = True
        return reward, info

    # -- Auxiliares -------------------------------------------------------

    def _territorial_progress(
        self, from_cell: Cell, to_cell: Cell, possession: str
    ) -> float:
        direction = 1 if possession == "A" else -1
        delta_col = (to_cell[0] - from_cell[0]) * direction
        return delta_col / self.grid_cols

    def _in_finishing_zone(self, cell: Cell, team: str) -> bool:
        if team == "A":
            return cell[0] >= self.grid_cols * FINALIZACAO_COL_MIN_FACTOR
        return cell[0] <= self.grid_cols * (1 - FINALIZACAO_COL_MIN_FACTOR)

    def _nearest_teammate(self, cell: Cell, team: str) -> Optional[Player]:
        s = self.state
        squad = s.team_a if team == "A" else s.team_b
        if not squad:
            return None
        return min(squad, key=lambda p: s.cell_distance(p.cell, cell))

    @staticmethod
    def _clamp(v: float, lo: float = 0.02, hi: float = 0.98) -> float:
        return max(lo, min(hi, v))

    def _snapshot(self) -> dict:
        s = self.state
        return {
            "time_step": s.time_step,
            "ball": {"cell": s.ball.cell, "owner_id": s.ball.owner_id},
            "possession": s.possession,
            "team_a": [(p.id, p.cell) for p in s.team_a],
            "team_b": [(p.id, p.cell) for p in s.team_b],
        }

    # -- Estatísticas do episódio ----------------------------------------

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "posse_steps_a": 0,
            "posse_steps_b": 0,
            "gols_a": 0,
            "gols_b": 0,
            "perdas_posse": 0,
            "chances_criadas": 0,
            "acoes_invalidas": 0,
            "progressao_territorial_soma": 0.0,
        }

    def _update_stats(
        self, action: Action, info: dict, valid: bool, decision_team: str
    ) -> None:
        s = self._episode_stats
        if decision_team == "A":
            s["posse_steps_a"] += 1
        else:
            s["posse_steps_b"] += 1
        if not valid:
            s["acoes_invalidas"] += 1
            return
        if info.get("turnover"):
            s["perdas_posse"] += 1
        if info.get("chance_created"):
            s["chances_criadas"] += 1
        if info.get("goal") == "A":
            s["gols_a"] += 1
        elif info.get("goal") == "B":
            s["gols_b"] += 1
        s["progressao_territorial_soma"] += info.get("territorial_progress", 0.0)
