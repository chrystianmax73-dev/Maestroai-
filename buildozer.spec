[app]
title = Maestro
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
# Empacota o núcleo e a captura Android, que só inicia após consentimento
# explícito do usuário através do fluxo MediaProjection.
source.include_patterns = maestro/**,app/**,services/**
version = 0.4.0

# python-for-android 2024.01.21 usa Python 3.11 de forma consistente
# para hostpython3 e python3.
requirements = python3,kivy

orientation = portrait
fullscreen = 0
# MediaProjection e overlay são usados somente pelo serviço autorizado.
android.permissions = SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = False
android.presplash_color = #2E7D32
android.accept_sdk_license = True
android.add_src = android_src
services = capture:services/capture.py
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
