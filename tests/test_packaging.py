"""Testes de empacotamento e smoke tests da infraestrutura Android."""

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
    assert "app" in parser
    app = parser["app"]
    required = [
        "title", "package.name", "package.domain", "source.dir", "version",
        "requirements", "services", "android.api", "android.minapi",
        "android.ndk", "android.archs", "android.permissions",
        "android.add_src", "android.activity_class_name",
    ]
    missing = [k for k in required if k not in app]
    assert not missing, f"buildozer.spec sem as chaves: {missing}"
    assert "kivy" in app["requirements"]
    assert "python3" in app["requirements"]
    assert "capture:services/capture.py" in app["services"]
    assert "mediaProjection" in app["services"]
    assert "FOREGROUND_SERVICE_MEDIA_PROJECTION" in app["android.permissions"]
    assert "SYSTEM_ALERT_WINDOW" in app["android.permissions"]
    assert "CaptureActivity" in app["android.activity_class_name"]
    print("TESTE PACKAGING 1 OK — configuração Android de captura presente")


def test_buildozer_source_patterns_include_project_packages():
    parser = configparser.ConfigParser()
    parser.read(ROOT / "buildozer.spec", encoding="utf-8")
    patterns = parser["app"].get("source.include_patterns", "")
    assert "maestro/**" in patterns
    assert "app/**" in patterns
    assert "services/**" in patterns
    assert (ROOT / "android_src" / "org" / "maestro" / "capture" / "CaptureActivity.java").exists()
    assert (ROOT / "android_src" / "org" / "maestro" / "capture" / "ProjectionCallback.java").exists()
    print("TESTE PACKAGING 2 OK — fontes do serviço/Activity Android presentes")


def test_capture_service_is_read_only():
    service = (ROOT / "services" / "capture.py").read_text(encoding="utf-8")
    assert "MediaProjectionManager" in service
    assert "ImageReader" in service
    assert "TYPE_APPLICATION_OVERLAY" in service
    assert "inject" not in service.lower()
    assert "input" not in service.lower()
    print("TESTE PACKAGING 3 OK — captura/overlay sem injeção de entrada")


def test_workflow_file_exists_and_has_expected_steps():
    workflow_path = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert workflow_path.exists(), "workflow de build do APK não encontrado"
    content = workflow_path.read_text(encoding="utf-8")
    assert "buildozer android debug" in content
    assert "upload-artifact" in content
    assert "workflow_dispatch" in content
    print("TESTE PACKAGING 4 OK — workflow do GitHub Actions presente")


def test_main_launcher_imports_app_correctly():
    launcher = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.main import MaestroMobileApp" in launcher
    print("TESTE PACKAGING 5 OK — launcher raiz continua apontando para app.main")


if __name__ == "__main__":
    test_buildozer_spec_has_required_keys()
    test_buildozer_source_patterns_include_project_packages()
    test_capture_service_is_read_only()
    test_workflow_file_exists_and_has_expected_steps()
    test_main_launcher_imports_app_correctly()
    print("\n=== TODOS OS TESTES DE EMPACOTAMENTO PASSARAM ===")
