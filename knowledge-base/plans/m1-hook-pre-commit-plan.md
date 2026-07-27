---
slug: m1-hook-pre-commit
milestone_id: M1
created_at: 2026-07-27
goal: Instalar um hook de pre-commit com um comando e bloquear o commit que introduz um segredo, lendo o conteúdo em stage e nunca destruindo hook preexistente.
---

# Plan: M1 — Hook de pre-commit

## Goal

`gitsafety install` escreve `.git/hooks/pre-commit` e, a partir daí, `git commit` de um
arquivo que **introduz** uma chave AWS falha com exit code 1. O hook lê o conteúdo em
stage — não o disco —, recusa-se a sobrescrever hook preexistente, e `git commit
--no-verify` continua passando.

## Context

Segundo milestone. Depois do M1 o produto **protege de verdade**: até aqui ele varre
quando alguém pede; a partir daqui intercepta o commit.

As decisões de forma estão travadas pelo blueprint
`knowledge-base/discoveries/blueprints/m1-pre-commit-hook-blueprint.md` (SHIPPABLE 100.0),
cujos 6 ADRs este plano consome como entrada. O achado que mais muda o M1: o
`ROADMAP.md § M1` supunha `git show :arquivo`; os peers usam `git diff --staged`, e a
diferença é de **produto**, não de técnica — varrer o arquivo inteiro bloquearia todo
commit em repositório legado.

## Baseline Context (deep review of current state)

**Estado:** branch `develop`, tag `v0.1.0` cortada, working tree limpo. 92 testes verdes.
O M0 entregou `scan` funcionando sobre o sistema de arquivos; o M1 acrescenta a fronteira
com o **git**, que é a primeira fronteira de infraestrutura real do projeto.

### Files that will be touched

| File | LoC hoje | Último commit | Por que existe hoje | Invariantes a preservar |
|---|---|---|---|---|
| `src/gitsafety/errors.py` | 63 | `8789f6f` | `ExitCode` + hierarquia tipada | `ExitCode` 0/1/2 é contrato público; toda exceção nova DEVE carregar `exit_code` |
| `src/gitsafety/cli.py` | 118 | `2896f97` | Parser, render, exit | Saída mascarada por padrão; `--help` só mostra o que existe |
| `src/gitsafety/scanner.py` | 88 | `2d78996` | Compõe walker + rules | `ScanResult(findings, skipped)` é consumido por `cli.render` — assinatura NÃO pode quebrar |
| `src/gitsafety/finding.py` | 60 | `1e27e9f` | `Finding` + mascaramento | `Finding.line` é 1-based e valida `>= 1` |
| `src/gitsafety/git.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/staged.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/hook.py` (NOVO) | 0 | — | (a criar) | — |
| `tests/unit/test_git.py`, `test_staged.py`, `test_hook.py` (NOVOS) | 0 | — | (a criar) | — |
| `tests/functional/test_hook_e2e.py` (NOVO) | 0 | — | (a criar) | — |
| `benchmarks/bench_hook.py` (NOVO) | 0 | — | (a criar) | — |
| `README.md` | 249 | `644c2fd` | Contrato público | As marcas ✅/⏳ devem migrar quando a flag passar a existir |

### Current callers / dependents

- `cli.main` chama `scan_path`; é o único chamador. O M1 acrescenta um segundo caminho
  (`--staged`) e um segundo subcomando (`install`).
- `cli.render` consome `ScanResult`. Se o modo staged produzisse outro tipo, `render`
  quebraria — daí o ADR D9.
- Nenhum consumidor externo: `v0.1.0` não foi publicada no PyPI.

### Domain glossary

- **Stage / índice** — a área onde o `git add` coloca o conteúdo que será commitado; pode divergir do disco quando se usa `git add -p`.
- **Hunk** — bloco contíguo de um diff unificado, com cabeçalho `@@ -a,b +c,d @@` onde `c` é a primeira linha do lado novo.
- **Linha adicionada** — linha do diff prefixada por `+` (e que não seja o cabeçalho `+++`). É o único conteúdo que o hook varre.
- **Hook marker** — a string `gitsafety scan --staged`, presente em todo hook que escrevemos; é como reconhecemos o nosso próprio (ADR D4 do blueprint).
- **`--no-verify`** — flag nativa do git que pula os hooks; é o bypass de emergência e não deve ser combatida.
- **Repositório git** — diretório onde `git rev-parse --git-dir` responde com sucesso.

### Architecture boundaries affected

```
domínio        errors.py, rules.py, finding.py
aplicação      walker.py, scanner.py, staged.py     <- staged.py é novo
infraestrutura git.py                                <- PRIMEIRA fronteira de infra
interface      cli.py, hook.py, __main__.py         <- hook.py escreve no FS do usuário
```

- `git.py` é a primeira **fronteira de infraestrutura** do projeto: encapsula `subprocess`
  e o binário `git`. Nenhum outro módulo invoca `subprocess`.
- `staged.py` é aplicação: consome `git.py` e produz o mesmo `Finding` do M0.
- `hook.py` escreve em `.git/hooks/` — é o único módulo que muda o sistema de arquivos do
  usuário, e por isso o único que precisa de teste de estado degenerado (D6 do blueprint).
- DIP: `git.py` NÃO recebe interface abstrata. Só existe um git, não há segundo
  implementador previsto, e `rules/architecture.md § 2` proíbe abstração especulativa. Os
  testes usam repositório real (ADR D5 do blueprint), não mock.

## Prior Art & Related Work

| Fonte | O que aproveitamos | Citação |
|---|---|---|
| Blueprint do M1 | Os 6 ADRs (D1-D6) são entrada travada | `knowledge-base/discoveries/blueprints/m1-pre-commit-hook-blueprint.md` |
| gitleaks | Comando literal de leitura do stage e suas flags defensivas | `knowledge-base/references/gitleaks/sources/git.go:139-142` |
| talisman | Confirmação independente do mesmo comando + `--src-prefix` | `knowledge-base/references/talisman/gitrepo/gitrepo.go:47` |
| talisman | Forma do teste de aceitação: repo real, asserção sobre exit code | `knowledge-base/references/talisman/cmd/acceptance_test.go:64-99` |
| ggshield | Escrita do hook: shebang `sh`, corpo de uma linha, `"$@"`, `0o700` | `knowledge-base/references/ggshield/ggshield/cmd/install.py:344,350,351` |
| ggshield | Recusa de hook preexistente com mensagem que nomeia a saída | `knowledge-base/references/ggshield/ggshield/cmd/install.py:328-335` |
| ggshield | Marcador de auto-reconhecimento para idempotência | `knowledge-base/references/ggshield/ggshield/cmd/install.py:37-39` |
| ggshield | Proporção da suíte: 4 de 7 testes sobre estado preexistente | `knowledge-base/references/ggshield/tests/unit/cmd/test_install.py:34-141` |
| Blueprint do M0 | `ExitCode` e `Finding` reusados sem mudança | `knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md` |
| `rules/testing.md § 4.1` | Edge case × negative case no plano de teste | `rules/testing.md` |
| `rules/error-handling.md § 2` | Erros tipados na fronteira com o git | `rules/error-handling.md` |
| `rules/architecture.md § 2` | Por que `git.py` não recebe interface abstrata | `rules/architecture.md` |

## Objective

Ao fim do M1, num repositório git limpo, `gitsafety install` seguido de `git commit` de um
arquivo com chave AWS **falha com exit 1**, e `git commit --no-verify` passa — verificado
por teste de integração automatizado sobre repositório git real.

## ADRs

D1-D6 vêm do blueprint e são restatados aqui em forma executável; o texto integral está em
`knowledge-base/discoveries/blueprints/m1-pre-commit-hook-blueprint.md § ADRs`. D7-D9 são
deste plano.

### D1 — Ler o stage com `git diff --staged`, varrendo só linhas adicionadas

**Decisão:** `git diff --staged -U0 --no-ext-diff --src-prefix=a/ --dst-prefix=b/`, e
varrer apenas as linhas prefixadas por `+`.

**Rationale:** convergência dos dois peers (`gitleaks/sources/git.go:139-142`,
`talisman/gitrepo/gitrepo.go:47`). Cada flag é defensiva: `-U0` evita achar em linha de
contexto não tocada; `--no-ext-diff` ignora driver de diff do usuário; os prefixos
protegem contra `diff.noprefix=true` na config. Varrer só o adicionado faz o hook reclamar
do que se **introduz**, e não de segredo preexistente — decisivo para a north-star de
retenção do `ROADMAP.md`.

**Alternativas consideradas:** (a) `git show :arquivo` — resolve ler o índice, mas varre o
arquivo inteiro e bloqueia todo commit em repositório legado; (b) ler do disco — é o Risco
nº 1 literal, `git add -p` faz disco e índice divergirem; (c) `--staged` sem `-U0` —
contexto inalterado entra na varredura.

**Consequências:** é preciso parsear diff unificado e mapear números de linha. Segredo
preexistente fica para `scan` e `--history` (M5); o README precisa dizer isso.

### D2 — O hook é um script `sh` de uma linha

**Decisão:** `#!/bin/sh` + `gitsafety scan --staged "$@"`, permissão `0o700`.

**Rationale:** `install.py:344,350,351`. O M0 mediu 0,0145 ms por arquivo — o custo
dominante aqui é o startup do interpretador, que um hook em shell não paga quando o git
decide não executá-lo. Funciona com venv desativado, porque resolve pelo PATH. `"$@"`
repassa os argumentos do git; engoli-los quebra o contrato em silêncio.

**Alternativas consideradas:** (a) hook em Python com shebang do venv — amarra a um venv
que pode ser apagado e paga startup sempre; (b) shell invocando `python -m gitsafety` —
mesma amarração, sem ganho.

**Consequências:** o hook exige `gitsafety` no PATH. Se faltar, o erro vem do shell e é
pior — daí o D8.

### D3 — Recusar hook preexistente, imprimindo a linha a colar

**Decisão:** `install` recusa, sai com `USAGE_ERROR` (2) e imprime a linha exata a
acrescentar. Sem `--force`, sem `--append`.

**Rationale:** `docs/PRD.md § FR-2` decidiu recusar; `install.py:331-335` mostra **como** —
a mensagem nomeia a saída em vez de só informar o conflito. Nosso equivalente é a linha a
colar. `--force`/`--append` são dois knobs contra o teto do `docs/PRD.md § NFR-3`, e
destruir hook alheio é dano difícil de desfazer.

**Alternativas consideradas:** (a) `--force` — YAGNI e destrutivo; (b) `--append` — anexar
a script desconhecido pode inserir código depois de um `exit`; (c) delegação em cadeia
(`install.py:28-31`) — a melhor solução para coexistência, adiada por escopo e registrada.

**Consequências:** usuário com hook preexistente tem passo manual. É o custo de nunca
destruir configuração alheia.

### D4 — Marcador de auto-reconhecimento

**Decisão:** o hook contém `gitsafety scan --staged`; `install` procura essa string antes
de declarar conflito.

**Rationale:** `install.py:37-39` + `hook_invokes_ggshield()` em `:207-216`. Sem marcador,
`install` duas vezes acusa conflito com o próprio hook, empurrando o usuário para o
`--force` que o D3 decidiu não oferecer. O marcador é a própria linha de comando, não
metadado extra que pode ser removido sem quebrar nada.

**Alternativas consideradas:** (a) comentário `# gitsafety-managed` — metadado removível,
criando divergência entre marcador e realidade; (b) arquivo de estado paralelo — dois
artefatos para sincronizar.

**Consequências:** hook de terceiro contendo a string seria confundido com o nosso. Risco
aceito: a string é específica.

### D5 — Teste contra repositório git real, asserindo exit code

**Decisão:** teste de integração cria repositório git temporário, faz `git add`, dispara
`git commit`, asserta o código de saída. Sem mock do git.

**Rationale:** `talisman/cmd/acceptance_test.go:64-99`. O comportamento sob teste É a
interação com o git; mock testaria o mock. O Risco nº 1 (stage divergindo do disco) só se
manifesta num índice de verdade.

**Alternativas consideradas:** (a) mockar `subprocess` — cega justamente a fronteira que
importa; (b) asserir sobre texto — acopla o teste à formatação, quando o contrato com o
git é numérico.

**Consequências:** testes do M1 são mais lentos que os unitários. Ficam em
`tests/functional/`; a divisão de dois níveis do M0 acomoda sem mudança.

### D6 — Cobrir os estados degenerados antes do caminho feliz

**Decisão:** `install` recebe teste para hook já existente, caminho é diretório, fora de
repositório git, `.git/hooks/` inexistente, instalação repetida, e `gitsafety` fora do
PATH — além do caminho feliz.

**Rationale:** em `ggshield/tests/unit/cmd/test_install.py`, 4 de 7 testes cobrem "já
existe alguma coisa lá" (`:34,44,54,88,116,141`). No `install` o caminho feliz é trivial e
o valor está nos estados degenerados. `rules/testing.md § 4.1`.

**Alternativas consideradas:** (a) cobrir só o caminho feliz e tratar os degenerados como
"casos raros" — rejeitada: nenhum deles é raro na prática, porque `install` roda em
repositórios que já têm história e ferramenta configurada; (b) cobrir os degenerados com
um único teste parametrizado sobre "estado inválido" — rejeitada, cada estado exige uma
**mensagem de erro diferente**, e um teste parametrizado sobre "levanta alguma coisa"
seria exatamente o `pytest.raises(Exception)` que o `/code-quality` do M0 flagrou como
B017; (c) postergar os degenerados para o M2 — rejeitada, `install` é o comando que toca o
diretório de outra ferramenta, e o dano de sobrescrever acontece na primeira execução.

**Consequências:** mais teste de erro que de sucesso no `install`. É o esperado para um
comando que escreve no diretório de outra ferramenta.

### D7 — `git.py` é a fronteira de infraestrutura, sem abstração

**Decisão:** um módulo `git.py` encapsula toda invocação de `subprocess`. Nenhuma
interface abstrata, nenhuma injeção de dependência.

**Rationale:** `rules/architecture.md § 1` pede que infraestrutura seja isolada — daí o
módulo. Mas o `§ 2` proíbe abstração especulativa: existe **um** git, não há segundo
implementador previsto, e o ADR D5 já decidiu testar contra git real em vez de mock.
Interface com um implementador único e nenhum consumidor de teste é o anti-pattern
literal do `rules/architecture.md § 6`.

**Alternativas consideradas:** (a) `GitClient` como protocolo com implementação real e
fake — rejeitada, o fake seria usado só por testes que o D5 decidiu não escrever;
(b) chamar `subprocess` direto de `staged.py` e `hook.py` — rejeitada, espalha o
tratamento de erro do git por dois módulos.

**Consequências:** trocar a forma de falar com o git exige tocar um módulo. Aceitável: é
exatamente o que o isolamento compra.

### D8 — `install` valida o PATH na instalação, não no commit

**Decisão:** `install` verifica que `gitsafety` é resolvível no PATH e recusa com mensagem
específica se não for.

**Rationale:** consequência declarada do D2 — o hook em `sh` invoca `gitsafety` pelo PATH.
Se faltar, o git reporta `gitsafety: not found` do shell no meio de um commit, momento em
que o usuário está fazendo outra coisa e a mensagem não ajuda. Validar na instalação move
a falha para o momento em que a pessoa está justamente instalando.
`rules/error-handling.md § 3`: falhar cedo e claro.

**Alternativas consideradas:** (a) não validar — empurra a falha para o pior momento;
(b) escrever caminho absoluto do executável no hook — quebra quando o venv muda de lugar,
e o D2 escolheu PATH exatamente para não amarrar a um venv.

**Consequências:** instalar com o venv desativado falha, mesmo que fosse funcionar depois.
Falso negativo de instalação — preferível ao falso sucesso.

### D9 — `--staged` devolve o mesmo `ScanResult` do M0

**Decisão:** `scan --staged` produz `ScanResult(findings, skipped)`, com `Finding` idêntico
ao do M0.

**Rationale:** `cli.render` já consome esse tipo e já mascara o segredo; um tipo paralelo
duplicaria a lógica de renderização e de mascaramento, e o `finding.py` foi feito
justamente para que nenhum caminho de saída futuro esquecesse de mascarar. DRY sobre
conhecimento, não sobre linhas.

**Alternativas consideradas:** (a) `StagedScanResult` próprio — duplica render e
mascaramento, e é o cenário que o M0 previu ao pôr o mascaramento no `Finding`;
(b) devolver lista de `Finding` sem `skipped` — quebra a assinatura que `render` consome.

**Consequências:** `Finding.path` no modo staged é o caminho relativo à raiz do
repositório, não absoluto — diferença que a saída precisa tratar sem confundir o usuário.

## Drawbacks & Risks

| Drawback / Risco | Severidade | Mitigação | Dono |
|---|---|---|---|
| Parsear diff unificado é código não trivial e errar o mapeamento de linha gera número errado no relatório | Alta | T1.2 tem teste com hunk múltiplo, arquivo novo, arquivo renomeado e linha adicionada no fim; o número de linha é asserido contra o esperado, não só a presença do finding | dev |
| Segredo preexistente em arquivo tocado **não** é reportado pelo hook (consequência do D1) | Média | Comportamento declarado no README e coberto por teste que documenta a decisão; `scan` completo e `--history` (M5) cobrem o caso | dev |
| `git` ausente do PATH quebra o `--staged` | Média | `git.py` levanta erro tipado com mensagem específica; teste negativo cobre | dev |
| Hook fica órfão se o usuário apagar o venv | Média | D2 escolheu PATH em vez de caminho absoluto; D8 valida na instalação. Resíduo aceito: apagar o venv depois quebra o hook | dev |
| Repositório com `core.hooksPath` customizado recebe hook no lugar errado | Média | `install` resolve o diretório de hooks via `git rev-parse --git-path hooks` em vez de assumir `.git/hooks` | dev |
| Testes que criam repositório git são lentos e podem ficar flaky em CI | Média | Ficam em `tests/functional/`; cada um cria repo isolado em `tmp_path`, sem estado compartilhado (`rules/testing.md § 3`) | dev |
| `git commit` em teste exige `user.email`/`user.name` configurados, que o runner de CI pode não ter | Alta | O helper de teste configura ambos **no repositório local**, nunca no global do runner | dev |

## Unresolved Questions

- Q1 — **Como o hook se comporta em Windows?** O blueprint marcou Q7 como confiança
  reduzida: não achou tratamento explícito de Windows nos arquivos em escopo. **Resolução
  adotada:** o M1 implementa e testa em POSIX; o `docs/PRD.md § NFR-6` promete Windows,
  então o README ganha nota de que o hook não foi exercido lá. Elevar para suporte
  verificado exige runner Windows no CI — trabalho de outro milestone.
- Q2 — **O `install` deve suportar `core.hooksPath` global?** O ggshield oferece modos
  `local`/`global`/`system` (`install.py:96,134`). **Resolução adotada:** o M1 faz apenas
  o modo local, e resolve o diretório com `git rev-parse --git-path hooks` para respeitar
  um `core.hooksPath` já configurado. Modo global é knob sem caso de uso pedido — YAGNI.
- Q3 — **Qual o orçamento de latência do hook?** `docs/PRD.md § NFR-2` fixa `< 1 s` para
  um commit típico. O M0 mediu 0,0145 ms por arquivo, então a varredura é irrelevante e o
  custo é o startup do processo. **Resolução adotada:** T3.2 mede o caminho completo do
  hook (invocação incluída) e o teste assert `< 1.0` s para um commit de 20 arquivos.

## Dependency Graph

```
T1.1 (git.py — runner + detecção de repo)
  └─> T1.2 (staged.py — diff parser + linhas adicionadas)
        └─> T2.1 (scan --staged na CLI)
              └─> T2.2 (install — escreve hook, recusa, marcador, PATH)
                    ├─> T3.1 (teste e2e: commit real bloqueado)
                    └─> T3.2 (benchmark do caminho do hook)
```

## Dependencies

| Dependência | Escopo | Versão | Rule 9 |
|---|---|---|---|
| *(nenhuma)* | runtime | — | **O M1 não adiciona dependência de runtime.** `subprocess`, `pathlib`, `os`, `re` da stdlib cobrem tudo — confirmado pelo Q6 do blueprint, que classificou os imports do `install.py` do ggshield e achou só `click` como terceiro (substituído por `argparse`, ADR D5 do M0). |
| `pytest` | dev | `>=9.0.3,<10` | Já declarado no M0. Piso mantido — abaixo de 9.0.3 há `GHSA-6w46-j5rx-g56g`. |
| `ruff` | dev | `>=0.6,<1` | Já declarado no M0. |
| **`git`** | binário externo | qualquer | Não é dependência de pacote: é o programa que estamos integrando. `docs/PRD.md § NFR-6` já declara que `git` é necessário para `--staged` e `--history`. Ausência é erro tipado, não crash. |

Nenhuma dependência nova → nenhuma superfície de CVE nova introduzida pelo M1.

---

## Phase 1: Fronteira com o git

### T1.1 — `git.py`: runner de subprocess e detecção de repositório

#### Objective

Toda conversa com o `git` passa por um módulo, e falhas viram erro tipado.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `git.py` com o runner e os erros de domínio.
**Raciocínio:** o M1 acrescenta a primeira fronteira de infraestrutura do projeto (ADR
D7). Centralizar antes de escrever qualquer consumidor evita que `staged.py` e `hook.py`
inventem cada um seu tratamento de erro — unificar depois seria refactor.

#### Evidence

- ADR D7 deste plano — por que módulo sem abstração
- `rules/architecture.md § 1` — infraestrutura isolada
- `rules/error-handling.md § 2` — erro tipado com contexto

#### Files to edit

- `src/gitsafety/git.py` (NOVO)
- `src/gitsafety/errors.py` (editar — `NotAGitRepositoryError`, `GitUnavailableError`)

#### Deep file dependency analysis

`git.py` importa `subprocess`, `pathlib` e `errors`. Consumido por T1.2 e T2.2. `errors.py`
ganha duas subclasses; a invariante testada no M0 (toda subclasse carrega `exit_code`)
passa a cobri-las automaticamente pelo `parametrize`.

#### Deep Dives

Três modos de falha distintos, que o código óbvio confunde num só:

1. **`git` não está no PATH** → `FileNotFoundError` do `subprocess` → `GitUnavailableError`.
2. **Estamos fora de um repositório** → `git` roda mas sai não-zero →
   `NotAGitRepositoryError`.
3. **O comando falhou por outro motivo** → deve propagar com stderr no contexto, não virar
   "não é repositório".

Confundir (1) com (2) produz "não é um repositório git" numa máquina sem git — mensagem
que manda o usuário procurar o problema errado.

O runner usa `check=False` e inspeciona o `returncode`, em vez de `check=True` +
`CalledProcessError`: queremos traduzir para erro de domínio, não repassar exceção de
biblioteca ao chamador.

#### Pseudo-code / Signatures

```python
def run_git(args: Sequence[str], *, cwd: Path) -> str: ...
def is_git_repository(path: Path) -> bool: ...
def repo_root(path: Path) -> Path: ...
def hooks_dir(path: Path) -> Path: ...   # git rev-parse --git-path hooks
```

#### Tasks

1. `GitUnavailableError` e `NotAGitRepositoryError` em `errors.py`, ambas `UsageError`.
2. `run_git()` com `check=False`, traduzindo `FileNotFoundError` e `returncode != 0`.
3. `is_git_repository()`, `repo_root()`, `hooks_dir()` via `git rev-parse`.

#### TDD

```python
# tests/unit/test_git.py
def test_repo_root_returns_the_repository_root(tmp_git_repo):
    assert repo_root(tmp_git_repo) == tmp_git_repo

def test_is_git_repository_is_false_outside_a_repo(tmp_path):
    assert is_git_repository(tmp_path) is False

def test_run_git_outside_a_repo_raises_not_a_git_repository(tmp_path):
    # caso negativo: erro específico, não genérico
    with pytest.raises(NotAGitRepositoryError) as exc:
        run_git(["rev-parse", "--git-dir"], cwd=tmp_path)
    assert str(tmp_path) in str(exc.value)

def test_missing_git_binary_raises_git_unavailable(monkeypatch, tmp_path):
    # caso negativo: NÃO pode virar 'não é repositório'
    monkeypatch.setenv("PATH", "")
    with pytest.raises(GitUnavailableError):
        run_git(["--version"], cwd=tmp_path)

def test_hooks_dir_respects_core_hookspath(tmp_git_repo):
    # edge case: config customizada
    run_git(["config", "core.hooksPath", "meus-hooks"], cwd=tmp_git_repo)
    assert hooks_dir(tmp_git_repo).name == "meus-hooks"

def test_every_git_error_carries_usage_exit_code():
    for cls in (GitUnavailableError, NotAGitRepositoryError):
        assert cls("x").exit_code == ExitCode.USAGE_ERROR
```

#### Acceptance Criteria

- [ ] `repo_root()` returns a raiz correta dentro de um repositório
- [ ] `is_git_repository()` returns `False` fora de repositório, sem levantar
- [ ] Fora de repositório, `run_git` raises `NotAGitRepositoryError` contains o caminho
- [ ] Sem `git` no PATH, raises `GitUnavailableError` — **nunca** `NotAGitRepositoryError`
- [ ] `hooks_dir()` respeita `core.hooksPath` — testado com `git config core.hooksPath meus-hooks`
- [ ] Toda exceção nova assert `exit_code == ExitCode.USAGE_ERROR`

#### DoD

- [ ] Todos os testes de T1.1 passam
- [ ] `subprocess` aparece **apenas** em `git.py` — verificado por `grep -rn subprocess src/`
- [ ] Commit atômico referenciando T1.1

---

### T1.2 — `staged.py`: ler o stage e extrair as linhas adicionadas

#### Objective

Obter, do índice, apenas as linhas que estão sendo introduzidas, com o número de linha
correto no arquivo novo.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `staged.py` com a invocação do D1 e o parser de diff unificado.
**Raciocínio:** é o núcleo do Risco nº 1 do `ROADMAP.md § M1` e a decisão que o blueprint
corrigiu. Vem antes da CLI porque a CLI só consome seu resultado.

#### Evidence

- `knowledge-base/references/gitleaks/sources/git.go:139-142` — `git diff -U0 --no-ext-diff --staged .`
- `knowledge-base/references/talisman/gitrepo/gitrepo.go:47` — `--src-prefix=a/ --dst-prefix=b/`
- ADR D1 deste plano

#### Files to edit

- `src/gitsafety/staged.py` (NOVO)

#### Deep file dependency analysis

Importa `git.py` (T1.1), `rules.py` e `finding.py` (M0, sem mudança). Consumido por T2.1.
Reusa `Finding` conforme ADR D9 — nenhum tipo novo.

#### Deep Dives

O cabeçalho de hunk `@@ -a,b +c,d @@` dá `c` = primeira linha do lado **novo**. Com `-U0`,
todas as linhas do hunk são adicionadas ou removidas; o contador avança **apenas** em
linhas `+` e de contexto, nunca em `-`. Errar isso desloca o número de linha em arquivos
com remoções.

Armadilhas cobertas por teste:

- `+++ b/arquivo` é cabeçalho, não linha adicionada — filtrar antes de contar.
- Arquivo novo aparece como `--- /dev/null`; o nome vem do lado `+++`.
- Renomeação produz cabeçalho sem hunk quando o conteúdo não muda — não deve gerar finding.
- Arquivo binário produz `Binary files ... differ`, sem linhas `+` — deve ser ignorado sem
  erro.
- Múltiplos hunks no mesmo arquivo: cada um reinicia o contador com seu próprio `c`.

`--src-prefix=a/ --dst-prefix=b/` (talisman) é obrigatório: com `diff.noprefix=true` na
config do usuário, o cabeçalho vira `--- arquivo` e o parser que assume `b/` quebra.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class AddedLine:
    path: Path
    line: int      # 1-based, no arquivo novo
    text: str

def staged_diff(cwd: Path) -> str: ...          # invoca o comando do D1
def parse_added_lines(diff: str) -> list[AddedLine]: ...
def scan_staged(cwd: Path, rules=BUILTIN_RULES) -> ScanResult: ...
```

#### Tasks

1. `staged_diff()` com as quatro flags do D1.
2. `AddedLine` e `parse_added_lines()`.
3. `scan_staged()` aplicando as regras sobre `AddedLine.text` e devolvendo `ScanResult`.

#### TDD

```python
# tests/unit/test_staged.py
def test_parse_extracts_added_line_with_correct_number():
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +3 @@\n+AKIAIOSFODNN7EXAMPLE\n"
    assert parse_added_lines(diff)[0].line == 3

def test_removed_lines_are_not_reported():
    # caso negativo: apagar um segredo não pode acusar
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -3 +0,0 @@\n-AKIAIOSFODNN7EXAMPLE\n"
    assert parse_added_lines(diff) == []

def test_plus_plus_plus_header_is_not_an_added_line():
    # edge case clássico: '+++ b/arquivo' começa com '+'
    assert all(not l.text.startswith("++") for l in parse_added_lines(DIFF_NOVO))

def test_multiple_hunks_each_restart_the_line_counter(): ...
def test_new_file_takes_its_name_from_the_plus_side(): ...
def test_binary_file_marker_produces_no_findings_and_no_error(): ...

def test_scan_staged_finds_secret_added_to_the_index(tmp_git_repo):
    write_and_stage(tmp_git_repo, "cfg.py", 'K = "AKIAIOSFODNN7EXAMPLE"\n')
    assert scan_staged(tmp_git_repo).has_findings

def test_scan_staged_ignores_secret_that_is_on_disk_but_not_staged(tmp_git_repo):
    # O RISCO Nº 1 EM FORMA DE TESTE
    write_and_stage(tmp_git_repo, "a.py", "x = 1\n")
    (tmp_git_repo / "a.py").write_text('K = "AKIAIOSFODNN7EXAMPLE"\n')  # só no disco
    assert scan_staged(tmp_git_repo).has_findings is False

def test_scan_staged_ignores_preexisting_secret_in_a_touched_file(tmp_git_repo):
    # consequência declarada do D1, documentada por teste
    ...
```

#### Acceptance Criteria

- [ ] `parse_added_lines` assert `line == 3` para hunk `@@ -0,0 +3 @@`
- [ ] Linha removida returns lista vazia — apagar segredo não acusa
- [ ] Cabeçalho `+++ b/arquivo` não vira `AddedLine`
- [ ] Múltiplos hunks reiniciam o contador com o `c` de cada um
- [ ] Arquivo binário returns sem finding e **sem exceção**
- [ ] `scan_staged` acha segredo que foi para o índice
- [ ] `scan_staged` **não** acha segredo que está só no disco (Risco nº 1)
- [ ] `scan_staged` **não** acha segredo preexistente em arquivo tocado (D1)

#### DoD

- [ ] Todos os testes de T1.2 passam, incluindo os dois que documentam o D1
- [ ] `scan_staged` returns `ScanResult`, o mesmo tipo do M0 (D9)
- [ ] Commit atômico referenciando T1.2

---

## Phase 2: Superfície de comando

### T2.1 — `scan --staged` na CLI

#### Objective

`gitsafety scan --staged` varre o índice e devolve os mesmos exit codes do M0.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** acrescentar a flag `--staged` ao parser e rotear para `scan_staged`.
**Raciocínio:** é o wiring que torna T1.1 e T1.2 alcançáveis pelo usuário — sem ele são
código morto, o que `cycle-implement § Wiring triad` proíbe. Precede o `install` porque o
hook invoca justamente este comando.

#### Evidence

- ADR D9 — mesmo `ScanResult`, mesma renderização
- `docs/PRD.md § FR-4` — `scan --staged`
- Teste do M0 `test_help_does_not_advertise_flags_that_do_not_exist_yet` — precisa mudar

#### Files to edit

- `src/gitsafety/cli.py` (editar)
- `tests/functional/test_cli.py` (editar — `--staged` deixa de ser flag inexistente)
- `README.md` (editar — `--staged` migra de ⏳ para ✅)

#### Deep file dependency analysis

`cli.py` passa a importar `staged.py`. O teste do M0 que assert que `--staged` **não**
aparece no `--help` precisa ser atualizado — é mudança intencional de contrato, e o teste
existe justamente para forçar essa atualização a ser consciente.

#### Deep Dives

`--staged` e um caminho posicional são mutuamente exclusivos: `scan --staged /tmp` é
pedido incoerente, porque o índice é do repositório atual. `argparse` resolve com
`add_mutually_exclusive_group`, o que produz mensagem melhor que validação manual.

Fora de repositório git, `--staged` deve falhar com `NotAGitRepositoryError` (exit 2), não
devolver vazio com exit 0 — é o mesmo princípio do `PathNotFoundError` do M0.

#### Pseudo-code / Signatures

```python
scan.add_argument("--staged", action="store_true", help="...")
# em main(): if args.staged: result = scan_staged(Path.cwd())
```

#### Tasks

1. Flag `--staged` no subparser, mutuamente exclusiva com o posicional.
2. Roteamento em `main()`.
3. Atualizar o teste do M0 e o README.

#### TDD

```python
# tests/functional/test_cli.py
def test_staged_scan_exits_one_when_index_has_a_secret(tmp_git_repo, monkeypatch): ...
def test_staged_scan_exits_zero_when_index_is_clean(tmp_git_repo, monkeypatch): ...

def test_staged_outside_a_git_repo_is_a_usage_error(tmp_path, monkeypatch):
    # caso negativo
    monkeypatch.chdir(tmp_path)
    assert main(["scan", "--staged"]) == ExitCode.USAGE_ERROR

def test_staged_and_positional_path_are_mutually_exclusive(tmp_git_repo):
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--staged", str(tmp_git_repo)])
    assert exc.value.code == ExitCode.USAGE_ERROR

def test_help_now_advertises_staged_but_still_not_history(capsys):
    # o contrato mudou de propósito; --history segue sendo M5
    ...
```

#### Acceptance Criteria

- [ ] `main(["scan", "--staged"])` returns `1` com segredo no índice
- [ ] returns `0` com índice limpo
- [ ] Fora de repositório git returns `2` com mensagem específica
- [ ] `scan --staged <caminho>` returns exit `2` — mutuamente exclusivos
- [ ] `--help` contains `--staged` e **não** contains `--history`
- [ ] Saída do modo staged mascara o segredo, igual ao M0

#### DoD

- [ ] Todos os testes de T2.1 passam
- [ ] README com `--staged` marcado como disponível
- [ ] Commit atômico referenciando T2.1

---

### T2.2 — `gitsafety install`

#### Objective

Um comando instala o hook, recusa-se a destruir hook alheio e é idempotente.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `hook.py` e o subcomando `install`.
**Raciocínio:** é o entregável que dá nome ao milestone. Vem por último na cadeia funcional
porque o hook que ele escreve invoca `scan --staged`, construído em T2.1.

#### Evidence

- `knowledge-base/references/ggshield/ggshield/cmd/install.py:344,350,351` — shebang, corpo, `0o700`
- `knowledge-base/references/ggshield/ggshield/cmd/install.py:328-335` — recusa e mensagem
- `knowledge-base/references/ggshield/ggshield/cmd/install.py:37-39` — marcador
- ADRs D2, D3, D4, D8

#### Files to edit

- `src/gitsafety/hook.py` (NOVO)
- `src/gitsafety/cli.py` (editar — subcomando `install`)
- `src/gitsafety/errors.py` (editar — `HookExistsError`, `CommandNotOnPathError`)
- `README.md` (editar — `install` migra para ✅)

#### Deep file dependency analysis

`hook.py` importa `git.py` (para `hooks_dir`) e `errors.py`. `cli.py` ganha o subcomando.
É o único módulo que escreve no sistema de arquivos do usuário.

#### Deep Dives

A ordem das verificações importa e é a do `install.py:328-335`:

1. O caminho é um **diretório**? → erro próprio. Escrever por cima falharia com `IsADirectoryError`.
2. O arquivo existe e **contém o nosso marcador**? → já instalado, sai com sucesso (D4).
3. O arquivo existe e **não** é nosso? → recusa, imprime a linha a colar (D3).
4. Caso contrário → escreve.

Inverter (2) e (3) faz `install` repetido acusar conflito com o próprio hook.

`hooks_dir()` vem de `git rev-parse --git-path hooks`, não de `.git/hooks` literal:
respeita `core.hooksPath` e worktrees, e é o mitigante do risco correspondente.

O `chmod` é `0o700`, não `0o755` (`install.py:351`): o hook executa código e deve ser
executável pelo menor conjunto de usuários possível.

#### Pseudo-code / Signatures

```python
HOOK_MARKER = "gitsafety scan --staged"
HOOK_BODY = '#!/bin/sh\ngitsafety scan --staged "$@"\n'

def hook_path_for(cwd: Path) -> Path: ...
def is_our_hook(path: Path) -> bool: ...
def install_hook(cwd: Path) -> Path: ...
```

#### Tasks

1. `HookExistsError` e `CommandNotOnPathError` em `errors.py`.
2. `hook_path_for()` via `hooks_dir()`.
3. `is_our_hook()` procurando o marcador.
4. `install_hook()` com a ordem de verificação acima + `mkdir(parents=True, exist_ok=True)` + `chmod 0o700`.
5. Validação de PATH (D8).
6. Subcomando `install` na CLI.

#### TDD

```python
# tests/unit/test_hook.py — estados degenerados primeiro (D6)
def test_install_refuses_when_a_foreign_hook_exists(tmp_git_repo):
    hook_path_for(tmp_git_repo).write_text("#!/bin/sh\necho outra-ferramenta\n")
    with pytest.raises(HookExistsError) as exc:
        install_hook(tmp_git_repo)
    assert "gitsafety scan --staged" in str(exc.value)   # imprime a linha a colar

def test_install_is_idempotent_when_the_hook_is_ours(tmp_git_repo):
    install_hook(tmp_git_repo)
    install_hook(tmp_git_repo)   # não levanta

def test_install_refuses_when_hook_path_is_a_directory(tmp_git_repo): ...
def test_install_outside_a_git_repo_raises(tmp_path): ...
def test_install_creates_hooks_dir_when_missing(tmp_git_repo): ...

def test_installed_hook_is_executable_by_owner_only(tmp_git_repo):
    p = install_hook(tmp_git_repo)
    assert oct(p.stat().st_mode)[-3:] == "700"

def test_installed_hook_starts_with_sh_shebang(tmp_git_repo):
    assert install_hook(tmp_git_repo).read_text().startswith("#!/bin/sh")

def test_installed_hook_forwards_arguments(tmp_git_repo):
    assert '"$@"' in install_hook(tmp_git_repo).read_text()

def test_install_respects_core_hookspath(tmp_git_repo): ...
def test_install_fails_when_gitsafety_is_not_on_path(tmp_git_repo, monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(CommandNotOnPathError):
        install_hook(tmp_git_repo)
```

#### Acceptance Criteria

- [ ] Hook alheio → raises `HookExistsError`, e a mensagem contains `gitsafety scan --staged`
- [ ] `install` duas vezes não levanta — idempotente pelo marcador
- [ ] Caminho do hook é diretório → erro próprio, distinto do anterior
- [ ] Fora de repositório git → raises, exit `2`
- [ ] `.git/hooks/` inexistente é criado
- [ ] Permissão do hook assert `oct(mode)[-3:] == "700"`
- [ ] Conteúdo starts with `#!/bin/sh` e contains `"$@"`
- [ ] `core.hooksPath` customizado é respeitado
- [ ] `gitsafety` fora do PATH → raises `CommandNotOnPathError` (D8)

#### DoD

- [ ] Todos os testes de T2.2 passam — mais testes de erro que de sucesso (D6)
- [ ] Wiring triad: `cli.main` chama `install_hook`; teste funcional cobre o subcomando; o caminho do hook impresso na saída é o sinal observável
- [ ] Commit atômico referenciando T2.2

---

## Phase 3: Prova ponta a ponta e medição

### T3.1 — Teste de integração: commit real bloqueado

#### Objective

Provar, contra um `git commit` de verdade, que o segredo é bloqueado e que
`--no-verify` passa.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `tests/functional/test_hook_e2e.py`.
**Raciocínio:** é o DoD nº 4 do `ROADMAP.md § M1` e a única prova que vale — todos os
testes anteriores exercem partes; este exerce o produto como o usuário o usa. O ADR D5
decidiu contra mock justamente porque o comportamento sob teste é a interação com o git.

#### Evidence

- `knowledge-base/references/talisman/cmd/acceptance_test.go:64-99` — forma do teste
- ADR D5
- `ROADMAP.md § M1` DoD nº 4

#### Files to edit

- `tests/functional/test_hook_e2e.py` (NOVO)
- `tests/conftest.py` (NOVO — fixture `tmp_git_repo`)

#### Deep file dependency analysis

A fixture `tmp_git_repo` é compartilhada por T1.1, T1.2, T2.1, T2.2 e T3.1. Nasce em
`tests/conftest.py` para não duplicar.

#### Deep Dives

`git commit` exige `user.email` e `user.name`. A fixture os configura **no repositório
local** (`git -C repo config user.email ...`), nunca no global — configurar global do
runner de CI é efeito colateral que vaza entre testes e pode quebrar a máquina do
desenvolvedor.

Para o hook ser encontrado, o `gitsafety` do venv precisa estar no `PATH` do subprocesso
que roda `git commit`. A fixture injeta o diretório de scripts (via `sysconfig`, como no
M0) no `PATH` do ambiente do subprocesso — nunca no do processo de teste.

`git commit` sem mudanças em stage sai não-zero por outro motivo; a fixture garante que
sempre há algo em stage antes de commitar, senão o teste passaria pelo motivo errado.

#### Pseudo-code / Signatures

```python
@pytest.fixture
def tmp_git_repo(tmp_path) -> Path: ...       # init + config local
def git_commit(repo: Path, msg: str, *, no_verify: bool = False) -> int: ...
```

#### Tasks

1. Fixture `tmp_git_repo` em `tests/conftest.py`.
2. Helper `git_commit()` devolvendo o exit code.
3. Os cinco testes abaixo.

#### TDD

```python
# tests/functional/test_hook_e2e.py
def test_commit_with_a_new_secret_is_blocked(tmp_git_repo):
    install_hook(tmp_git_repo)
    stage(tmp_git_repo, "config.py", 'K = "AKIAIOSFODNN7EXAMPLE"\n')
    assert git_commit(tmp_git_repo, "add config") == 1

def test_clean_commit_succeeds_with_the_hook_installed(tmp_git_repo):
    install_hook(tmp_git_repo)
    stage(tmp_git_repo, "app.py", "print('ok')\n")
    assert git_commit(tmp_git_repo, "add app") == 0

def test_no_verify_bypasses_the_hook(tmp_git_repo):
    # o bypass é do git e não deve ser combatido
    install_hook(tmp_git_repo)
    stage(tmp_git_repo, "config.py", 'K = "AKIAIOSFODNN7EXAMPLE"\n')
    assert git_commit(tmp_git_repo, "bypass", no_verify=True) == 0

def test_secret_only_on_disk_does_not_block_the_commit(tmp_git_repo):
    # O RISCO Nº 1, ponta a ponta
    install_hook(tmp_git_repo)
    stage(tmp_git_repo, "a.py", "x = 1\n")
    (tmp_git_repo / "a.py").write_text('K = "AKIAIOSFODNN7EXAMPLE"\n')
    assert git_commit(tmp_git_repo, "safe") == 0

def test_blocked_commit_prints_the_masked_secret(tmp_git_repo, ...):
    # a saída do hook chega ao usuário e não vaza
    ...
```

#### Acceptance Criteria

- [ ] `git_commit` com segredo novo returns `1`
- [ ] `git_commit` limpo returns `0` com o hook instalado
- [ ] `git commit --no-verify` returns `0` mesmo com segredo
- [ ] Segredo só no disco **não** bloqueia — Risco nº 1 provado ponta a ponta
- [ ] A saída do commit bloqueado contains o segredo **mascarado**, não o íntegro

#### DoD

- [ ] Os cinco testes passam contra `git` real
- [ ] A fixture configura `user.email`/`user.name` **local**, nunca global
- [ ] Commit atômico referenciando T3.1

---

### T3.2 — Benchmark do caminho do hook

#### Objective

Medir a latência do hook como o git a experimenta, e provar o `NFR-2`.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `benchmarks/bench_hook.py` e um teste de orçamento.
**Raciocínio:** o M0 mediu a varredura (0,0145 ms/arquivo) e concluiu que o custo dominante
do M1 seria o **startup do processo**. Essa é hipótese, não medição. O `docs/PRD.md § NFR-2`
promete `< 1 s` no commit; sem medir o caminho completo, a promessa é afirmação sem lastro.

#### Evidence

- `knowledge-base/implementations/m0-esqueleto-cli-implementation.md` — 0,0145 ms/arquivo
- `docs/PRD.md § NFR-2` — `< 1 s` num commit típico
- Unresolved Question Q3 deste plano

#### Files to edit

- `benchmarks/bench_hook.py` (NOVO)
- `tests/functional/test_hook_performance.py` (NOVO)

#### Deep file dependency analysis

Consome `install_hook` e a fixture de repositório. Não é importado por produção.

#### Deep Dives

O que se mede é o **`git commit` inteiro** com o hook instalado, menos o `git commit`
inteiro sem o hook — a diferença é o custo que o gitsafety impõe. Medir só `scan --staged`
mediria a varredura de novo, que o M0 já sabe ser irrelevante.

A hipótese do M0 é falsificável aqui: se o custo total ficar na casa de dezenas de ms com
20 arquivos, o startup domina e a hipótese se confirma; se escalar com o número de
arquivos, a varredura importa mais do que o M0 concluiu.

#### Pseudo-code / Signatures

```python
def measure_commit(repo: Path, *, with_hook: bool, n_files: int) -> float: ...
```

#### Tasks

1. Gerador de commit com N arquivos.
2. Medição pareada: com e sem hook.
3. Teste de orçamento.

#### TDD

```python
# tests/functional/test_hook_performance.py
def test_hook_overhead_on_a_typical_commit_is_under_one_second(tmp_git_repo):
    overhead = measure_overhead(tmp_git_repo, n_files=20)
    assert overhead < 1.0, f"NFR-2 violado: {overhead}s"

def test_benchmark_reports_both_measurements(tmp_git_repo):
    m = measure_commit_pair(tmp_git_repo, n_files=20)
    assert set(m) == {"with_hook_s", "without_hook_s", "overhead_s"}
```

#### Acceptance Criteria

- [ ] O benchmark outputs `with_hook_s`, `without_hook_s` e `overhead_s`
- [ ] `assert overhead < 1.0` para commit de 20 arquivos (NFR-2)
- [ ] Os números medidos ficam registrados em `knowledge-base/implementations/m1-hook-pre-commit-implementation.md`
- [ ] O relatório declara se a hipótese do M0 (startup domina) se confirmou

#### DoD

- [ ] Os dois testes passam
- [ ] Números reais registrados, com hardware e método
- [ ] Commit atômico referenciando T3.2

---

## Coverage Matrix

| # | Requisito (origem) | Task(s) | Como é resolvido |
|---|---|---|---|
| 1 | `install` escreve `.git/hooks/pre-commit` executável chamando `scan --staged` (ROADMAP M1 DoD 1) | T2.2 | `install_hook`; testes de shebang, conteúdo e permissão `700` |
| 2 | Hook preexistente → recusa, exit 2, imprime a linha (ROADMAP M1 DoD 2, PRD FR-2) | T2.2 | `HookExistsError` com a linha na mensagem |
| 3 | `scan --staged` lê o conteúdo em stage, não o disco (ROADMAP M1 DoD 3) | T1.2, T2.1 | `git diff --staged`; teste do segredo só no disco |
| 4 | Teste de integração: commit bloqueado, `--no-verify` passa (ROADMAP M1 DoD 4) | T3.1 | 5 testes contra `git` real |
| 5 | Fora de repositório git → mensagem específica, exit 2 (ROADMAP M1 DoD 5, PRD NFR-5) | T1.1, T2.1, T2.2 | `NotAGitRepositoryError` tipado |
| 6 | Distinguir `git` ausente de "não é repositório" | T1.1 | Dois erros distintos, dois testes negativos |
| 7 | `core.hooksPath` respeitado | T1.1, T2.2 | `git rev-parse --git-path hooks` |
| 8 | Instalação idempotente | T2.2 | Marcador (D4) |
| 9 | `gitsafety` no PATH validado na instalação (D8) | T2.2 | `CommandNotOnPathError` |
| 10 | Segredo mascarado também no modo staged (PRD NFR-4) | T2.1, T3.1 | `Finding` reusado (D9); asserção na saída do commit |
| 11 | Sem dependência de runtime nova (PRD NFR-1) | T1.1 | `subprocess` da stdlib; `dependencies = []` inalterado |
| 12 | Latência do commit `< 1 s` (PRD NFR-2) | T3.2 | Medição pareada + teste de orçamento |
| 13 | Linha reportada correta no diff | T1.2 | Parser com teste de hunk múltiplo e de fim de arquivo |
| 14 | Remover segredo não gera finding | T1.2 | Teste de linha `-` |
| 15 | `--help` não anuncia `--history` (ainda M5) | T2.1 | Teste atualizado, não removido |

**Cobertura: 15/15 requisitos mapeados (100%)**

## Global Definition of Done

- [ ] Os 5 itens de DoD do `ROADMAP.md § M1` verificados por teste automatizado
- [ ] Toda regra de negócio com teste unitário (`rules/testing.md § 3`)
- [ ] Casos negativos cobertos onde aplicável (`§ 4.1`)
- [ ] Nenhum `except Exception` genérico (`rules/error-handling.md § 5`)
- [ ] `subprocess` aparece apenas em `git.py` (fronteira de infra, ADR D7)
- [ ] Wiring triad em T2.1 e T2.2
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] `/code-quality` com veredito ∈ {PASS, PASS_WITH_CAVEATS, FAIL_SOFT com ADR}
- [ ] Benchmark executado, com números e hardware registrados
- [ ] README com `install` e `--staged` marcados como disponíveis

## Failure scenarios

O M1 acrescenta uma fronteira externa real — o **binário `git`**. Modos de falha:

| Recurso | Modo de falha | Como o teste reproduz | Comportamento esperado |
|---|---|---|---|
| `git` (processo) | Binário ausente do PATH | `monkeypatch.setenv("PATH", "")` | `GitUnavailableError`, exit 2, mensagem distinta de "não é repositório" |
| `git` (processo) | Diretório não é repositório | `tmp_path` sem `git init` | `NotAGitRepositoryError` com o caminho na mensagem; exit 2 |
| `git` (processo) | `core.hooksPath` aponta para outro lugar | `git config core.hooksPath meus-hooks` | Hook escrito no diretório configurado, não em `.git/hooks` |
| `git` (processo) | Config `diff.noprefix=true` do usuário | `git config diff.noprefix true` | `--src-prefix`/`--dst-prefix` explícitos mantêm o parsing correto |
| Sistema de arquivos | `.git/hooks/` não existe | Remover o diretório antes de instalar | Criado com `mkdir(parents=True, exist_ok=True)` |
| Sistema de arquivos | Caminho do hook é um diretório | `mkdir` no lugar do arquivo | Erro próprio, distinto de "já existe um hook" |
| Sistema de arquivos | Hook de terceiro já instalado | Escrever script alheio antes | Recusa; **jamais** sobrescreve |
| PATH | `gitsafety` não resolvível | `monkeypatch.setenv("PATH", "")` | `CommandNotOnPathError` na instalação, não no commit |

## Concurrency tests

**(none — single-threaded)** — o M1 invoca `git` sequencialmente e escreve um arquivo. Não
há thread, async, lock nem estado compartilhado mutável. O `git` mantém seu próprio lock
de índice (`index.lock`); não competimos com ele porque só lemos.

---

## Final Phase: Integration Validation (MANDATORY)

### Execution

```bash
.venv/bin/pytest -q                                    # suíte inteira
cd $(mktemp -d) && git init -q demo && cd demo
git config user.email t@e.st && git config user.name Teste
gitsafety install                                       # espera: caminho impresso, exit 0
printf 'K = "AKIAIOSFODNN7EXAMPLE"\n' > cfg.py && git add cfg.py
git commit -m "com segredo";        echo "exit=$?"      # espera: exit≠0, bloqueado
git commit -m "bypass" --no-verify; echo "exit=$?"      # espera: exit=0
gitsafety install;                  echo "exit=$?"      # espera: exit=0, idempotente
.venv/bin/python benchmarks/bench_hook.py               # números registrados
```

### Acceptance Criteria

- [ ] Suíte inteira verde
- [ ] `gitsafety install` imprime o caminho do hook e returns `0`
- [ ] Commit com segredo é **bloqueado**, com o segredo mascarado na saída
- [ ] `--no-verify` passa
- [ ] `install` repetido returns `0` sem erro
- [ ] Benchmark produz `with_hook_s`, `without_hook_s` e `overhead_s`

### If Validation Fails

Voltar ao task correspondente pelo Coverage Matrix. Não seguir para `/code-quality` com
qualquer item falhando — `cycle-implement § Stop conditions` proíbe emitir a promessa de
conclusão em estado parcial.
