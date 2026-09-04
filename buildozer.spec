[app]
title = Maestro
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,java
source.include_patterns = maestro/**,app/**,services/**,android_src/**
version = 0.3.1

# Dependências Python empacotadas no APK.
# A release v2024.01.21 do python-for-android usa Python 3.11
# de forma consistente para hostpython3 e python3.
requirements = python3,kivy

# Serviço de captura: somente foreground. A autorização MediaProjection
# ocorre sob ação explícita do usuário antes do serviço iniciar a sessão.
services = capture:services/capture.py:foreground

orientation = portrait
fullscreen = 0
android.permissions = FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION,SYSTEM_ALERT_WINDOW,POST_NOTIFICATIONS
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.add_src = %(source.dir)s/android_src
android.allow_backup = False
android.presplash_color = #2E7D32
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
