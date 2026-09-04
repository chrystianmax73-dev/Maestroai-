# Maestro Mobile (v0.2)

Simulador de futebol offline em grade discreta, com interface Kivy para
Android/desktop. A v0.2 adiciona um **modo autônomo** (a IA joga sozinha)
e um pipeline de **build automático do APK** via GitHub Actions.

## O que é o Maestro

O `MaestroGridEnv` é um ambiente de simulação estilo Gym (`reset()` /
`step(Action)`), 100% autocontido — sem rede, sem processos externos,
sem interação com jogos ou aplicativos de terceiros. Duas equipes (A e
B) disputam a bola numa grade; a cada passo, o jogador com a posse
executa uma das cinco ações:

- **PASSE** — para um companheiro
- **DRIBLE** — avança para uma célula próxima
- **LANÇAMENTO** — bola longa para uma célula alvo
- **CRUZAMENTO** — cruzamento lateral para um companheiro
- **FINALIZAR** — chute a gol

Cada ação tem probabilidade de sucesso calculada a partir de pressão
adversária, distância, e se a linha de passe está aberta. O núcleo
(`maestro/maestro_grid_env_v2.py`) é a baseline oficial e **não foi
alterado** na v0.2 — só foi consumido através da API pública já
existente.

## Como funciona o modo autônomo

A v0.2 adiciona `maestro/heuristic_agent.py` — um `HeuristicAgent` que
decide ações inteiramente a partir da API pública do ambiente
(`state.owner()`, `pressure_on()`, `passing_lane_open()`,
`open_space_around()`, `cell_distance()`, etc.), sem ler nem alterar
nada privado do núcleo. Ele pontua candidatos de PASSE, CRUZAMENTO,
LANÇAMENTO e DRIBLE, prioriza FINALIZAR quando está em zona de ataque
com pouca pressão, e sempre devolve uma ação válida (nunca deixa o
ator sem opção).

Por decidir sempre para quem estiver com a posse no momento, o agente
consegue simular a partida inteira sozinho — os dois times — no modo
autônomo (auto-jogo/self-play). Também pode ser restrito a um único
time (`HeuristicAgent(team="A")`) para cenários futuros.

Na interface:

- **JOGAR SOZINHO** — liga a IA. Um `Clock.schedule_interval` do Kivy
  pede uma ação ao agente a cada tick e a executa pelo mesmo caminho
  das ações manuais (`_execute()`), então toda a validação e
  atualização de tela já existentes continuam valendo sem duplicação.
- **PARAR IA** — desliga e devolve o controle manual imediatamente.
- **Velocidade** — 0.5x / 1x / 2x / 4x, ajusta o intervalo entre
  decisões da IA em tempo real (inclusive com a IA já rodando).
- Enquanto a IA está ativa, os botões de ação manual ficam
  desabilitados (evita dois "atores" decidindo ao mesmo tempo); ao
  parar, voltam a funcionar normalmente.
- Placar, tempo (`time_step`) e posse continuam visíveis no topo; um
  rótulo "Modo: MANUAL" / "Modo: IA (autônoma) — Nx" mostra o status
  atual da partida a qualquer momento.

Tudo roda localmente — nenhuma chamada de rede, nenhuma API externa,
nenhum serviço de terceiros.

## Estrutura do projeto

```
maestro_mobile/
├── main.py                          # launcher (desktop + Buildozer)
├── requirements.txt
├── buildozer.spec
├── README.md
├── ENTREGA.md                       # relatório da entrega v0.1
├── .github/workflows/
│   └── build-apk.yml                # build automático do APK (CI)
├── maestro/                         # NÚCLEO — não alterado na v0.2
│   ├── __init__.py
│   ├── maestro_grid_env_v2.py       # ambiente oficial (baseline)
│   └── heuristic_agent.py           # IA do modo autônomo (novo)
├── app/
│   └── main.py                      # interface Kivy (manual + IA)
└── tests/
    ├── test_env_integration.py      # testes do núcleo (10 testes)
    ├── test_heuristic_agent.py      # testes da IA (novo)
    └── test_packaging.py            # smoke tests de buildozer.spec/workflow (novo)
```

### Separação de responsabilidades

| Camada | Arquivo | Papel |
|--------|---------|--------|
| Motor / regras | `maestro/maestro_grid_env_v2.py` | Fonte oficial. Validação, resolução, posse, métricas. **Congelada.** |
| IA | `maestro/heuristic_agent.py` | Decide ações só via API pública do ambiente. Não lê/altera estado privado. |
| Interface | `app/main.py` | Observa `GameState`, chama `reset()`/`step(Action)`, manual ou via IA. |
| Cursor futuro | `controlled_player_id` na UI | Já existe; independente de `ball.owner_id`. |

## Como executar localmente

```bash
cd maestro_mobile
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Só validar a lógica (sem GUI):

```bash
python tests/test_env_integration.py
python tests/test_heuristic_agent.py
python tests/test_packaging.py
```

## Como gerar o APK

### Localmente

Requisitos no host de build (recomendado: Ubuntu 22.04 ou WSL2, ~8 GB livres):

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
pip install buildozer cython

cd maestro_mobile
buildozer android debug
```

O APK sai em `bin/maestrogrid-0.2.0-arm64-v8a-debug.apk`. Instale com
`adb install -r bin/maestrogrid-0.2.0-*.apk`, ou copie o arquivo pro
celular e instale manualmente (ativar "fontes desconhecidas"). A
primeira compilação baixa o NDK/SDK e pode levar 20–40 min.

### Via GitHub Actions (recomendado — não exige nada instalado)

O workflow `.github/workflows/build-apk.yml` builda o APK automaticamente:

1. Roda `python3 tests/test_env_integration.py` e
   `python3 tests/test_heuristic_agent.py` — se algum teste falhar, o
   build para aqui.
2. Executa `buildozer android debug` no runner (Ubuntu), via a action
   `ArtemSBulgakov/buildozer-action`.
3. Publica o `.apk` gerado como **artifact** da execução.

Como usar:

- Automático a cada `push` que altere `maestro/`, `app/`, `main.py`,
  `buildozer.spec` ou `requirements.txt`, em `main` ou em qualquer
  branch `feat/**`.
- Ou manualmente: aba **Actions** do repositório → **Build Android
  APK** → **Run workflow**.
- Ao terminar, baixe o `.apk` na seção **Artifacts** da execução (fica
  disponível por 30 dias).

> **Importante:** o build real de APK exige Android SDK/NDK completos
> e não pôde ser executado no ambiente de desenvolvimento usado para
> preparar esta v0.2 (sandbox sem acesso a esses componentes) — por
> isso o workflow é a via recomendada: ele roda num runner do GitHub
> que já traz (ou baixa) tudo que é necessário. A lógica do jogo, da
> IA e a construção da interface Kivy (com renderização real via
> Xvfb) foram validadas localmente antes do commit; a etapa que falta
> validar de fato é a compilação Android em si, que só o CI consegue
> rodar até o fim.

## Uso no app

1. Ao abrir, a partida inicia automaticamente (seed=42).
2. Modo manual: toque em **PASSE / DRIBLE / LANÇAR / CRUZAR /
   FINALIZAR**; quando a ação precisa de alvo, botões de destino
   aparecem na barra inferior.
3. Modo autônomo: toque em **JOGAR SOZINHO** para a IA assumir;
   ajuste a velocidade (0.5x–4x) a qualquer momento; toque em **PARAR
   IA** para retomar o controle manual.
4. Placar, tempo, posse e modo atual ficam sempre visíveis no topo.
5. **RESET** reinicia a partida (desabilitado enquanto a IA está
   rodando — pare a IA primeiro).

### Cursor (preparação futura)

- A UI mantém `controlled_player_id`, independente de `ball.owner_id`.
- Hoje acompanha o dono da bola do time do usuário.
- Quando a defesa for implementada, bastará permitir selecionar
  qualquer jogador do time controlado, sem mudar a regra atual do
  ambiente de que só o `owner` executa ações com bola.

## O que é provisório / fora de escopo

- Layout visual simples (prioridade = funcionar).
- Seleção de alvo por botões (não por toque no campo).
- Time do usuário fixo em "A".
- Sem sons, animações ou Tactical Engine.
- **Este projeto é um simulador offline e controlado.** Não implementa
  (e não deve implementar) automação de jogos online de terceiros,
  captura de tela de apps externos, bypass de anti-cheat ou qualquer
  mecanismo de controle de jogos reais. Um código legado de automação
  existe apenas como referência histórica e não foi reaproveitado
  nesta versão.
