"""
Testes de empacotamento (smoke tests).

NÃO geram o .apk de verdade — isso exige Android SDK/NDK completos,
disponíveis apenas no runner do GitHub Actions (ver
.github/workflows/build-apk.yml). Aqui validamos só que os arquivos
de configuração usados por esse pipeline estão bem formados, para
detectar erro de digitação/config antes de gastar tempo de CI.
"""

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
        "title",
        "package.name",
        "package.domain",
        "source.dir",
        "version",
        "requirements",
        "android.api",
        "android.minapi",
        "android.ndk",
        "android.archs",
    ]
    missing = [k for k in required if k not in app]
    assert not missing, f"buildozer.spec sem as chaves: {missing}"

    assert "kivy" in app["requirements"], "kivy precisa estar em requirements"
    assert "python3" in app["requirements"], "python3 precisa estar em requirements"
    print("TESTE PACKAGING 1 OK — buildozer.spec com todas as chaves obrigatórias")


def test_buildozer_source_patterns_include_project_packages():
    parser = configparser.ConfigParser()
    parser.read(ROOT / "buildozer.spec", encoding="utf-8")
    patterns = parser["app"].get("source.include_patterns", "")
    assert "maestro/**" in patterns
    assert "app/**" in patterns
    print("TESTE PACKAGING 2 OK — source.include_patterns cobre maestro/ e app/")


def test_workflow_file_exists_and_has_expected_steps():
    workflow_path = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert workflow_path.exists(), "workflow de build do APK não encontrado"
    content = workflow_path.read_text(encoding="utf-8")
    assert "buildozer android debug" in content
    assert "upload-artifact" in content
    assert "workflow_dispatch" in content
    print("TESTE PACKAGING 3 OK — workflow do GitHub Actions presente e com os passos esperados")


def test_main_launcher_imports_app_correctly():
    launcher = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.main import MaestroMobileApp" in launcher
    print("TESTE PACKAGING 4 OK — launcher raiz aponta para app.main.MaestroMobileApp")


if __name__ == "__main__":
    test_buildozer_spec_has_required_keys()
    test_buildozer_source_patterns_include_project_packages()
    test_workflow_file_exists_and_has_expected_steps()
    test_main_launcher_imports_app_correctly()
    print("\n=== TODOS OS TESTES DE EMPACOTAMENTO PASSARAM ===")
