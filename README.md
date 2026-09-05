# Maestro (v0.4)

Simulador de futebol offline em grade discreta, com interface Kivy
(Home → Laboratório), agente autônomo (`HeuristicAgent`) e build de
APK Android via GitHub Actions.

Para o diagrama completo da arquitetura, o porquê do crash de startup
corrigido e o ponto de integração isolado da camada de captura de
tela, veja **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## O que é o Maestro

`MaestroGridEnv` (`maestro/maestro_grid_env_v2.py`) é o núcleo: um
ambiente estilo Gym (`reset()` / `step(Action)`), 100% autocontido,
sem rede. Duas equipes disputam a bola numa grade; a cada passo, o
jogador com a posse executa **PASSE**, **DRIBLE**, **LANÇAMENTO**,
**CRUZAMENTO** ou **FINALIZAR**. Esse núcleo não foi alterado desde a
v0.1 — só é consumido pela API pública já existente.

`HeuristicAgent` (`maestro/heuristic_agent.py`) decide ações usando só
essa API pública, e consegue jogar a partida inteira sozinho (os dois
times), sem intervenção manual.

## Interface

- **Home**: estado dos módulos (Simulador/Agente prontos, Visão não
  incluída nesta build) e acesso ao Laboratório.
- **Laboratório**: campo, placar, controles de partida (JOGAR SOZINHO
  / PAUSAR / NOVO JOGO), ações manuais (PASSE/DRIBLE/LANÇAMENTO/
  CRUZAMENTO/FINALIZAR), e acesso a Diagnóstico e Agente.
- **Diagnóstico**: métricas reais do simulador; qualquer coisa que
  dependeria de captura de tela aparece como `N/D` — nunca um número
  inventado.

## Camada de visão (genérica, testável sem Android)

```
FrameSource -> ScreenPerception.analyze() -> PerceptionResult
```

`maestro/vision/screen_perception.py` faz a análise (campo, linhas,
bola, cores de time) a partir de `(largura, altura, pixel_at)` — não
sabe nada sobre Kivy, Android ou de onde o frame veio.

`maestro/vision/frame_source.py` define o contrato `FrameSource`
(`start`/`get_frame`/`stop`) com duas implementações genéricas:
`SyntheticFrameSource` (cena sintética determinística, para testes) e
`FileFrameSource` (lê imagens fornecidas explicitamente no disco).

Um adapter de captura real de tela Android (`services/capture.py`,
`android_src/`, `maestro/vision/capture_controller.py`) existe no
repositório mas **não é importado nem empacotado** nesta build — ver
ARCHITECTURE.md para o porquê e como retomar isso seguindo o mesmo
contrato de `FrameSource`.

## Estrutura do projeto

```
maestro_mobile/
├── main.py                      # launcher com diagnóstico de startup
├── buildozer.spec
├── requirements.txt
├── ARCHITECTURE.md
├── .github/workflows/build-apk.yml
├── maestro/
│   ├── maestro_grid_env_v2.py   # núcleo — não alterado
│   ├── heuristic_agent.py       # IA
│   └── vision/
│       ├── screen_perception.py # análise genérica de frame
│       └── frame_source.py      # FrameSource + Synthetic/File
├── app/main.py                  # interface Kivy (Home + Laboratório)
├── services/capture.py          # ISOLADO — não empacotado
├── android_src/                 # ISOLADO — não empacotado
└── tests/
    ├── test_env_integration.py
    ├── test_heuristic_agent.py
    ├── test_screen_perception.py
    ├── test_frame_source.py
    └── test_packaging.py
```

## Como executar localmente

```bash
cd maestro_mobile
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Só a lógica, sem GUI:

```bash
python tests/test_env_integration.py
python tests/test_heuristic_agent.py
python tests/test_screen_perception.py
python tests/test_frame_source.py
python tests/test_packaging.py
```

## Como gerar o APK

**Via GitHub Actions (recomendado):** o workflow
`.github/workflows/build-apk.yml` roda os testes, builda com
Buildozer e publica o `.apk` como artifact da execução — automático a
cada push em `main`/`feat/**`, ou manualmente em **Actions → Build
Android APK → Run workflow**. O workflow nunca modifica arquivos do
projeto durante a execução: builda exatamente o código commitado.

**Localmente** (Ubuntu 22.04/WSL2):

```bash
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev cmake libffi-dev libssl-dev
pip install buildozer cython
buildozer android debug
```

O APK sai em `bin/*.apk`. Primeira compilação baixa NDK/SDK e leva
20–40 min.

## Fora de escopo

- Captura de tela de aplicativos de terceiros, automação de jogos
  online, ou qualquer controle de aplicativo externo — deliberadamente
  não implementado (ver ARCHITECTURE.md).
- Sem sons, animações ou rede.
