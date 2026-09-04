"""Controle da sessão Android de captura do Maestro Vision."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CaptureStatus:
    active: bool = False
    frames: int = 0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    last_frame: str = ""
    error: str = ""
    scene_confidence: float = 0.0
    ball_confidence: float = 0.0
    uncertain: bool = True
    agent_active: bool = False
    agent_state: str = "OFF"


class CaptureController:
    REQUEST_CODE = 4901
    RESULT_ACTION = "org.maestro.CAPTURE_RESULT"
    STOP_ACTION = "org.maestro.CAPTURE_STOP"
    AGENT_START_ACTION = "org.maestro.AGENT_START"
    AGENT_PAUSE_ACTION = "org.maestro.AGENT_PAUSE"
    AGENT_STOP_ACTION = "org.maestro.AGENT_STOP"

    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self._android = False
        self._status_path: Optional[Path] = None
        self._activity = None
        try:
            from android import activity  # type: ignore
            from jnius import autoclass  # type: ignore
            self._android = True
            self._activity_module = activity
            self._autoclass = autoclass
        except ImportError:
            self._activity_module = None
            self._autoclass = None

    @property
    def available(self) -> bool:
        return self._android

    def _get_activity(self):
        if self._activity is None:
            self._activity = self._autoclass("org.kivy.android.PythonActivity").mActivity
        return self._activity

    def _load_status_path(self) -> Path:
        if self._status_path is None:
            activity = self._get_activity()
            self._status_path = Path(str(activity.getFilesDir().getAbsolutePath())) / "maestro_capture_status.json"
        return self._status_path

    def status(self) -> CaptureStatus:
        if not self.available:
            return CaptureStatus(error="captura Android indisponível no desktop")
        try:
            data = json.loads(self._load_status_path().read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return CaptureStatus()
        return CaptureStatus(
            active=bool(data.get("active", False)), frames=int(data.get("frames", 0)),
            fps=float(data.get("fps", 0.0)), width=int(data.get("width", 0)),
            height=int(data.get("height", 0)), last_frame=str(data.get("last_frame", "")),
            error=str(data.get("error", "")), scene_confidence=float(data.get("scene_confidence", 0.0)),
            ball_confidence=float(data.get("ball_confidence", 0.0)), uncertain=bool(data.get("uncertain", True)),
            agent_active=bool(data.get("agent_active", False)), agent_state=str(data.get("agent_state", "OFF")),
        )

    def _notify(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

    def request_capture(self) -> bool:
        if not self.available:
            self._notify("Captura Android indisponível")
            return False
        activity = self._get_activity()
        Settings = self._autoclass("android.provider.Settings")
        Build = self._autoclass("android.os.Build$VERSION")
        Uri = self._autoclass("android.net.Uri")
        if int(Build.SDK_INT) >= 23 and not Settings.canDrawOverlays(activity):
            intent = self._autoclass("android.content.Intent")(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
            intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
            activity.startActivity(intent)
            self._notify("Permita sobreposição e toque em ATIVAR CAPTURA novamente")
            return False
        Context = self._autoclass("android.content.Context")
        MPM = self._autoclass("android.media.projection.MediaProjectionManager")
        manager = activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
        if manager is None:
            self._notify("MediaProjection indisponível neste dispositivo")
            return False
        activity.startActivityForResult(manager.createScreenCaptureIntent(), self.REQUEST_CODE)
        self._notify("Aguardando autorização de captura de tela…")
        return True

    def _send(self, action: str) -> None:
        if not self.available:
            return
        try:
            Intent = self._autoclass("android.content.Intent")
            activity = self._get_activity()
            intent = Intent(action)
            intent.setPackage(activity.getPackageName())
            activity.sendBroadcast(intent)
        except Exception as exc:
            self._notify(f"Falha no comando: {exc}")

    def start_agent(self) -> None:
        self._send(self.AGENT_START_ACTION)
        self._notify("Modo IA de observação solicitado")

    def pause_agent(self) -> None:
        self._send(self.AGENT_PAUSE_ACTION)
        self._notify("IA pausada")

    def stop_agent(self) -> None:
        self._send(self.AGENT_STOP_ACTION)
        self._notify("IA parada")

    def stop(self) -> None:
        if not self.available:
            return
        # A parada é feita pelo receiver do próprio serviço. Isso evita depender
        # de uma API estática que o p4a não garante no PythonService gerado.
        self._send(self.STOP_ACTION)
        self._notify("Captura parada")

    def close(self) -> None:
        self.stop()
