from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro import HeuristicAgent, MaestroGridEnv
from maestro.execution import AutonomousLoop, SimulatorExecutor


def test_autonomous_loop_executes_decision_and_changes_step():
    env = MaestroGridEnv(seed=42, max_steps=12)
    loop = AutonomousLoop(env, HeuristicAgent(seed=42), SimulatorExecutor(env))

    state = loop.reset()
    assert state.time_step == 0

    record = loop.tick()
    assert record is not None
    assert record.valid is True
    assert record.step == 1
    assert loop.state.time_step == 1
    assert len(loop.history) == 1


def test_autonomous_loop_can_pause_and_resume():
    env = MaestroGridEnv(seed=7, max_steps=10)
    loop = AutonomousLoop(env, HeuristicAgent(seed=7), SimulatorExecutor(env))
    loop.reset()

    loop.pause()
    assert loop.tick() is None
    assert len(loop.history) == 0

    loop.resume()
    assert loop.tick() is not None
    assert len(loop.history) == 1


def test_autonomous_loop_run_respects_cycle_limit():
    env = MaestroGridEnv(seed=9, max_steps=50)
    loop = AutonomousLoop(env, HeuristicAgent(seed=9), SimulatorExecutor(env))
    history = loop.run(max_cycles=5)

    assert len(history) == 5
    assert all(item.valid for item in history)
    assert env.state.time_step == 5
