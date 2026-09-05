# Arquitetura — Maestro (v0.4)

```
Kivy (app/main.py)
  │
  └── MaestroMobileApp
       │
       ├── Simulator   → maestro/maestro_grid_env_v2.py (MaestroGridEnv, Action,
       │                 ActionType, GameState) — núcleo, não alterado
       │
       ├── Agent       → maestro/heuristic_agent.py (HeuristicAgent) — decide só
       │                 via API pública do MaestroGridEnv
       │
       ├── Vision      → maestro/vision/
       │     ├── screen_perception.py  (ScreenPerception) — análise de
       │     │                          frame genérica, determinística, sem
       │     │                          saber de Android/Kivy/eFootball
       │     └── frame_source.py       (FrameSource, SyntheticFrameSource,
       │                                FileFrameSource) — origem de frame
       │                                genérica, testável sem Android
       │
       ├── Diagnostics → popup em app/main.py, lê métricas reais do
       │                 simulador; mostra "N/D" onde não há dado real
       │                 (nunca inventa número)
       │
       └── Android adapters (ISOLADOS — não compilados nesta build)
             ├── maestro/vision/capture_controller.py
             ├── services/capture.py
             └── android_src/org/maestro/capture/*.java
```

## Ponto de integração isolado

`services/capture.py`, `android_src/` e `capture_controller.py`
implementam uma captura de tela real via `MediaProjection` + overlay
próprio. Esses arquivos **continuam no repositório** — não foram
apagados — mas:

- `app/main.py` não os importa nem os referencia.
- `buildozer.spec` não declara o serviço (`services=`) nem inclui as
  fontes Java (`android.add_src=`), então o APK gerado por este
  workflow **não contém** esse código nem as permissões associadas
  (`SYSTEM_ALERT_WINDOW`, `FOREGROUND_SERVICE_MEDIA_PROJECTION`).
- `tests/test_packaging.py` valida ativamente essa separação (build
  sem captura, arquivos preservados no repo, `app/main.py` sem
  wiring).

Qualquer implementação futura de uma origem de frame real deveria
seguir o mesmo contrato de `FrameSource` (`start()` / `get_frame()` /
`stop()`), mas isso está fora do escopo do que este projeto entrega.

## Por que o crash de startup acontecia

`LabScreen.__init__` (em `app/main.py`) construía um `FloatLayout`
passando `padding=dp(8))`. `FloatLayout` do Kivy **não tem** a
propriedade `padding` (ela existe em `BoxLayout`/`GridLayout`, não em
`FloatLayout`) — o construtor lançava `TypeError` na hora de montar a
tela do Laboratório, dentro de `build()`, antes da UI aparecer. Isso
foi reproduzido localmente (Kivy real + Xvfb, não just parsing) e
confirmado como a causa: com essa única linha corrigida
(`FloatLayout()` sem `padding`), o app constrói, navega Home→Lab,
reseta a partida, liga/desliga a IA, executa ações manuais e abre os
diagnósticos sem exceção.
