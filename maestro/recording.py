"""Registro append-only de sessões do pipeline do Maestro."""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from .pipeline_models import jsonable, state_snapshot

class SessionRecorder:
    def __init__(self, path: str | Path, session_id: Optional[str] = None):
        self.path = Path(path)
        self.session_id = session_id or f"session-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        self.count = 0

    def record(self, *, frame: Any = None, perception: Any = None, game_state: Any = None,
               candidates: Any = None, decision: Any = None, execution: Any = None,
               error: Optional[str] = None) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"session_id": self.session_id, "sequence": self.count, "timestamp": time.time(),
                 "frame": jsonable(frame), "perception": jsonable(perception),
                 "game_state": state_snapshot(game_state) if game_state is not None else None,
                 "candidates": jsonable(candidates), "decision": jsonable(decision),
                 "execution": jsonable(execution), "error": error}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        self.count += 1
        return entry

    def record_decision(self, state, candidates, decision, execution=None, **extra):
        return self.record(game_state=state, candidates=candidates, decision=decision, execution=execution, **extra)
