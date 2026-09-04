"""Controle da sessão Android de captura do Maestro Vision.

O controlador roda no processo principal. Ele nunca inicia MediaProjection no
startup: somente após ação explícita do usuário e RESULT_OK do Android o
serviço p4a Capture é iniciado e recebe o token por broadcast local.
"""
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
    REQUEST_ACTION = "org.maestro.CAPTURE_REQUEST"
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
        self._activity_module = None
        self._autoclass = None
        self._activity_bound = False
        try:
            from android import activity  # type: ignore
            from jnius import autoclass  # type: ignore
            self._android = True
            self._activity_module = activity
            self._autoclass = autoclass
            self._bind_activity_result()
        except Exception:
            # Captura é opcional: falha de bridge nunca pode impedir o startup.
            self._android = False
            self._activity_module = None
            self._autoclass = None

    @property
    def available(self) -> bool:
        return self._android

    def _get_activity(self):
        if not self.available:
            raise RuntimeError("captura Android indisponível")
        if self._activity is None:
            self._activity = self._autoclass("org.kivy.android.PythonActivity").mActivity
        return self._activity

    def _bind_activity_result(self) -> None:
        if not self.available or self._activity_bound:
            return
        try:
            self._activity_module.bind(on_activity_result=self._on_activity_result)
            self._activity_bound = True
        except Exception as exc:
            self._notify(f"Bridge MediaProjection indisponível: {exc}")

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
            try:
                self.status_callback(text)
            except Exception:
                pass

    def request_capture(self) -> bool:
        if not self.available:
            self._notify("Captura Android indisponível")
            return False
        try:
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
        except Exception as exc:
            self._notify(f"Falha ao solicitar captura: {exc}")
            return False

    def _on_activity_result(self, request_code, result_code, data_intent) -> None:
        if int(request_code) != self.REQUEST_CODE:
            return
        try:
            if int(result_code) != -1 or data_intent is None:
                self._notify("Captura cancelada pelo usuário")
                return
            self._start_service()
            self._send_result(result_code, data_intent)
            self._notify("Autorização recebida; iniciando captura…")
        except Exception as exc:
            self._notify(f"Falha ao iniciar captura autorizada: {exc}")

    def _start_service(self) -> None:
        activity = self._get_activity()
        ServiceCapture = self._autoclass("org.maestro.maestrogrid.ServiceCapture")
        ServiceCapture.start(activity, "capture")

    def _send_result(self, result_code, data_intent) -> None:
        Intent = self._autoclass("android.content.Intent")
        activity = self._get_activity()
        intent = Intent(self.RESULT_ACTION)
        intent.setPackage(activity.getPackageName())
        intent.putExtra("result_code", int(result_code))
        intent.putExtra("data_intent", data_intent)
        activity.sendBroadcast(intent)

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
        self._send(self.STOP_ACTION)
        self._notify("Captura parada")

    def close(self) -> None:
        if self._activity_module is not None and self._activity_bound:
            try:
                self._activity_module.unbind(on_activity_result=self._on_activity_result)
            except Exception:
                pass
            self._activity_bound = False
        self.stop()
