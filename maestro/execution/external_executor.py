"""Cliente JSONL para um executor externo explicitamente autorizado.

Não executa shell, não lê memória e não injeta código: conversa apenas com
um processo de teste previamente iniciado e aceita operações semânticas.
"""
from __future__ import annotations
import json
import subprocess
import time
import uuid
from typing import Any, Iterable, Optional
from ..pipeline_models import ExecutionResult

ALLOWED_OPERATIONS = frozenset({"observe", "tap", "swipe", "key", "wait"})

class ExternalExecutorClient:
    def __init__(self, command: Iterable[str], timeout: float = 5.0, allowed_operations: Optional[set[str]] = None):
        self.command = list(command)
        self.timeout = float(timeout)
        self.allowed_operations = frozenset(allowed_operations or ALLOWED_OPERATIONS)
        self.process: Optional[subprocess.Popen[str]] = None

    def start(self) -> None:
        if self.process is None:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def request(self, operation: str, payload: Optional[dict[str, Any]] = None) -> ExecutionResult:
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        if operation not in self.allowed_operations or operation not in ALLOWED_OPERATIONS:
            return ExecutionResult(False, operation, request_id, error="operação não permitida")
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            return ExecutionResult(False, operation, request_id, error="executor externo não iniciado")
        try:
            self.process.stdin.write(json.dumps({"request_id": request_id, "operation": operation, "payload": payload or {}}, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("executor encerrou sem resposta")
            response = json.loads(line)
            return ExecutionResult(bool(response.get("success", False)), operation, request_id, (time.monotonic() - started) * 1000, response.get("error"), response.get("observed_state"), response)
        except Exception as exc:
            return ExecutionResult(False, operation, request_id, (time.monotonic() - started) * 1000, str(exc))
