"""
Smoke tests de empacotamento e arquitetura.

Estes testes validam duas coisas ao mesmo tempo:

1. O app compilável (Kivy + simulador + IA) tem uma configuração de
   build coerente e não depende, em nenhum ponto, do módulo de captura
   de tela Android.
2. Os arquivos-fonte do módulo de captura (services/capture.py,
   android_src/, maestro/vision/capture_controller.py) continuam
   presentes no repositório — não foram apagados — mas ficam de fato
   fora do binário: nem importados por app/main.py, nem referenciados
   em buildozer.spec (sem "services=", sem "android.add_src=", sem as
   permissões de overlay/MediaProjection).

NOTA: uma versão anterior deste arquivo fazia o oposto — exigia que
app/main.py importasse CaptureController e chamasse request_capture(),
e que buildozer.spec declarasse o serviço de captura com as permissões
SYSTEM_ALERT_WINDOW/FOREGROUND_SERVICE_MEDIA_PROJECTION. Isso é
incompatível com a arquitetura atual (captura isolada, não conectada
ao app distribuído), então essas asserções foram substituídas pelas
condições opostas — não porque o build estivesse falhando por causa
delas, mas porque validavam um comportamento que este build não tem
mais por decisão de escopo.
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
    app = parser["app"]
    required = [
        "title", "package.name", "package.domain", "source.dir", "version",
        "requirements", "android.api", "android.minapi", "android.ndk", "android.archs",
    ]
    missing = [k for k in required if k not in app]
    assert not missing, f"buildozer.spec sem as chaves: {missing}"
    assert "kivy" in app["requirements"] and "python3" in app["requirements"]
    print("TESTE PACKAGING 1 OK — chaves obrigatórias do buildozer.spec presentes")


def test_buildozer_spec_does_not_package_capture_module():
    parser = configparser.ConfigParser()
    parser.read(ROOT / "buildozer.spec", encoding="utf-8")
    app = parser["app"]
    assert "services" not in app, "build não deve declarar o serviço de captura Android"
    assert "android.add_src" not in app, "build não deve compilar android_src/ (Java de captura)"
    perms = app.get("android.permissions", "")
    for forbidden in ("SYSTEM_ALERT_WINDOW", "FOREGROUND_SERVICE_MEDIA_PROJECTION", "FOREGROUND_SERVICE"):
        assert forbidden not in perms, f"permissão de captura não deveria estar no build: {forbidden}"
    patterns = parser["app"].get("source.include_patterns", "")
    assert "services/**" not in patterns
    assert "android_src/**" not in patterns
    print("TESTE PACKAGING 2 OK — build não referencia serviço/permissões/fontes de captura")


def test_capture_sources_still_exist_but_are_isolated():
    """Confirma que nada foi apagado — só desconectado do build."""
    for rel in (
        "services/capture.py",
        "android_src/org/maestro/capture/CaptureActivity.java",
        "android_src/org/maestro/capture/ProjectionCallback.java",
        "maestro/vision/capture_controller.py",
    ):
        assert (ROOT / rel).exists(), f"arquivo isolado não deveria ter sido removido: {rel}"
    print("TESTE PACKAGING 3 OK — arquivos de captura preservados no repositório (não apagados)")


def test_app_main_does_not_wire_capture():
    app_src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    # Um comentário explicando o isolamento pode mencionar o nome do
    # módulo — o que não pode existir é o IMPORT ou a CHAMADA reais.
    assert "from maestro.vision.capture_controller import" not in app_src
    assert "CaptureController(" not in app_src  # instanciação
    assert "request_capture()" not in app_src
    print("TESTE PACKAGING 4 OK — app/main.py não importa nem instancia o CaptureController")


def test_app_main_has_lab_controls():
    app_src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    for label in (
        "ENTRAR NO LABORATÓRIO", "JOGAR SOZINHO", "NOVO JOGO",
        "PASSE", "DRIBLE", "LANÇAMENTO", "CRUZAMENTO", "FINALIZAR",
    ):
        assert label in app_src, f"controle de UI ausente: {label}"
    assert "ScreenManager" in app_src and "open_diagnostics" in app_src
    print("TESTE PACKAGING 5 OK — controles do laboratório presentes na UI")


def test_workflow_file_has_no_self_patching_step():
    workflow_path = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")
    assert "buildozer" in content and "android debug" in content
    assert "upload-artifact" in content and "workflow_dispatch" in content
    # O CI nunca deve alterar/commitar arquivos do projeto durante a execução —
    # o código testado e empacotado tem que ser exatamente o commitado.
    assert "git commit" not in content
    assert "git push" not in content
    assert "Enforce stable capture integration" not in content
    print("TESTE PACKAGING 6 OK — workflow não contém etapa de auto-patch/commit")


def test_main_launcher_has_startup_diagnostics():
    launcher = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.main import MaestroMobileApp" in launcher
    assert "maestro_startup.log" in launcher
    assert "traceback.format_exc()" in launcher
    assert "except BaseException" in launcher
    print("TESTE PACKAGING 7 OK — launcher raiz com diagnóstico de startup robusto")


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
    print("\n=== TODOS OS TESTES DE EMPACOTAMENTO/ARQUITETURA PASSARAM ===")
