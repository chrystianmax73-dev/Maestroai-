"""Controle robusto da sessão de captura Android do Maestro.

Somente leitura: MediaProjection captura a tela para percepção/diagnóstico.
Nenhum toque, teclado ou comando é injetado em aplicativos externos.
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


class CaptureController:
    REQUEST_CODE = 4901
    REQUEST_ACTION = "org.maestro.CAPTURE_REQUEST"
    RESULT_ACTION = "org.maestro.CAPTURE_RESULT"
    STOP_ACTION = "org.maestro.CAPTURE_STOP"

    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self._android = False
        self._status_path: Optional[Path] = None
        self._activity = None
        self._bound = False
        try:
            from android import activity
            from jnius import autoclass
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
        if self._activity is not None:
            return self._activity
        PythonActivity = self._autoclass("org.kivy.android.PythonActivity")
        self._activity = PythonActivity.mActivity
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
        Intent = self._autoclass("android.content.Intent")
        Uri = self._autoclass("android.net.Uri")
        if int(Build.SDK_INT) >= 23 and not Settings.canDrawOverlays(activity):
            intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
            intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
            activity.startActivity(intent)
            self._notify("Permita sobreposição e toque em ATIVAR CAPTURA novamente")
            return False
        if not self._bound:
            self._activity_module.bind(on_activity_result=self._on_activity_result)
            self._bound = True
        Context = self._autoclass("android.content.Context")
        MPM = self._autoclass("android.media.projection.MediaProjectionManager")
        manager = activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
        activity.startActivityForResult(manager.createScreenCaptureIntent(), self.REQUEST_CODE)
        self._notify("Aguardando autorização de captura de tela…")
        return True

    def _on_activity_result(self, request_code, result_code, data):
        if request_code != self.REQUEST_CODE:
            return
        if int(result_code) <= 0 or data is None:
            self._notify("Captura cancelada")
            return
        try:
            ServiceClass = self._autoclass("org.maestro.maestrogrid.ServiceCapture")
            activity = self._get_activity()
            ServiceClass.start(activity, "capture")
            self._send_result_broadcast(activity, int(result_code), data)
            self._notify("Captura iniciada; aguardando primeiro frame…")
        except Exception as exc:
            self._notify(f"Falha ao iniciar captura: {exc}")

    def _send_result_broadcast(self, activity, result_code, data):
        Intent = self._autoclass("android.content.Intent")
        intent = Intent(self.RESULT_ACTION)
        intent.setPackage(activity.getPackageName())
        intent.putExtra("result_code", result_code)
        intent.putExtra("data_intent", data)
        activity.sendBroadcast(intent)

    def stop(self) -> None:
        if not self.available:
            return
        try:
            self._autoclass("org.maestro.maestrogrid.ServiceCapture").stop(self._get_activity())
        except Exception:
            try:
                Intent = self._autoclass("android.content.Intent")
                intent = Intent(self.STOP_ACTION)
                intent.setPackage(self._get_activity().getPackageName())
                self._get_activity().sendBroadcast(intent)
            except Exception:
                pass
        self._notify("Captura parada")

    def close(self) -> None:
        if self._bound and self._activity_module is not None:
            try:
                self._activity_module.unbind(on_activity_result=self._on_activity_result)
            except Exception:
                pass
            self._bound = False
        self.stop()
