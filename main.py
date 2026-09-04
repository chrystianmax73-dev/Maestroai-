"""Launcher estável do Maestro — com diagnóstico de startup.

Nunca deixa o app fechar em silêncio: qualquer falha grava
maestro_startup.log e tenta mostrar a mensagem.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _log_path() -> Path:
    candidates = []
    try:
        from android.storage import app_storage_path  # type: ignore
        candidates.append(Path(app_storage_path()))
    except Exception:
        pass
    candidates.extend((Path.home(), Path("/sdcard"), Path.cwd()))
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            p = base / "maestro_startup.log"
            # Não apagar um log anterior antes de descobrir que a abertura falhou.
            if not p.exists():
                p.write_text("", encoding="utf-8")
            return p
        except Exception:
            continue
    return Path.cwd() / "maestro_startup.log"


def _log(msg: str, log_file: Path | None = None) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} | {msg}\n"
    try:
        sys.stderr.write(line)
        sys.stderr.flush()
    except Exception:
        pass
    if log_file is not None:
        try:
            with log_file.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            pass


def main() -> int:
    log_file = _log_path()
    _log(f"START path={log_file}", log_file)
    _log(f"python={sys.version}", log_file)
    _log(f"argv={sys.argv}", log_file)
    _log(f"platform={sys.platform}", log_file)

    try:
        _log("import app.main ...", log_file)
        from app.main import MaestroMobileApp
        _log("MaestroMobileApp import OK", log_file)
        app = MaestroMobileApp()
        _log("MaestroMobileApp() construído", log_file)
        app.run()
        _log("app.run() encerrou normalmente", log_file)
        return 0
    except BaseException as exc:
        # Captura também SystemExit/KeyboardInterrupt para não perder a causa
        # durante bootstrap. O traceback completo fica persistido localmente.
        tb = traceback.format_exc()
        _log(f"FATAL: {exc!r}", log_file)
        _log(tb, log_file)
        try:
            from kivy.app import App
            from kivy.uix.label import Label

            class CrashApp(App):
                def build(self):
                    label = Label(
                        text=f"MAESTRO FALHOU AO INICIAR\n\n{exc}\n\nVeja maestro_startup.log",
                        halign="center",
                        valign="middle",
                    )
                    label.bind(size=lambda *_: setattr(label, "text_size", label.size))
                    return label

            CrashApp().run()
        except BaseException as exc2:
            _log(f"CrashApp também falhou: {exc2!r}", log_file)
            _log(traceback.format_exc(), log_file)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
