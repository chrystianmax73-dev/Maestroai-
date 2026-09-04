"""
Testes do HeuristicAgent (modo autônomo).
Garante que a IA nunca produz ações inválidas e não quebra o
contrato do MaestroGridEnv, rodando partidas completas sozinha.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro import Action, ActionType, HeuristicAgent, MaestroGridEnv


def _run_autonomous_match(seed: int, max_steps: int = 120):
    env = MaestroGridEnv(seed=seed, max_steps=max_steps)
    agent = HeuristicAgent(seed=seed)
    state, info = env.reset()
    history = []
    done = False
    while not done:
        action = agent.decide(state, env)
        assert action is not None, "agente deve sempre decidir enquanto houver dono da bola"
        state, reward, done, info = env.step(action)
        history.append(info)
    return history


def test_agent_always_produces_valid_actions():
    for seed in (1, 2, 3, 42, 99):
        history = _run_autonomous_match(seed, max_steps=80)
        invalid = [h for h in history if h.get("valid") is False]
        assert not invalid, f"IA gerou ação inválida: {invalid[0]}"
    print("TESTE IA 1 OK — nenhuma ação inválida em 5 partidas completas")


def test_agent_respects_actor_has_ball_rule():
    env = MaestroGridEnv(seed=7, max_steps=50)
    agent = HeuristicAgent(seed=7)
    state, _ = env.reset()
    for _ in range(50):
        owner_before = state.owner()
        action = agent.decide(state, env)
        if action is None:
            break
        assert action.actor_id == owner_before.id, (
            "agente só pode agir pelo jogador que está com a bola"
        )
        state, reward, done, info = env.step(action)
        if done:
            break
    print("TESTE IA 2 OK — ator sempre é o dono da bola no momento da decisão")


def test_agent_respects_dribble_distance_limit():
    env = MaestroGridEnv(seed=13, max_steps=100)
    agent = HeuristicAgent(seed=13)
    state, _ = env.reset()
    done = False
    while not done:
        action = agent.decide(state, env)
        if action.type == ActionType.DRIBLE:
            dist = state.cell_distance(state.owner().cell, action.target_cell)
            assert dist <= env.MAX_DRIBBLE_DISTANCE
        state, reward, done, info = env.step(action)
    print("TESTE IA 3 OK — drible nunca excede MAX_DRIBBLE_DISTANCE")


def test_agent_reproducibility_with_seed():
    def run():
        return [
            (info.get("action"), info.get("success"), info.get("goal"))
            for info in _run_autonomous_match(seed=21, max_steps=40)
        ]

    a = run()
    b = run()
    assert a == b, "mesma seed (env + agente) deve produzir a mesma sequência"
    print("TESTE IA 4 OK — reprodutibilidade do modo autônomo")


def test_agent_scoped_to_single_team_returns_none_when_not_its_turn():
    env = MaestroGridEnv(seed=5, max_steps=30)
    agent_a = HeuristicAgent(team="A", seed=5)
    state, _ = env.reset()
    # Time A começa com a bola — agente restrito a A deve decidir
    assert agent_a.decide(state, env) is not None
    # Força posse para B via turnover simulando lançamento perdido
    owner = state.owner()
    state, reward, done, info = env.step(
        Action(type=ActionType.LANCAMENTO, actor_id=owner.id, target_cell=(0, 0))
    )
    if state.possession == "B":
        assert agent_a.decide(state, env) is None
    print("TESTE IA 5 OK — agente restrito a um time não age fora de sua vez")


def test_manual_mode_still_works_alongside_agent():
    """Garante que o ambiente continua aceitando ações manuais
    normalmente mesmo com o HeuristicAgent importado/disponível."""
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    teammates = [p for p in state.team_of(owner.id) if p.id != owner.id]
    action = Action(type=ActionType.PASSE, actor_id=owner.id, target_id=teammates[0].id)
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    print("TESTE IA 6 OK — modo manual continua funcionando normalmente")


if __name__ == "__main__":
    test_agent_always_produces_valid_actions()
    test_agent_respects_actor_has_ball_rule()
    test_agent_respects_dribble_distance_limit()
    test_agent_reproducibility_with_seed()
    test_agent_scoped_to_single_team_returns_none_when_not_its_turn()
    test_manual_mode_still_works_alongside_agent()
    print("\n=== TODOS OS TESTES DO HEURISTIC AGENT PASSARAM ===")
