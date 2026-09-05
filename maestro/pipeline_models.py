"""Modelos serializáveis do pipeline de pesquisa do Maestro."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

@dataclass(frozen=True)
class Point:
    x: float
    y: float

@dataclass(frozen=True)
class PlayerObservation:
    team: str
    x: float
    y: float
    confidence: float = 0.0

@dataclass(frozen=True)
class PerceptionSnapshot:
    width: int
    height: int
    ball: Optional[Point]
    players: list[PlayerObservation] = field(default_factory=list)
    field_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    confidence: float = 0.0
    uncertain: bool = True
    timestamp: float = 0.0
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class TacticalOption:
    label: str
    score: float
    rationale: str
    action: dict[str, Any]

@dataclass(frozen=True)
class TacticalDecision:
    action: dict[str, Any]
    label: str
    score: float
    rationale: str
    alternatives: list[TacticalOption] = field(default_factory=list)
    decision_id: str = ""
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    operation: str
    request_id: str
    duration_ms: float = 0.0
    error: Optional[str] = None
    observed_state: Optional[dict[str, Any]] = None
    raw: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def jsonable(value: Any) -> Any:
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value

def state_snapshot(state: Any) -> dict[str, Any]:
    return {} if state is None else jsonable(state)

def action_snapshot(action: Any) -> dict[str, Any]:
    return jsonable(action)
