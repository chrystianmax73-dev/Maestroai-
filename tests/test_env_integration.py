"""
Testes de integração do MaestroGridEnv usados pela vertical slice mobile.
Não alteram o ambiente — apenas validam o contrato consumido pela UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro import Action, ActionType, MaestroGridEnv


def test_reset_and_initial_state():
    env = MaestroGridEnv(seed=42)
    state, info = env.reset()
    assert state is not None
    assert state.possession == "A"
    assert state.ball.owner_id is not None
    assert len(state.team_a) == 4
    assert len(state.team_b) == 4
    assert info.get("event") == "reset"
    print("TESTE 1 OK — inicialização")


def test_passe_valid():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    teammates = [p for p in state.team_of(owner.id) if p.id != owner.id]
    assert teammates
    action = Action(type=ActionType.PASSE, actor_id=owner.id, target_id=teammates[0].id)
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    assert info["action"] == "PASSE"
    assert "success" in info
    print("TESTE 2 OK — passe")


def test_drible_valid():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    oc, or_ = owner.cell
    # tenta célula adjacente válida
    target = None
    for dc, dr in [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1)]:
        tc, tr = oc + dc, or_ + dr
        if 0 <= tc < state.grid_cols and 0 <= tr < state.grid_rows:
            target = (tc, tr)
            break
    assert target is not None
    action = Action(type=ActionType.DRIBLE, actor_id=owner.id, target_cell=target)
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    assert info["action"] == "DRIBLE"
    print("TESTE 3 OK — drible")


def test_lancamento():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    oc, or_ = owner.cell
    tc = min(state.grid_cols - 1, oc + 3)
    action = Action(
        type=ActionType.LANCAMENTO, actor_id=owner.id, target_cell=(tc, or_)
    )
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    assert info["action"] == "LANCAMENTO"
    print("TESTE 4 OK — lançamento")


def test_cruzamento():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    teammates = [p for p in state.team_of(owner.id) if p.id != owner.id]
    action = Action(
        type=ActionType.CRUZAMENTO, actor_id=owner.id, target_id=teammates[0].id
    )
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    assert info["action"] == "CRUZAMENTO"
    print("TESTE 5 OK — cruzamento")


def test_finalizar():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    action = Action(type=ActionType.FINALIZAR, actor_id=owner.id)
    state2, reward, done, info = env.step(action)
    assert info["valid"] is True
    assert info["action"] == "FINALIZAR"
    assert "success" in info
    print("TESTE 6 OK — finalização")


def test_invalid_action():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    owner = state.owner()
    # ator sem bola (outro jogador)
    other = [p for p in state.all_players() if p.id != owner.id][0]
    before = env._snapshot()
    action = Action(type=ActionType.FINALIZAR, actor_id=other.id)
    state2, reward, done, info = env.step(action)
    assert info["valid"] is False
    assert "reason" in info
    after = env._snapshot()
    # time_step avança, mas bola/jogadores não mudam (exceto time_step)
    assert after["ball"] == before["ball"]
    assert after["team_a"] == before["team_a"]
    assert after["team_b"] == before["team_b"]
    print("TESTE 7 OK — ação inválida")


def test_reset_again():
    env = MaestroGridEnv(seed=42)
    env.reset()
    owner = env.state.owner()
    env.step(Action(type=ActionType.FINALIZAR, actor_id=owner.id))
    state, info = env.reset()
    assert state.time_step == 0
    assert info.get("event") == "reset"
    print("TESTE 8 OK — reinicialização")


def test_sequence():
    env = MaestroGridEnv(seed=42)
    state, _ = env.reset()
    for _ in range(5):
        owner = state.owner()
        if owner is None:
            break
        teammates = [p for p in state.team_of(owner.id) if p.id != owner.id]
        if teammates:
            action = Action(
                type=ActionType.PASSE, actor_id=owner.id, target_id=teammates[0].id
            )
        else:
            action = Action(type=ActionType.FINALIZAR, actor_id=owner.id)
        state, reward, done, info = env.step(action)
        assert "valid" in info
        if done:
            break
    print("TESTE 9 OK — sequência de ações")


def test_reproducibility():
    def run():
        env = MaestroGridEnv(seed=42)
        state, _ = env.reset()
        results = []
        for _ in range(8):
            owner = state.owner()
            if not owner:
                break
            teammates = [p for p in state.team_of(owner.id) if p.id != owner.id]
            if teammates:
                action = Action(
                    type=ActionType.PASSE,
                    actor_id=owner.id,
                    target_id=teammates[0].id,
                )
            else:
                action = Action(type=ActionType.FINALIZAR, actor_id=owner.id)
            state, reward, done, info = env.step(action)
            results.append(
                (
                    info.get("action"),
                    info.get("success"),
                    info.get("goal"),
                    state.ball.owner_id,
                    state.possession,
                )
            )
            if done:
                break
        return results

    a = run()
    b = run()
    assert a == b, "mesma seed deve produzir mesma sequência"
    print("TESTE 10 OK — reprodutibilidade")


if __name__ == "__main__":
    test_reset_and_initial_state()
    test_passe_valid()
    test_drible_valid()
    test_lancamento()
    test_cruzamento()
    test_finalizar()
    test_invalid_action()
    test_reset_again()
    test_sequence()
    test_reproducibility()
    print("\n=== TODOS OS 10 TESTES PASSARAM ===")
