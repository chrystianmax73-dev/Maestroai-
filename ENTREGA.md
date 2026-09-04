# Entrega — Maestro Mobile Vertical Slice (v0.1)

Data: 2026-08-09

## 1. Arquivos finais

```
maestro_mobile/
├── main.py                          # launcher desktop + Buildozer
├── requirements.txt
├── buildozer.spec                   # configuração de APK
├── README.md
├── ENTREGA.md                       # este arquivo
├── maestro/
│   ├── __init__.py
│   └── maestro_grid_env_v2.py       # NÚCLEO INALTERADO (baseline)
├── app/
│   └── main.py                      # interface Kivy (UI only)
└── tests/
    └── test_env_integration.py      # 10 testes de contrato
```

## 2. Estrutura e arquitetura

| Camada | Responsabilidade | Alteração nesta etapa? |
|--------|------------------|------------------------|
| `maestro/maestro_grid_env_v2.py` | Regras oficiais do jogo | **Não** — baseline congelada |
| `app/main.py` | Interface + orquestração de ações | **Sim** — novo |
| `controlled_player_id` | Reserva para cursor futuro | Preparado, sem lógica defensiva |

Separação rigorosa: a UI só chama `env.reset()` e `env.step(Action)`. Toda validação, probabilidade, posse e gol continuam 100% no ambiente.

## 3. Instruções — executar no computador

```bash
cd maestro_mobile
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Validação rápida da lógica (sem GUI):

```bash
python tests/test_env_integration.py
```

## 4. Instruções — gerar o APK

Host recomendado: Ubuntu 22.04 ou WSL2 com ~8 GB livres.

```bash
# uma vez
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
pip install buildozer cython

cd maestro_mobile
buildozer android debug
```

APK gerado em:

```
bin/maestrogrid-0.1.0-arm64-v8a-debug.apk
```

Instalação:

```bash
adb install -r bin/maestrogrid-0.1.0-*.apk
```

Ou copie o `.apk` para o celular e instale (ativar “fontes desconhecidas”).

**Nesta sessão de sandbox não foi possível gerar o APK binário** (ausência de Android NDK/SDK e ambiente de build completo). O código e o `buildozer.spec` estão prontos para compilação no host do usuário.

## 5. APK

Não gerado aqui. Use as instruções da seção 4.

## 6. Lista de testes executados

| # | Teste | Resultado |
|---|-------|-----------|
| 1 | Inicialização (campo, jogadores, bola, estado) | **PASS** |
| 2 | Passe válido | **PASS** |
| 3 | Drible válido | **PASS** |
| 4 | Lançamento | **PASS** |
| 5 | Cruzamento | **PASS** |
| 6 | Finalização | **PASS** |
| 7 | Ação inválida (estado preservado) | **PASS** |
| 8 | Reinicialização | **PASS** |
| 9 | Sequência de ações consecutivas | **PASS** |
| 10 | Reprodutibilidade (seed=42) | **PASS** |

Comando: `python tests/test_env_integration.py`  
Saída: `=== TODOS OS 10 TESTES PASSARAM ===`

## 7. Resultado de cada teste (resumo)

- **1**: `reset()` devolve estado com 4+4 jogadores, posse A, bola com owner.
- **2–6**: Cada tipo de ação retorna `valid=True` e campos esperados no `info`.
- **7**: Ação de jogador sem bola → `valid=False`, bola/posições inalteradas (só `time_step` avança, como no contrato do env).
- **8**: Segundo `reset()` zera `time_step` e reconstrói estado.
- **9**: 5 steps consecutivos mantêm sincronia estado ↔ info.
- **10**: Duas execuções com seed=42 produzem sequência idêntica de (ação, success, goal, owner, possession).

## 8. Problemas encontrados

- Nenhum no núcleo.
- UI: seleção de alvo ainda por botões (não por toque no campo) — provisório e aceitável para a vertical slice.
- Buildozer: primeira compilação exige download grande de NDK; deve ser feita no ambiente do usuário.

## 9. Partes provisórias

- Visual simples (cores sólidas, sem animação).
- Time do usuário fixo em “A”.
- Sem sons / haptic.
- Alvos de lançamento/drible listados em barra horizontal (não grid interativo).
- Sem Tactical Engine nesta etapa (conforme prioridade).

## 10. Preparado para cursor defensivo futuro

- `controlled_player_id` existe na App e no `FieldWidget`.
- Anel visual (`CURSOR_RING`) já é desenhado quando o id é válido.
- A UI **não** acopla “jogador controlado” a “dono da bola” de forma irreversível: hoje o controlado *acompanha* o owner do time do usuário, mas a variável é independente.
- Quando a lógica de cursor (ALTERAR_CURSOR, CURSOR_ATIVO_MIN/MAX) for adicionada ao ambiente ou à camada de decisão, a interface só precisará:
  1. Atualizar `controlled_player_id` na troca de cursor;
  2. Continuar enviando `actor_id = ball.owner_id` enquanto o contrato do env exigir posse para ações com bola;
  3. No futuro, permitir ações defensivas do jogador controlado *sem* bola.

Nenhuma barreira arquitetural foi criada contra isso.

---

## Classificação de mudanças

| Item | Classificação |
|------|----------------|
| `maestro/maestro_grid_env_v2.py` | Lógica do ambiente — **cópia da baseline, zero alteração** |
| `app/main.py`, launcher, tests, buildozer | **Interface / mobile** |

Prioridade atendida: **FUNCIONAR → testar integração → depois refinar visual e cursor**.
