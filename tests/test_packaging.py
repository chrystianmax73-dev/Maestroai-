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
    parser = configparser.ConfigParser(); parser.read(spec_path, encoding="utf-8")
    app = parser["app"]
    required = ["title", "package.name", "package.domain", "source.dir", "version", "requirements", "services", "android.api", "android.minapi", "android.ndk", "android.archs", "android.permissions", "android.add_src", "android.activity_class_name"]
    missing = [k for k in required if k not in app]
    assert not missing, f"buildozer.spec sem as chaves: {missing}"
    assert "kivy" in app["requirements"] and "python3" in app["requirements"]
    assert "capture:services/capture.py" in app["services"]
    assert "foregroundServiceType=mediaProjection" in app["services"]
    assert "FOREGROUND_SERVICE_MEDIA_PROJECTION" in app["android.permissions"]
    assert "SYSTEM_ALERT_WINDOW" in app["android.permissions"]
    assert "CaptureActivity" in app["android.activity_class_name"]


def test_project_sources_exist():
    parser = configparser.ConfigParser(); parser.read(ROOT / "buildozer.spec", encoding="utf-8")
    patterns = parser["app"].get("source.include_patterns", "")
    assert all(x in patterns for x in ("maestro/**", "app/**", "services/**"))
    assert (ROOT / "android_src/org/maestro/capture/CaptureActivity.java").exists()
    assert (ROOT / "android_src/org/maestro/capture/ProjectionCallback.java").exists()
    assert (ROOT / "app/main_v2.py").exists()


def test_capture_is_observation_only():
    service = (ROOT / "services/capture.py").read_text(encoding="utf-8")
    assert "MediaProjection" in service and "ImageReader" in service
    assert "TYPE_APPLICATION_OVERLAY" in service and "OnTouchListener" in service
    forbidden = ("adb", "input tap", "AccessibilityService", "performGlobalAction")
    assert not any(token.lower() in service.lower() for token in forbidden)


def test_capture_activation_is_explicit():
    java = (ROOT / "android_src/org/maestro/capture/CaptureActivity.java").read_text(encoding="utf-8")
    app = (ROOT / "app/main_v2.py").read_text(encoding="utf-8")
    assert "CAPTURE_RESULT" in java
    assert "MediaProjectionManager" in java
    assert "org.maestro.CAPTURE_REQUEST" in app
    assert "requestCaptureIfNeeded();" not in java


def test_service_bridge_matches_buildozer_name():
    spec = configparser.ConfigParser(); spec.read(ROOT / "buildozer.spec", encoding="utf-8")
    service = (ROOT / "services/capture.py").read_text(encoding="utf-8")
    controller = (ROOT / "maestro/vision/capture_controller.py").read_text(encoding="utf-8")
    java = (ROOT / "android_src/org/maestro/capture/CaptureActivity.java").read_text(encoding="utf-8")
    assert spec["app"]["package.name"] == "maestrogrid"
    assert "Class.forName(\"org.maestro.maestrogrid.ServiceCapture\")" in java
    assert 'getMethod("start", android.app.Activity.class, String.class)' in java
    assert 'invoke(null, this, "capture")' in java
    assert "CAPTURE_STOP" in controller
    assert "ServiceCapture.stop" not in controller
    assert "CAPTURE_RESULT" in service
    assert "CAPTURE_STOP" in service
    assert "getParcelableExtra(\"data_intent\")" in service


def test_ui_has_real_lab_controls():
    app = (ROOT / "app/main_v2.py").read_text(encoding="utf-8")
    for label in ("ABRIR LABORATÓRIO", "TESTAR VISÃO E CAPTURA", "INICIAR IA", "PARAR IA", "DIAGNÓSTICO", "NOVO JOGO", "PASSE", "DRIBLE", "LANÇAMENTO", "CRUZAMENTO", "FINALIZAR", "MAESTRO LAB", "FOOTBALL INTELLIGENCE LAB"):
        assert label in app, f"controle ausente: {label}"
    assert "ScreenManager" in app and "_poll" in app and "open_diagnostics" in app


def test_workflow_file_exists_and_has_expected_steps():
    workflow_path = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")
    assert "buildozer" in content and "android debug" in content
    assert "upload-artifact" in content and "workflow_dispatch" in content


def test_main_launcher_imports_app_correctly():
    launcher = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.main_v2 import MaestroMobileApp" in launcher


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn): fn()
    print("=== TODOS OS TESTES DE EMPACOTAMENTO/UI PASSARAM ===")
