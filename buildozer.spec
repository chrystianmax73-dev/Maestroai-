[app]
title = Maestro Grid
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
source.include_patterns = maestro/**,app/**,services/**
version = 0.2.0

# Dependências Python empacotadas no APK
requirements = python3==3.11,kivy

# Serviço de captura: MediaProjection + foreground service.
services = capture:services/capture.py:foreground:sticky:foregroundServiceType=mediaProjection

orientation = portrait
fullscreen = 0
android.permissions = FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION,SYSTEM_ALERT_WINDOW,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.add_src = %(source.dir)s/android_src
android.activity_class_name = org.maestro.capture.CaptureActivity
android.allow_backup = False
android.presplash_color = #2E7D32
android.accept_sdk_license = True
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
