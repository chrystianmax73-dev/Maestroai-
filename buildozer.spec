[app]
title = Maestro
package.name = maestrogrid
package.domain = org.maestro
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
# Empacota só o que é de fato usado pelo app compilado: núcleo do
# simulador, IA, camada de visão genérica (maestro/vision, sem
# capture_controller.py sendo importado por ninguém) e a interface.
# services/**, android_src/** e o pacote `android`/jnius do capture
# controller NÃO são incluídos aqui — ficam no repositório como código
# isolado, fora do build (ver README/ARCHITECTURE.md).
source.include_patterns = maestro/**,app/**
version = 0.4.0

# python-for-android 2024.01.21 usa Python 3.11 de forma consistente
# para hostpython3 e python3.
requirements = python3,kivy

orientation = portrait
fullscreen = 0
# Sem serviço de captura nesta build: nenhuma permissão de overlay,
# projeção de mídia ou serviço em primeiro plano é necessária.
android.permissions = 
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = False
android.presplash_color = #2E7D32
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
