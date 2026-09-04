[app]
title = Maestro Grid
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
source.include_patterns = maestro/**,app/**,services/**
version = 0.2.0

# Dependências Python empacotadas no APK
requirements = python3,kivy

# Serviço de captura: MediaProjection + foreground service.
# O serviço roda separado do processo Kivy e recebe o token de captura por IPC.
services = capture:services/capture.py:foreground:sticky:foregroundServiceType=mediaProjection

orientation = portrait
fullscreen = 0
android.permissions = FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION,SYSTEM_ALERT_WINDOW,POST_NOTIFICATIONS
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.add_src = %(source.dir)s/android_src
android.allow_backup = True
android.presplash_color = #2E7D32
# Aceita a licença do SDK automaticamente — necessário em CI não interativo
android.accept_sdk_license = True

# O launcher na raiz (main.py) importa app.main.
# Buildozer procura main.py em source.dir por padrão.

[buildozer]
log_level = 2
warn_on_root = 1
