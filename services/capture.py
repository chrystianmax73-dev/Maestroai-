"""Foreground MediaProjection capture service for Maestro.

The service captures frames into the app-private sandbox and exposes only
local diagnostic telemetry. It does not synthesize or inject input events.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from android.broadcast import BroadcastReceiver
from jnius import PythonJavaClass, autoclass, java_method


RESULT_ACTION = "org.maestro.CAPTURE_RESULT"
STOP_ACTION = "org.maestro.CAPTURE_STOP"


class ImageAvailableListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/ImageReader$OnImageAvailableListener"]

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    @java_method("(Landroid/media/ImageReader;)V")
    def onImageAvailable(self, reader):
        self.owner.handle_image(reader)


class CaptureService:
    def __init__(self):
        self.service = autoclass("org.kivy.android.PythonService").mService
        self.context = self.service
        self.reader = None
        self.virtual_display = None
        self.projection = None
        self.listener = None
        self.receiver = None
        self.running = False
        self.frame_count = 0
        self.window_start = time.monotonic()
        self.fps = 0.0
        self.last_frame_path = ""
        self.width = 0
        self.height = 0
        self._lock = threading.Lock()
        self.status_path = Path(
            str(self.context.getFilesDir().getAbsolutePath())
        ) / "maestro_capture_status.json"
        self._write_status(error="Aguardando token de MediaProjection")

    def _write_status(self, **extra):
        data = {
            "active": self.running,
            "frames": self.frame_count,
            "fps": round(self.fps, 2),
            "width": self.width,
            "height": self.height,
            "last_frame": self.last_frame_path,
            "updated_at": time.time(),
            "error": "",
        }
        data.update(extra)
        tmp = self.status_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.status_path)
        except OSError:
            pass

    def register_receiver(self):
        self.receiver = BroadcastReceiver(self.on_broadcast, actions=[
            "org.maestro.CAPTURE_RESULT",
            "org.maestro.CAPTURE_STOP",
        ])
        self.receiver.start()

    def on_broadcast(self, context, intent):
        action = str(intent.getAction())
        if action == RESULT_ACTION:
            try:
                result_code = int(intent.getIntExtra("result_code", 0))
                data_intent = intent.getParcelableExtra("data_intent")
                self.start_projection(result_code, data_intent)
            except Exception as exc:
                self._write_status(error=f"MediaProjection: {exc}")
        elif action == STOP_ACTION:
            self.stop()

    def start_projection(self, result_code, data_intent):
        if result_code <= 0 or data_intent is None:
            self._write_status(error="Consentimento de captura ausente")
            return

        try:
            Context = autoclass("android.content.Context")
            MediaProjectionManager = autoclass(
                "android.media.projection.MediaProjectionManager"
            )
            DisplayMetrics = autoclass("android.util.DisplayMetrics")
            WindowManager = autoclass("android.view.WindowManager")
            ImageReader = autoclass("android.media.ImageReader")
            PixelFormat = autoclass("android.graphics.PixelFormat")
            Handler = autoclass("android.os.Handler")
            Looper = autoclass("android.os.Looper")
            Build = autoclass("android.os.Build$VERSION")

            manager = self.context.getSystemService(
                Context.MEDIA_PROJECTION_SERVICE
            )
            self.projection = manager.getMediaProjection(result_code, data_intent)
            if self.projection is None:
                raise RuntimeError("getMediaProjection retornou None")

            metrics = DisplayMetrics()
            wm = self.context.getSystemService(Context.WINDOW_SERVICE)
            wm.getDefaultDisplay().getRealMetrics(metrics)
            self.width = int(metrics.widthPixels)
            self.height = int(metrics.heightPixels)
            density = int(metrics.densityDpi)

            # Reduz a resolução apenas se a tela for muito grande, mantendo
            # captura suficiente para a próxima camada de visão computacional.
            max_dim = 1280
            scale = min(1.0, max_dim / float(max(self.width, self.height)))
            cap_w = max(2, int(self.width * scale))
            cap_h = max(2, int(self.height * scale))

            self.reader = ImageReader.newInstance(
                cap_w, cap_h, PixelFormat.RGBA_8888, 2
            )
            self.listener = ImageAvailableListener(self)
            self.reader.setOnImageAvailableListener(
                self.listener, Handler(Looper.getMainLooper())
            )

            flags = 0
            DisplayManager = autoclass("android.hardware.display.DisplayManager")
            flags = int(DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR)
            self.virtual_display = self.projection.createVirtualDisplay(
                "MaestroCapture",
                cap_w,
                cap_h,
                density,
                flags,
                self.reader.getSurface(),
                None,
                None,
            )

            self.running = True
            self.window_start = time.monotonic()
            self.frame_count = 0
            self._write_status()

            # Android 14+: a MediaProjection session must be stopped when the
            # system withdraws the token.
            try:
                self.projection.registerCallback(
                    ProjectionCallback(self), Handler(Looper.getMainLooper())
                )
            except Exception:
                pass
        except Exception as exc:
            self._write_status(error=f"Falha ao criar captura: {exc}")
            self.stop()

    def handle_image(self, reader):
        if not self.running:
            return
        image = None
        try:
            image = reader.acquireLatestImage()
            if image is None:
                return
            # Mantemos uma amostra JPEG por segundo. O restante dos frames
            # serve para telemetria de FPS sem gerar I/O excessivo.
            now = time.monotonic()
            self.frame_count += 1
            elapsed = now - self.window_start
            if elapsed >= 1.0:
                self.fps = self.frame_count / elapsed
                self.frame_count = 0
                self.window_start = now
                self._save_sample(image)
                self._write_status()
        except Exception as exc:
            self._write_status(error=f"Frame: {exc}")
        finally:
            if image is not None:
                try:
                    image.close()
                except Exception:
                    pass

    def _save_sample(self, image):
        planes = image.getPlanes()
        if planes is None or len(planes) == 0:
            return
        plane = planes[0]
        buffer = plane.getBuffer()
        pixel_stride = int(plane.getPixelStride())
        row_stride = int(plane.getRowStride())
        width = int(image.getWidth())
        height = int(image.getHeight())
        row_padding = max(0, row_stride - pixel_stride * width)
        padded_width = width + (row_padding // max(1, pixel_stride))

        Bitmap = autoclass("android.graphics.Bitmap")
        CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
        bitmap = None
        try:
            bitmap = Bitmap.createBitmap(
                padded_width, height, Bitmap.Config.ARGB_8888
            )
            bitmap.copyPixelsFromBuffer(buffer)
            cropped = bitmap
            if padded_width != width:
                cropped = Bitmap.createBitmap(bitmap, 0, 0, width, height)

            out_path = Path(
                str(self.context.getFilesDir().getAbsolutePath())
            ) / "maestro_latest_frame.jpg"
            with open(out_path, "wb") as fp:
                cropped.compress(CompressFormat.JPEG, 75, fp)
            self.last_frame_path = str(out_path)
            if cropped is not bitmap:
                cropped.recycle()
        finally:
            if bitmap is not None:
                bitmap.recycle()

    def stop(self):
        self.running = False
        for obj, method in [
            (self.virtual_display, "release"),
            (self.reader, "close"),
            (self.projection, "stop"),
        ]:
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
        self.virtual_display = None
        self.reader = None
        self.projection = None
        self.listener = None
        self._write_status()


class ProjectionCallback(PythonJavaClass):
    __javainterfaces__ = ["android/media/projection/MediaProjection$Callback"]

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    @java_method("()V")
    def onStop(self):
        self.owner.stop()


capture = CaptureService()
capture.register_receiver()

try:
    while True:
        time.sleep(1.0)
except KeyboardInterrupt:
    capture.stop()
