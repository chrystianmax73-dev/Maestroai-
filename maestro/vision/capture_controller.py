"""Controle da sessão de captura de tela Android do Maestro.

A implementação Android usa apenas APIs oficiais de MediaProjection e um
serviço foreground. A captura é somente leitura: os frames são analisados
localmente e nenhum evento de toque/teclado é injetado.
"""

from __future__ import annotations

import json
import os
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


class CaptureController:
    """Ponte entre a UI Kivy e o serviço Android de captura."""

    REQUEST_CODE = 4901
    RESULT_ACTION = "org.maestro.CAPTURE_RESULT"
    STOP_ACTION = "org.maestro.CAPTURE_STOP"

    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self._android = False
        self._status_path: Optional[Path] = None
        self._service = None
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

    def _load_status_path(self) -> Path:
        if self._status_path is not None:
            return self._status_path
        PythonActivity = self._autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        self._activity = activity
        self._status_path = Path(
            str(activity.getFilesDir().getAbsolutePath())
        ) / "maestro_capture_status.json"
        return self._status_path

    def status(self) -> CaptureStatus:
        if not self.available:
            return CaptureStatus(error="captura Android indisponível no desktop")
        path = self._load_status_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return CaptureStatus()
        return CaptureStatus(
            active=bool(data.get("active", False)),
            frames=int(data.get("frames", 0)),
            fps=float(data.get("fps", 0.0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            last_frame=str(data.get("last_frame", "")),
            error=str(data.get("error", "")),
        )

    def _notify(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

    def request_capture(self) -> bool:
        """Abre os dois consentimentos necessários em momentos separados.

        Primeiro garante SYSTEM_ALERT_WINDOW. Depois abre o diálogo oficial de
        MediaProjection. O token nunca é persistido em disco; é entregue por
        broadcast ao serviço depois do consentimento do usuário.
        """
        if not self.available:
            self._notify("Captura: disponível somente no Android")
            return False

        Settings = self._autoclass("android.provider.Settings")
        Build = self._autoclass("android.os.Build$VERSION")
        Intent = self._autoclass("android.content.Intent")
        Uri = self._autoclass("android.net.Uri")

        activity = self._activity or self._load_status_path() and self._activity
        if int(Build.SDK_INT) >= 23 and not Settings.canDrawOverlays(activity):
            intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
            intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
            activity.startActivity(intent)
            self._notify("Permita 'sobrepor a outros apps' e toque em CAPTURAR novamente")
            return False

        MediaProjectionManager = self._autoclass(
            "android.media.projection.MediaProjectionManager"
        )
        Context = self._autoclass("android.content.Context")
        manager = activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
        capture_intent = manager.createScreenCaptureIntent()

        if not self._bound:
            self._activity_module.bind(on_activity_result=self._on_activity_result)
            self._bound = True
        activity.startActivityForResult(capture_intent, self.REQUEST_CODE)
        self._notify("Aguardando autorização de captura de tela…")
        return True

    def _on_activity_result(self, request_code, result_code, data):
        if request_code != self.REQUEST_CODE:
            return
        if int(result_code) <= 0 or data is None:
            self._notify("Captura cancelada pelo usuário")
            return

        try:
            ServiceClass = self._autoclass(
                "org.maestro.maestrogrid.ServiceCapture"
            )
            activity = self._activity or self._load_status_path() and self._activity
            ServiceClass.start(activity, "capture")
            self._notify("Serviço de captura iniciado; preparando frames…")

            # O serviço é um processo separado do app Kivy. Enviamos o Intent
            # de consentimento por IPC/Broadcast, sem serializá-lo em disco.
            Clock = self._autoclass("android.os.Handler")
            Looper = self._autoclass("android.os.Looper")
            handler = Clock(Looper.getMainLooper())
            Runnable = self._make_runnable(
                lambda: self._send_result_broadcast(activity, int(result_code), data)
            )
            handler.postDelayed(Runnable, 700)
        except Exception as exc:
            self._notify(f"Falha ao iniciar captura: {exc}")

    def _make_runnable(self, fn):
        from jnius import PythonJavaClass, java_method

        class RunnableProxy(PythonJavaClass):
            __javainterfaces__ = ["java/lang/Runnable"]

            @java_method("()V")
            def run(self):
                fn()

        return RunnableProxy()

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
            ServiceClass = self._autoclass(
                "org.maestro.maestrogrid.ServiceCapture"
            )
            activity = self._activity or self._load_status_path() and self._activity
            ServiceClass.stop(activity)
        except Exception:
            try:
                Intent = self._autoclass("android.content.Intent")
                activity.sendBroadcast(Intent(self.STOP_ACTION).setPackage(activity.getPackageName()))
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
