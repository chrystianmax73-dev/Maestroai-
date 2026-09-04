"""
HeuristicAgent — IA local para o modo autônomo do Maestro.
============================================================
100% offline, sem dependências externas, sem rede. Decide ações
inteiramente através da API pública já existente do `MaestroGridEnv`
e do `GameState` (métodos como `pressure_on`, `passing_lane_open`,
`open_space_around`, `cell_distance`, `owner()`, `team_of()`,
`opponents_of()`). Não lê nem altera nenhum atributo privado do
ambiente (nada prefixado com `_`), e não modifica o núcleo do jogo.

O agente decide sempre para o time que está com a posse no momento
(`state.owner()`), permitindo simular a partida inteira sozinho —
os dois times — em modo autônomo. Também pode ser restrito a um
único time via `team=` para cenários futuros (ex.: IA só do
adversário, com o usuário controlando o outro lado).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .maestro_grid_env_v2 import (
    Action,
    ActionType,
    GameState,
    MaestroGridEnv,
    Player,
)

# Mesmo fator usado internamente pelo ambiente para zona de finalização
# (replicado aqui apenas como estimativa heurística — não altera nem
# lê nenhum estado privado do env; é só um parâmetro de decisão da IA).
_FINISHING_ZONE_FACTOR = 10 / 12

# Limiar de pressão acima do qual a IA evita finalizar/arriscar
_HIGH_PRESSURE = 0.55


@dataclass
class _Candidate:
    score: float
    action: Action
    label: str


class HeuristicAgent:
    """Agente baseado em regras simples e pontuação de candidatos.

    Uso:
        agent = HeuristicAgent(seed=7)
        action = agent.decide(env.state, env)
        state, reward, done, info = env.step(action)
    """

    def __init__(self, team: Optional[str] = None, seed: Optional[int] = None):
        """
        team: se definido ("A" ou "B"), o agente só decide quando esse
              time está com a posse; caso contrário devolve None.
              Se None, decide para quem estiver com a bola (self-play).
        """
        self.team = team
        self._rng = random.Random(seed)

    # -- API pública --------------------------------------------------

    def decide(self, state: GameState, env: MaestroGridEnv) -> Optional[Action]:
        """Retorna uma Action válida para o dono atual da bola, ou None
        se não houver dono ou se `team` estiver definido e não bater
        com o time da posse."""
        owner = state.owner()
        if owner is None:
            return None
        if self.team is not None and owner.team != self.team:
            return None

        candidates: list[_Candidate] = []
        pressure = state.pressure_on(owner.id)
        in_zone = self._in_finishing_zone(state, owner)

        # FINALIZAR — só quando faz sentido (zona de ataque, pouca pressão)
        if in_zone and pressure < _HIGH_PRESSURE:
            candidates.append(
                _Candidate(
                    score=0.9 - pressure * 0.3,
                    action=Action(type=ActionType.FINALIZAR, actor_id=owner.id),
                    label="FINALIZAR",
                )
            )

        candidates.extend(self._passe_candidates(state, owner))
        candidates.extend(self._cruzamento_candidates(state, owner))
        candidates.extend(self._lancamento_candidates(state, env, owner))
        candidates.extend(self._drible_candidates(state, env, owner))

        if not candidates:
            # Nenhuma opção decente — finaliza mesmo sob pressão, para
            # nunca devolver uma ação inválida (ator sempre tem a bola).
            return Action(type=ActionType.FINALIZAR, actor_id=owner.id)

        best = max(candidates, key=lambda c: c.score)
        return best.action

    # -- Geração de candidatos -----------------------------------------

    def _passe_candidates(self, state: GameState, owner: Player) -> list[_Candidate]:
        out = []
        for tm in state.team_of(owner.id):
            if tm.id == owner.id:
                continue
            progress = self._territorial_progress(state, owner.cell, tm.cell)
            lane_open = state.passing_lane_open(owner.id, tm.id)
            marked = state.is_marked(tm.id)
            score = 0.35 + progress * 0.6
            score += 0.15 if lane_open else -0.2
            score -= 0.15 if marked else 0.0
            out.append(
                _Candidate(
                    score=score,
                    action=Action(
                        type=ActionType.PASSE, actor_id=owner.id, target_id=tm.id
                    ),
                    label="PASSE",
                )
            )
        return out

    def _cruzamento_candidates(
        self, state: GameState, owner: Player
    ) -> list[_Candidate]:
        out = []
        is_lateral = owner.cell[1] in (0, 1, state.grid_rows - 2, state.grid_rows - 1)
        if not is_lateral:
            return out
        for tm in state.team_of(owner.id):
            if tm.id == owner.id:
                continue
            progress = self._territorial_progress(state, owner.cell, tm.cell)
            if progress <= 0:
                continue
            open_space = state.open_space_around(tm.id)
            score = 0.3 + progress * 0.5 + open_space * 0.2
            out.append(
                _Candidate(
                    score=score,
                    action=Action(
                        type=ActionType.CRUZAMENTO,
                        actor_id=owner.id,
                        target_id=tm.id,
                    ),
                    label="CRUZAMENTO",
                )
            )
        return out

    def _lancamento_candidates(
        self, state: GameState, env: MaestroGridEnv, owner: Player
    ) -> list[_Candidate]:
        out = []
        direction = 1 if owner.team == "A" else -1
        oc, orow = owner.cell
        pressure = state.pressure_on(owner.id)
        # só vale a pena arriscar lançamento sob pressão alta, ou para
        # progredir bastante o campo
        for reach in (3, 4):
            tc = oc + direction * reach
            for dr in (-1, 0, 1):
                tr = orow + dr
                if not (0 <= tc < state.grid_cols and 0 <= tr < state.grid_rows):
                    continue
                progress = self._territorial_progress(state, owner.cell, (tc, tr))
                if progress <= 0:
                    continue
                score = 0.15 + progress * 0.55 + (0.15 if pressure > _HIGH_PRESSURE else 0)
                out.append(
                    _Candidate(
                        score=score,
                        action=Action(
                            type=ActionType.LANCAMENTO,
                            actor_id=owner.id,
                            target_cell=(tc, tr),
                        ),
                        label="LANCAMENTO",
                    )
                )
        return out

    def _drible_candidates(
        self, state: GameState, env: MaestroGridEnv, owner: Player
    ) -> list[_Candidate]:
        out = []
        direction = 1 if owner.team == "A" else -1
        oc, orow = owner.cell
        pressure = state.pressure_on(owner.id)
        for dc, dr in [
            (direction, -1), (direction, 0), (direction, 1),
            (0, -1), (0, 1),
        ]:
            tc, tr = oc + dc, orow + dr
            if not (0 <= tc < state.grid_cols and 0 <= tr < state.grid_rows):
                continue
            dist = state.cell_distance(owner.cell, (tc, tr))
            if dist > env.MAX_DRIBBLE_DISTANCE:
                continue
            progress = self._territorial_progress(state, owner.cell, (tc, tr))
            score = 0.2 + progress * 0.4 - pressure * 0.3
            out.append(
                _Candidate(
                    score=score,
                    action=Action(
                        type=ActionType.DRIBLE,
                        actor_id=owner.id,
                        target_cell=(tc, tr),
                    ),
                    label="DRIBLE",
                )
            )
        return out

    # -- Auxiliares ------------------------------------------------------

    @staticmethod
    def _territorial_progress(state: GameState, from_cell, to_cell) -> float:
        direction = 1 if state.possession == "A" else -1
        delta_col = (to_cell[0] - from_cell[0]) * direction
        return delta_col / state.grid_cols

    @staticmethod
    def _in_finishing_zone(state: GameState, owner: Player) -> bool:
        if owner.team == "A":
            return owner.cell[0] >= state.grid_cols * _FINISHING_ZONE_FACTOR
        return owner.cell[0] <= state.grid_cols * (1 - _FINISHING_ZONE_FACTOR)
