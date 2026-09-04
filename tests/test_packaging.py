"""Smoke tests da interface, captura e empacotamento Android."""

from __future__ import annotations

import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_buildozer_spec_has_required_keys():
    spec_path = ROOT / "buildozer.spec"
    assert spec_path.exists(), "buildozer.spec não encontrado"
    parser = configparser.ConfigParser()
    parser.read(spec_path, encoding="utf-8")
    app = parser["app"]
    required = ["title", "package.name", "package.domain", "source.dir", "version",
                "requirements", "services", "android.api", "android.minapi",
                "android.ndk", "android.archs", "android.permissions",
                "android.add_src", "android.activity_class_name"]
    missing = [k for k in required if k not in app]
    assert not missing, f"buildozer.spec sem as chaves: {missing}"
    assert "kivy" in app["requirements"] and "python3" in app["requirements"]
    assert "capture:services/capture.py" in app["services"]
    assert "mediaProjection" in app["services"]
    assert "FOREGROUND_SERVICE_MEDIA_PROJECTION" in app["android.permissions"]
    assert "SYSTEM_ALERT_WINDOW" in app["android.permissions"]
    assert "CaptureActivity" in app["android.activity_class_name"]


def test_project_sources_exist():
    parser = configparser.ConfigParser()
    parser.read(ROOT / "buildozer.spec", encoding="utf-8")
    patterns = parser["app"].get("source.include_patterns", "")
    assert all(x in patterns for x in ("maestro/**", "app/**", "services/**"))
    assert (ROOT / "android_src/org/maestro/capture/CaptureActivity.java").exists()
    assert (ROOT / "android_src/org/maestro/capture/ProjectionCallback.java").exists()


def test_capture_is_observation_only():
    service = (ROOT / "services/capture.py").read_text(encoding="utf-8")
    assert "MediaProjectionManager" in service
    assert "ImageReader" in service
    assert "TYPE_APPLICATION_OVERLAY" in service
    forbidden = ("adb", "input tap", "AccessibilityService", "performGlobalAction")
    assert not any(token.lower() in service.lower() for token in forbidden)


def test_capture_activation_is_explicit():
    java = (ROOT / "android_src/org/maestro/capture/CaptureActivity.java").read_text(encoding="utf-8")
    app = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "org.maestro.CAPTURE_REQUEST" in java
    assert "org.maestro.CAPTURE_REQUEST" in app
    create_block = java.split("onCreate(Bundle savedInstanceState)", 1)[1].split("onResume", 1)[0]
    assert "requestCaptureIfNeeded();" not in create_block


def test_ui_has_real_lab_controls():
    app = (ROOT / "app/main.py").read_text(encoding="utf-8")
    for label in ("ENTRAR NO LABORATÓRIO", "TESTAR VISÃO / CAPTURA", "JOGAR SOZINHO",
                  "PARAR IA", "PAUSAR", "NOVO JOGO", "PASSE", "DRIBLE", "LANÇAMENTO",
                  "CRUZAMENTO", "FINALIZAR", "MAESTRO VISION"):
        assert label in app, f"controle ausente: {label}"
    assert "ScreenManager" in app and "poll_capture" in app and "open_diagnostics" in app


def test_workflow_file_exists_and_has_expected_steps():
    workflow_path = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")
    assert "buildozer" in content and "android debug" in content
    assert "upload-artifact" in content and "workflow_dispatch" in content


def test_main_launcher_imports_app_correctly():
    launcher = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.main import MaestroMobileApp" in launcher


if __name__ == "__main__":
    test_buildozer_spec_has_required_keys()
    test_project_sources_exist()
    test_capture_is_observation_only()
    test_capture_activation_is_explicit()
    test_ui_has_real_lab_controls()
    test_workflow_file_exists_and_has_expected_steps()
    test_main_launcher_imports_app_correctly()
    print("=== TODOS OS TESTES DE EMPACOTAMENTO/UI PASSARAM ===")
