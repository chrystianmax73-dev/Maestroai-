from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro import MaestroGridEnv
from maestro.tactical_engine import TacticalEngine


def test_tactical_engine_only_evaluates_and_does_not_advance_simulation():
    env = MaestroGridEnv(seed=42, max_steps=20)
    state, _ = env.reset()
    before = state.time_step

    engine = TacticalEngine(env)
    candidates = engine.evaluate(state)

    assert candidates
    assert all(0.0 <= item.score <= 1.0 for item in candidates)
    assert all(item.action.actor_id == state.owner().id for item in candidates)
    assert env.state.time_step == before


def test_tactical_engine_is_ranked_and_best_matches_first():
    env = MaestroGridEnv(seed=7, max_steps=20)
    state, _ = env.reset()
    engine = TacticalEngine(env)

    ranked = engine.evaluate(state)
    best = engine.best(state)

    assert best is not None
    assert ranked[0] == best
    assert all(ranked[i].score >= ranked[i + 1].score for i in range(len(ranked) - 1))
