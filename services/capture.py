"""Foreground MediaProjection capture service for Maestro Vision.

Captura, percepção e overlay são somente leitura em relação ao aplicativo
em primeiro plano. Os controles do overlay comandam apenas o próprio Maestro.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from android.broadcast import BroadcastReceiver
from jnius import PythonJavaClass, autoclass, java_method
from maestro.vision.screen_perception import ScreenPerception

RESULT_ACTION = "org.maestro.CAPTURE_RESULT"
STOP_ACTION = "org.maestro.CAPTURE_STOP"
AGENT_START_ACTION = "org.maestro.AGENT_START"
AGENT_PAUSE_ACTION = "org.maestro.AGENT_PAUSE"
AGENT_STOP_ACTION = "org.maestro.AGENT_STOP"


class ImageAvailableListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/ImageReader$OnImageAvailableListener"]

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    @java_method("(Landroid/media/ImageReader;)V")
    def onImageAvailable(self, reader):
        self.owner.handle_image(reader)


class OverlayTouchListener(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnTouchListener"]

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.down_x = 0.0
        self.down_y = 0.0
        self.start_x = 0
        self.start_y = 0

    @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
    def onTouch(self, view, event):
        MotionEvent = autoclass("android.view.MotionEvent")
        action = event.getActionMasked()
        if action == MotionEvent.ACTION_DOWN:
            self.down_x = float(event.getRawX())
            self.down_y = float(event.getRawY())
            self.start_x = int(self.service.overlay_params.x)
            self.start_y = int(self.service.overlay_params.y)
            return True
        if action == MotionEvent.ACTION_MOVE and self.service.overlay_params is not None:
            self.service.overlay_params.x = self.start_x + int(float(event.getRawX()) - self.down_x)
            self.service.overlay_params.y = self.start_y + int(float(event.getRawY()) - self.down_y)
            self.service._update_overlay_position()
            return True
        return action == MotionEvent.ACTION_UP


class CaptureService:
    def __init__(self):
        self.service = autoclass("org.kivy.android.PythonService").mService
        self.context = self.service
        self.reader = self.virtual_display = self.projection = None
        self.listener = self.receiver = self.projection_callback = None
        self.overlay = self.overlay_params = self.overlay_touch = None
        self.header = self.details = None
        self.overlay_expanded = True
        self.running = False
        self.agent_active = False
        self.agent_state = "OFF"
        self.frame_count = 0
        self.total_frames = 0
        self.window_start = time.monotonic()
        self.fps = 0.0
        self.last_frame_path = ""
        self.width = self.height = 0
        self.capture_width = self.capture_height = 0
        self.perception = ScreenPerception()
        self.last_perception = {}
        base = Path(str(self.context.getFilesDir().getAbsolutePath()))
        self.status_path = base / "maestro_capture_status.json"
        self.perception_path = base / "maestro_perception.json"
        self._write_status(error="Aguardando autorização de MediaProjection")

    def _write_status(self, **extra):
        p = self.last_perception or {}
        data = {
            "active": self.running, "frames": self.total_frames,
            "fps": round(self.fps, 2), "width": self.width, "height": self.height,
            "capture_width": self.capture_width, "capture_height": self.capture_height,
            "last_frame": self.last_frame_path, "updated_at": time.time(), "error": "",
            "perception": p, "scene_confidence": p.get("scene_confidence", 0.0),
            "field_confidence": p.get("field_confidence", 0.0),
            "ball_confidence": p.get("ball_confidence", 0.0),
            "uncertain": p.get("uncertain", True), "agent_active": self.agent_active,
            "agent_state": self.agent_state,
            "proposed_action": "OBSERVAR" if self.agent_active else "—",
        }
        data.update(extra)
        try:
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.status_path)
            self.perception_path.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def register_receiver(self):
        self.receiver = BroadcastReceiver(
            self.on_broadcast,
            actions=[RESULT_ACTION, STOP_ACTION, AGENT_START_ACTION,
                     AGENT_PAUSE_ACTION, AGENT_STOP_ACTION],
        )
        self.receiver.start()

    def on_broadcast(self, context, intent):
        action = str(intent.getAction())
        try:
            if action == RESULT_ACTION:
                self.start_projection(int(intent.getIntExtra("result_code", 0)),
                                      intent.getParcelableExtra("data_intent"))
            elif action == STOP_ACTION:
                self.stop()
            elif action == AGENT_START_ACTION:
                self.agent_active = True; self.agent_state = "ATIVO · OBSERVAÇÃO"
                self._write_status(); self._update_overlay()
            elif action == AGENT_PAUSE_ACTION:
                self.agent_active = False; self.agent_state = "PAUSADO"
                self._write_status(); self._update_overlay()
            elif action == AGENT_STOP_ACTION:
                self.agent_active = False; self.agent_state = "OFF"
                self._write_status(); self._update_overlay()
        except Exception as exc:
            self._write_status(error=f"Comando: {exc}")

    def start_projection(self, result_code, data_intent):
        if result_code <= 0 or data_intent is None:
            self._write_status(error="Consentimento de captura ausente"); return
        if self.running: return
        try:
            Context = autoclass("android.content.Context")
            Metrics = autoclass("android.util.DisplayMetrics")
            ImageReader = autoclass("android.media.ImageReader")
            PixelFormat = autoclass("android.graphics.PixelFormat")
            Handler = autoclass("android.os.Handler")
            Looper = autoclass("android.os.Looper")
            DisplayManager = autoclass("android.hardware.display.DisplayManager")
            ProjectionCallback = autoclass("org.maestro.capture.ProjectionCallback")
            manager = self.context.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
            self.projection = manager.getMediaProjection(result_code, data_intent)
            if self.projection is None: raise RuntimeError("getMediaProjection retornou None")
            metrics = Metrics(); wm = self.context.getSystemService(Context.WINDOW_SERVICE)
            wm.getDefaultDisplay().getRealMetrics(metrics)
            source_w, source_h, density = int(metrics.widthPixels), int(metrics.heightPixels), int(metrics.densityDpi)
            self.width, self.height = source_w, source_h
            scale = min(1.0, 1280.0 / max(source_w, source_h))
            cap_w, cap_h = max(2, int(source_w * scale)), max(2, int(source_h * scale))
            self.capture_width, self.capture_height = cap_w, cap_h
            self.reader = ImageReader.newInstance(cap_w, cap_h, PixelFormat.RGBA_8888, 2)
            self.listener = ImageAvailableListener(self)
            self.reader.setOnImageAvailableListener(self.listener, Handler(Looper.getMainLooper()))
            self.virtual_display = self.projection.createVirtualDisplay(
                "MaestroCapture", cap_w, cap_h, density,
                int(DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR),
                self.reader.getSurface(), None, None)
            self.projection_callback = ProjectionCallback(self.context)
            self.projection.registerCallback(self.projection_callback, Handler(Looper.getMainLooper()))
            self.running = True; self.window_start = time.monotonic()
            self.frame_count = 0; self.total_frames = 0
            self._write_status(error=""); self._ensure_overlay()
        except Exception as exc:
            self._write_status(error=f"Falha ao criar captura: {exc}"); self.stop()

    def _button(self, parent, label, callback):
        Button = autoclass("android.widget.Button")
        button = Button(self.context); button.setText(label); button.setTextSize(11.0)
        button.setAllCaps(False); button.setOnClickListener(callback); parent.addView(button)
        return button

    def _ensure_overlay(self):
        if self.overlay is not None: return
        try:
            Context = autoclass("android.content.Context")
            LinearLayout = autoclass("android.widget.LinearLayout")
            TextView = autoclass("android.widget.TextView")
            Params = autoclass("android.view.WindowManager$LayoutParams")
            PixelFormat = autoclass("android.graphics.PixelFormat")
            Gravity = autoclass("android.view.Gravity")

            root = LinearLayout(self.context); root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(12, 8, 12, 8); root.setBackgroundColor(0xE614181C)
            header = TextView(self.context); header.setTextSize(13.0)
            header.setTextColor(0xFFFFFFFF); header.setPadding(4, 2, 4, 8); root.addView(header)
            self.header = header
            self.details = LinearLayout(self.context); self.details.setOrientation(LinearLayout.VERTICAL)
            root.addView(self.details)
            self._button(self.details, "▶  INICIAR IA", lambda v: self._agent_start())
            self._button(self.details, "Ⅱ  PAUSAR IA", lambda v: self._agent_pause())
            self._button(self.details, "■  PARAR IA", lambda v: self._agent_stop())
            self._button(self.details, "⌃  MINIMIZAR", lambda v: self._toggle_minimize())
            params = Params(Params.WRAP_CONTENT, Params.WRAP_CONTENT, Params.TYPE_APPLICATION_OVERLAY,
                            Params.FLAG_NOT_FOCUSABLE | Params.FLAG_LAYOUT_NO_LIMITS, PixelFormat.TRANSLUCENT)
            params.gravity = Gravity.TOP | Gravity.START; params.x = 12; params.y = 48
            self.context.getSystemService(Context.WINDOW_SERVICE).addView(root, params)
            self.overlay = root; self.overlay_params = params
            self.overlay_touch = OverlayTouchListener(self); header.setOnTouchListener(self.overlay_touch)
            self._update_overlay()
        except Exception as exc:
            self._write_status(error=f"Overlay: {exc}")

    def _agent_start(self):
        self.agent_active = True; self.agent_state = "ATIVO · OBSERVAÇÃO"
        self._write_status(); self._update_overlay()

    def _agent_pause(self):
        self.agent_active = False; self.agent_state = "PAUSADO"
        self._write_status(); self._update_overlay()

    def _agent_stop(self):
        self.agent_active = False; self.agent_state = "OFF"
        self._write_status(); self._update_overlay()

    def _toggle_minimize(self):
        self.overlay_expanded = not self.overlay_expanded
        if self.details is not None:
            self.details.setVisibility(0 if self.overlay_expanded else 8)
        if self.header is not None:
            self.header.setText("MAESTRO VISION · toque/arraste" if not self.overlay_expanded else "MAESTRO VISION")

    def _update_overlay_position(self):
        if self.overlay is None or self.overlay_params is None: return
        try:
            Context = autoclass("android.content.Context")
            self.context.getSystemService(Context.WINDOW_SERVICE).updateViewLayout(self.overlay, self.overlay_params)
        except Exception: pass

    def _update_overlay(self):
        if not self.running: return
        self._ensure_overlay()
        if self.overlay is None: return
        try:
            p = self.last_perception
            scene = float(p.get("scene_confidence", 0.0)); field = float(p.get("field_confidence", 0.0))
            ball = float(p.get("ball_confidence", 0.0)); name = "CAMPO" if scene >= 0.55 else "INCERTO"
            if self.header is not None:
                self.header.setText("MAESTRO VISION  ·  ● ATIVA\nIA: %s | FPS %.1f\n%s %.0f%% · campo %.0f%% · bola %.0f%%" %
                                    (self.agent_state, self.fps, name, scene * 100, field * 100, ball * 100))
        except Exception: pass

    def _remove_overlay(self):
        if self.overlay is None: return
        try:
            Context = autoclass("android.content.Context")
            self.context.getSystemService(Context.WINDOW_SERVICE).removeView(self.overlay)
        except Exception: pass
        self.overlay = self.overlay_params = self.overlay_touch = None
        self.header = self.details = None

    def handle_image(self, reader):
        if not self.running: return
        image = bitmap = None
        try:
            image = reader.acquireLatestImage()
            if image is None: return
            self.total_frames += 1; self.frame_count += 1
            now = time.monotonic(); elapsed = now - self.window_start
            if elapsed >= 1.0:
                self.fps = self.frame_count / elapsed; self.frame_count = 0; self.window_start = now
            plane = image.getPlanes()[0]; buffer = plane.getBuffer()
            w, h = int(image.getWidth()), int(image.getHeight())
            stride, pixel = int(plane.getRowStride()), int(plane.getPixelStride())

            # Duplicate preserva o cursor do buffer original usado pelo Bitmap.
            duplicate = buffer.duplicate(); remaining = int(duplicate.remaining())
            raw = bytearray(remaining); duplicate.get(raw)
            self.last_perception = self.perception.analyze_rgba_bytes(w, h, raw, stride, pixel).to_dict()

            Bitmap = autoclass("android.graphics.Bitmap"); Config = autoclass("android.graphics.Bitmap$Config")
            bitmap = Bitmap.createBitmap(w, h, Config.ARGB_8888); buffer.rewind(); bitmap.copyPixelsFromBuffer(buffer)
            frame = str(self.context.getFilesDir().getAbsolutePath()) + "/maestro_latest_frame.jpg"
            fos = autoclass("java.io.FileOutputStream")(frame)
            bitmap.compress(Bitmap.CompressFormat.JPEG, 82, fos); fos.close(); self.last_frame_path = frame
            self._write_status(); self._update_overlay()
        except Exception as exc:
            self._write_status(error=f"Frame: {exc}")
        finally:
            if bitmap is not None:
                try: bitmap.recycle()
                except Exception: pass
            if image is not None:
                try: image.close()
                except Exception: pass

    def stop(self):
        self.running = False; self.agent_active = False; self.agent_state = "OFF"
        for obj, method in ((self.virtual_display, "release"), (self.reader, "close"), (self.projection, "stop")):
            if obj is not None:
                try: getattr(obj, method)()
                except Exception: pass
        self.virtual_display = self.reader = self.projection = None
        self._remove_overlay(); self._write_status(error="Captura parada")


if __name__ == "__main__":
    service = CaptureService(); service.register_receiver()
    while True: time.sleep(60)
