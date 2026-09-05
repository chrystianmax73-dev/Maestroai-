from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from maestro.runtime import MaestroRuntime
from maestro.vision.frame_source import SyntheticFrameSource


def test_runtime_connects_simulation_tactics_and_execution():
    runtime = MaestroRuntime(seed=42, max_steps=10)
    runtime.start()
    candidates = runtime.analyze_current_state()
    assert candidates
    record = runtime.tick()
    assert record is not None
    assert record.step == 1
    assert runtime.snapshot().step == 1
    assert runtime.snapshot().last_decision == record


def test_runtime_can_analyze_explicit_frame_source_without_execution():
    source = SyntheticFrameSource(seed=3)
    source.start()
    runtime = MaestroRuntime(frame_source=source)
    result = runtime.poll_frame_source()
    assert result is not None
    assert 0.0 <= result.scene_confidence <= 1.0
    assert runtime.snapshot().perception == result
    assert runtime.snapshot().step == 0


def test_runtime_failure_is_observable_instead_of_crashing_the_ui():
    runtime = MaestroRuntime()
    runtime.last_error = "sentinel"
    snapshot = runtime.snapshot()
    assert snapshot.error == "sentinel"
