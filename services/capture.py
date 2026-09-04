"""Foreground MediaProjection capture service for Maestro.

Captura e percepção são somente leitura. O serviço não injeta eventos em
aplicativos externos.
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


class ImageAvailableListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/ImageReader$OnImageAvailableListener"]
    def __init__(self, owner):
        super().__init__(); self.owner = owner
    @java_method("(Landroid/media/ImageReader;)V")
    def onImageAvailable(self, reader):
        self.owner.handle_image(reader)


class CaptureService:
    def __init__(self):
        self.service = autoclass("org.kivy.android.PythonService").mService
        self.context = self.service
        self.reader = self.virtual_display = self.projection = None
        self.listener = self.receiver = self.projection_callback = None
        self.overlay = self.overlay_params = None
        self.running = False; self.frame_count = 0; self.window_start = time.monotonic()
        self.fps = 0.0; self.last_frame_path = ""; self.width = self.height = 0
        self.perception = ScreenPerception(); self.last_perception = {}
        base = Path(str(self.context.getFilesDir().getAbsolutePath()))
        self.status_path = base / "maestro_capture_status.json"
        self.perception_path = base / "maestro_perception.json"
        self._write_status(error="Aguardando token de MediaProjection")

    def _write_status(self, **extra):
        p = self.last_perception or {}
        data = {"active": self.running, "frames": self.frame_count, "fps": round(self.fps, 2),
                "width": self.width, "height": self.height, "last_frame": self.last_frame_path,
                "updated_at": time.time(), "error": "", "perception": p,
                "scene_confidence": p.get("scene_confidence", 0.0),
                "ball_confidence": p.get("ball_confidence", 0.0),
                "uncertain": p.get("uncertain", True)}
        data.update(extra)
        try:
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.status_path)
            self.perception_path.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def register_receiver(self):
        self.receiver = BroadcastReceiver(self.on_broadcast, actions=[RESULT_ACTION, STOP_ACTION])
        self.receiver.start()

    def on_broadcast(self, context, intent):
        action = str(intent.getAction())
        if action == RESULT_ACTION:
            try:
                self.start_projection(int(intent.getIntExtra("result_code", 0)),
                                      intent.getParcelableExtra("data_intent"))
            except Exception as exc: self._write_status(error=f"MediaProjection: {exc}")
        elif action == STOP_ACTION: self.stop()

    def start_projection(self, result_code, data_intent):
        if result_code <= 0 or data_intent is None:
            self._write_status(error="Consentimento de captura ausente"); return
        try:
            Context = autoclass("android.content.Context")
            MPM = autoclass("android.media.projection.MediaProjectionManager")
            Metrics = autoclass("android.util.DisplayMetrics")
            ImageReader = autoclass("android.media.ImageReader")
            PixelFormat = autoclass("android.graphics.PixelFormat")
            Handler = autoclass("android.os.Handler"); Looper = autoclass("android.os.Looper")
            DisplayManager = autoclass("android.hardware.display.DisplayManager")
            ProjectionCallback = autoclass("org.maestro.capture.ProjectionCallback")
            manager = self.context.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
            self.projection = manager.getMediaProjection(result_code, data_intent)
            if self.projection is None: raise RuntimeError("getMediaProjection retornou None")
            metrics = Metrics(); wm = self.context.getSystemService(Context.WINDOW_SERVICE)
            wm.getDefaultDisplay().getRealMetrics(metrics)
            source_w, source_h, density = int(metrics.widthPixels), int(metrics.heightPixels), int(metrics.densityDpi)
            self.width, self.height = source_w, source_h
            scale = min(1.0, 1280.0 / max(source_w, source_h)); cap_w=max(2,int(source_w*scale)); cap_h=max(2,int(source_h*scale))
            self.reader = ImageReader.newInstance(cap_w, cap_h, PixelFormat.RGBA_8888, 2)
            self.listener = ImageAvailableListener(self)
            self.reader.setOnImageAvailableListener(self.listener, Handler(Looper.getMainLooper()))
            self.virtual_display = self.projection.createVirtualDisplay("MaestroCapture", cap_w, cap_h, density,
                int(DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR), self.reader.getSurface(), None, None)
            self.projection_callback = ProjectionCallback(self.context)
            self.projection.registerCallback(self.projection_callback, Handler(Looper.getMainLooper()))
            self.running=True; self.window_start=time.monotonic(); self.frame_count=0; self._write_status()
        except Exception as exc:
            self._write_status(error=f"Falha ao criar captura: {exc}"); self.stop()

    def _ensure_overlay(self):
        if self.overlay is not None: return
        try:
            Context=autoclass("android.content.Context"); TextView=autoclass("android.widget.TextView")
            Params=autoclass("android.view.WindowManager$LayoutParams"); PixelFormat=autoclass("android.graphics.PixelFormat")
            Gravity=autoclass("android.view.Gravity")
            view=TextView(self.context); view.setText("MAESTRO VISION\\nCAPTURA: ATIVA\\nAguardando frames…")
            view.setTextSize(12.0); view.setTextColor(0xFFFFFFFF); view.setBackgroundColor(0xB8000000); view.setPadding(18,12,18,12)
            flags=Params.FLAG_NOT_FOCUSABLE | Params.FLAG_NOT_TOUCHABLE | Params.FLAG_LAYOUT_NO_LIMITS
            params=Params(Params.WRAP_CONTENT,Params.WRAP_CONTENT,Params.TYPE_APPLICATION_OVERLAY,flags,PixelFormat.TRANSLUCENT)
            params.gravity=Gravity.TOP|Gravity.START; params.x=12; params.y=42
            self.context.getSystemService(Context.WINDOW_SERVICE).addView(view,params)
            self.overlay=view; self.overlay_params=params
        except Exception as exc: self._write_status(error=f"Overlay: {exc}")

    def _update_overlay(self):
        if not self.running: return
        self._ensure_overlay()
        if self.overlay is None: return
        try:
            p=self.last_perception; scene=float(p.get("scene_confidence",0)); field=float(p.get("field_confidence",0)); ball=float(p.get("ball_confidence",0))
            self.overlay.setText("MAESTRO VISION\\nCAPTURA: ATIVA  FPS: %.1f\\nTELA: %dx%d\\nCENA: %s %.0f%%\\nGRAMADO: %.0f%%  BOLA: %s %.0f%%\\nANÁLISE: somente leitura" %
                (self.fps,self.width,self.height,"CAMPO" if scene>=.55 else "INCERTO",scene*100,field*100,"sim" if ball>=.55 else "não",ball*100))
        except Exception: pass

    def _remove_overlay(self):
        if self.overlay is None:return
        try:
            Context=autoclass("android.content.Context"); self.context.getSystemService(Context.WINDOW_SERVICE).removeView(self.overlay)
        except Exception: pass
        self.overlay=self.overlay_params=None

    def handle_image(self, reader):
        if not self.running:return
        image=None
        try:
            image=reader.acquireLatestImage()
            if image is None:return
            self.frame_count+=1; now=time.monotonic(); elapsed=now-self.window_start
            if elapsed>=1.0: self.fps=self.frame_count/elapsed; self.frame_count=0; self.window_start=now
            plane=image.getPlanes()[0]; buffer=plane.getBuffer(); w=int(image.getWidth()); h=int(image.getHeight()); stride=int(plane.getRowStride()); pixel=int(plane.getPixelStride())
            # Bitmap is created from a temporary byte[] only; no frame leaves app-private storage.
            Bitmap=autoclass("android.graphics.Bitmap"); Config=autoclass("android.graphics.Bitmap$Config")
            bitmap=Bitmap.createBitmap(w,h,Config.ARGB_8888); bitmap.copyPixelsFromBuffer(buffer)
            frame=self.context.getFilesDir().getAbsolutePath()+"/maestro_latest_frame.jpg"
            fos=autoclass("java.io.FileOutputStream")(frame); bitmap.compress(Bitmap.CompressFormat.JPEG,82,fos); fos.close(); bitmap.recycle()
            self.last_frame_path=frame
            self.last_perception=self.perception.analyze_bitmap(buffer,w,h,stride,pixel) if hasattr(self.perception,"analyze_bitmap") else {}
            self._write_status(); self._update_overlay()
        except Exception as exc: self._write_status(error=f"Frame: {exc}")
        finally:
            if image is not None:
                try:image.close()
                except Exception:pass

    def stop(self):
        self.running=False
        for obj, method in ((self.virtual_display,"release"),(self.reader,"close"),(self.projection,"stop")):
            if obj is not None:
                try:getattr(obj,method)()
                except Exception:pass
        self.virtual_display=self.reader=self.projection=None; self._remove_overlay(); self._write_status(error="Captura parada")


if __name__ == "__main__":
    CaptureService().register_receiver()
    while True: time.sleep(60)
