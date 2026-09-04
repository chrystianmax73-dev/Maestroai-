[app]
title = Maestro Grid
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
source.include_patterns = maestro/**,app/**
version = 0.2.0

# Dependências Python empacotadas no APK
requirements = python3,kivy

orientation = portrait
fullscreen = 0
android.permissions =
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.presplash_color = #2E7D32
# Aceita a licença do SDK automaticamente — necessário em CI não interativo
android.accept_sdk_license = True

# O launcher na raiz (main.py) importa app.main
# Buildozer procura main.py em source.dir por padrão.

[buildozer]
log_level = 2
warn_on_root = 1
