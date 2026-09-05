from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from maestro import MaestroGridEnv
from maestro.pipeline import ResearchPipeline
from maestro.pipeline_models import PerceptionSnapshot, Point, PlayerObservation
from maestro.recording import SessionRecorder
from maestro.vision.game_state_adapter import GameStateAdapter
from maestro.execution.external_executor import ExternalExecutorClient

def test_game_state_adapter_maps_confident_perception():
    perception = PerceptionSnapshot(100, 100, Point(.25, .5), [PlayerObservation("A", .25, .5, .9), PlayerObservation("B", .8, .5, .9)], confidence=.9, uncertain=False)
    state = GameStateAdapter().to_state(perception)
    assert state is not None
    assert state.ball.owner_id == 0
    assert state.team_a[0].cell == (3, 4)

def test_pipeline_decision_and_recording():
    env = MaestroGridEnv(seed=1, max_steps=5)
    state, _ = env.reset()
    with tempfile.TemporaryDirectory() as directory:
        recorder = SessionRecorder(Path(directory) / "session.jsonl")
        decision = ResearchPipeline(env, recorder).decide(state)
        assert decision is not None
        lines = (Path(directory) / "session.jsonl").read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["decision"]["label"] == decision.label

def test_external_executor_rejects_unsafe_operation_before_process():
    result = ExternalExecutorClient(["not-started"], allowed_operations={"tap"}).request("memory_read")
    assert not result.success
    assert "não permitida" in (result.error or "")

if __name__ == "__main__":
    test_game_state_adapter_maps_confident_perception()
    test_pipeline_decision_and_recording()
    test_external_executor_rejects_unsafe_operation_before_process()
    print("=== TESTES DO PIPELINE PASSARAM ===")
