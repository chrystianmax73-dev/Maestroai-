# Maestro Mobile — Vertical Slice (v0.1)

Protótipo Android (e desktop) que executa o **MaestroGridEnv** validado, com interface Kivy.

## Objetivo desta etapa

- Abrir no celular → iniciar partida → ver campo/jogadores/bola/placar  
- Executar as 5 ações do ambiente  
- Receber resultado e atualizar a tela  
- Rejeitar ações inválidas sem corromper estado  
- Gerar **APK** instalável offline  

**Não** inclui Tactical Engine, IA nem regras defensivas novas.

---

## Estrutura do projeto

```
maestro_mobile/
├── main.py                 # launcher (desktop + Buildozer)
├── requirements.txt
├── buildozer.spec
├── README.md
├── maestro/                # NÚCLEO — lógica oficial (não alterar sem marcar)
│   ├── __init__.py
│   └── maestro_grid_env_v2.py
├── app/
│   └── main.py             # interface Kivy (UI only)
└── tests/
    └── test_env_integration.py
```

### Separação de responsabilidades

| Camada | Arquivo | Papel |
|--------|---------|--------|
| Motor / regras | `maestro/maestro_grid_env_v2.py` | Fonte oficial. Validação, resolução, posse, métricas. |
| Interface | `app/main.py` | Só observa `GameState` e chama `reset()` / `step(Action)`. |
| Cursor futuro | `controlled_player_id` na UI | Já existe; independente de `ball.owner_id`. |

**Nenhuma alteração silenciosa foi feita no núcleo.** O arquivo `maestro_grid_env_v2.py` é a baseline congelada (seed=42, invariantes preservados).

---

## Como rodar no computador

```bash
cd maestro_mobile
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Ou, para só validar a lógica:

```bash
python tests/test_env_integration.py
```

---

## Como gerar o APK (Android)

Requisitos no host de build (recomendado: Ubuntu 22.04 ou WSL2):

- Python 3.10+
- Buildozer (`pip install buildozer`)
- Dependências de sistema: ver [docs Buildozer](https://buildozer.readthedocs.io/)
- Android SDK / NDK (Buildozer baixa automaticamente na primeira vez)

```bash
cd maestro_mobile
pip install buildozer cython
buildozer android debug
```

O APK sai em:

```
bin/maestrogrid-0.1.0-arm64-v8a-debug.apk
```

Instale no celular:

```bash
adb install -r bin/maestrogrid-0.1.0-*.apk
```

Ou copie o arquivo e instale manualmente (permitir “fontes desconhecidas”).

> **Nota:** a primeira compilação pode demorar 20–40 min (download de NDK/SDK). Compilações seguintes são bem mais rápidas.

---

## Uso no app

1. Ao abrir, a partida inicia automaticamente (seed=42).  
2. Toque em **PASSE / DRIBLE / LANÇAR / CRUZAR / FINALIZAR**.  
3. Quando a ação precisar de alvo, botões de destino aparecem na barra inferior.  
4. Resultado (sucesso, falha, gol, inválida) aparece no status.  
5. **RESET** reinicia a partida.

### Cursor (preparação futura)

- A UI já mantém `controlled_player_id`.  
- Hoje ele acompanha o dono da bola do time do usuário.  
- Quando implementarmos defesa, bastará permitir selecionar qualquer jogador do time **sem** mudar a regra do ambiente de que só o `owner` pode executar ação com bola.

---

## Testes executados

Ver `tests/test_env_integration.py` e a seção de resultados no relatório entregue junto com este README.

---

## O que é provisório

- Layout visual simples (prioridade = funcionar).  
- Seleção de alvo por botões (não por toque no campo).  
- Time do usuário fixo em “A”.  
- Sem sons, animações ou Tactical Engine.

## O que já está preparado para o cursor defensivo

- Campo `controlled_player_id` na UI e no `FieldWidget` (anel visual reservado).  
- Ações ainda obrigatoriamente via `owner` (contrato atual do env).  
- Separação clara motor × interface permite evoluir o cursor sem reescrever regras.
