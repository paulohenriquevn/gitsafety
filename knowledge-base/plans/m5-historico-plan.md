---
slug: m5-historico
milestone_id: M5
created_at: 2026-07-27
goal: Encontrar segredos já commitados no histórico do git, reportando commit, autor e data.
---

# Plano: `scan --history` (M5) — linha de chegada da V1

## Goal

`gitsafety scan --history` percorre o histórico do repositório e reporta cada segredo que
já foi commitado, com **commit, autor e data**, reusando o mesmo matcher do scan de
arquivos, sem crashar em repositório sem commits.

## Context

O M5 fecha a V1. O hook do M1 impede que o segredo **entre**; o `--history` responde a
pergunta que ele não responde: "e a chave que eu commitei mês passado?".

O blueprint (`knowledge-base/discoveries/blueprints/m5-historico-git-blueprint.md`,
SHIPPABLE 100.0) já decidiu o comando, e a decisão **diverge do gitleaks por medição**: o
comando que ele usa não enxerga segredo introduzido na resolução de conflito de merge.

## Baseline Context (deep review of current state)

### Files that will be touched

| Arquivo | LoC | Papel hoje | O que muda |
|---|---|---|---|
| `src/gitsafety/git.py` | 96 | Único módulo que importa `subprocess`; expõe `run_git(args, *, cwd)` | Nada — `history.py` chama `run_git` |
| `src/gitsafety/staged.py` | 149 | `AddedLine`, `_HUNK_RE`, `_NEW_FILE_RE`, `parse_added_lines(diff)`, `scan_staged` | Nada — `parse_added_lines` é **reusado**, não copiado |
| `src/gitsafety/scanner.py` | 340 | `is_allowed`, `ScanResult`, `scan_path` | Nada |
| `src/gitsafety/finding.py` | 74 | `Finding(rule_id, path, line, secret)`, `mask()` | Nada |
| `src/gitsafety/cli.py` | 138 | `build_parser` com 4 flags, `render`, `main` | +1 flag `--history` no grupo `alvo` (mutuamente exclusivo com `--staged`) |
| `src/gitsafety/errors.py` | 88 | `GitsafetyError` e subclasses com `exit_code` | +1 erro se necessário (ver ADR D4) |
| `src/gitsafety/history.py` | — | **NOVO** | Comando de histórico, parsing de commits, dedup |

git sha da baseline: `dec5ae0` (develop).

### Contracts consumed

```python
# git.py
def run_git(args: Sequence[str], *, cwd: Path) -> str: ...

# staged.py
@dataclass(frozen=True)
class AddedLine:
    path: Path
    line: int   # 1-based no arquivo novo
    text: str

def parse_added_lines(diff: str) -> list[AddedLine]: ...
_HUNK_RE  = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+)$")

# scanner.py
def is_allowed(secret: str, line: str, allow: Sequence[Pattern[str]] = ()) -> bool: ...
```

### Current callers / dependents

`cli.main` → `scan_path` (arquivos) **ou** `scan_staged` (index). O M5 acrescenta um terceiro
alvo, `scan_history`, no mesmo ponto de decisão — sem tocar nos outros dois.

### Domain glossary

| Termo | Significado aqui |
|---|---|
| **Ocorrência** | Um par (segredo, arquivo) encontrado em algum commit |
| **Introdução** | O commit **mais antigo** em que a ocorrência aparece |
| **Diff de primeiro pai** | O diff de um merge contra seu primeiro pai — o que `--diff-merges=first-parent` emite |

### Architecture boundaries affected

`rules/architecture.md § 1`: `history.py` é camada de **aplicação** — compõe `git` (de onde
vem o texto), `staged` (como o diff vira linhas) e `rules` (o que procurar). Não imprime e
não chama `sys.exit`; isso é da interface.

## Prior Art & Related Work

| Fonte | O que trouxe |
|---|---|
| `knowledge-base/discoveries/blueprints/m5-historico-git-blueprint.md` | Comando, lacuna do merge medida, custo, dedup |
| `knowledge-base/references/gitleaks/sources/git.go:93-94` | O comando que **não** copiamos, e por quê |
| `knowledge-base/references/gitleaks/detect/detect.go:714` | Fingerprint `commit:file:rule:line` |
| `knowledge-base/references/talisman/gitrepo/gitrepo.go:238` | Estratégia alternativa (enumerar objetos) |
| `knowledge-base/references/ggshield/tests/repository.py:22-27` | Fixture que imprime stdout+stderr do git antes de relançar |
| `src/gitsafety/staged.py` (M1) | O parser de diff que reusamos |

## Objective

Entregar `--history` com os 4 itens do DoD do `ROADMAP.md § M5` verificados por teste, sem
dependência nova e sem segundo motor de detecção.

## ADRs

### D1 — `--diff-merges=first-parent`, não a flag do gitleaks

**Decisão:** `git log -p -U0 --all --diff-merges=first-parent --no-ext-diff`.

**Rationale:** o blueprint mediu que `--full-history --diff-filter=tuxdb` (o comando do
gitleaks) devolve **0 ocorrências** onde há 1 real, quando o segredo é colado na resolução
de um conflito de merge. `--diff-merges=first-parent` devolve 1, ao custo de 0,113 s contra
0,115 s — sem custo. `--no-ext-diff` pelo mesmo motivo do M1: um `diff.external` configurado
pelo usuário mudaria o formato que parseamos.

**Alternativas consideradas:** (a) copiar o comando do gitleaks — herda uma lacuna **medida**
e uma flag (`--diff-filter=tuxdb`) cuja razão não consegui citar na fonte; (b) `-m` — acha,
mas emite o diff uma vez por pai, dobrando achados de merge e empurrando o problema para a
dedup; (c) `rev-list --objects --all | cat-file --batch` (estratégia do talisman) — também
não tem a lacuna, mas custa 2× e devolve arquivos íntegros, o que muda o significado de
"linha" no achado e revarre conteúdo não modificado a cada commit.

**Consequences:** um segredo que existe em ambos os pais e sobrevive ao merge é reportado
pelo pai, não pelo merge — que é onde ele foi de fato introduzido.

### D2 — Dedup por `(regra, segredo, arquivo)`, reportando a introdução e a contagem

**Decisão:** colapsar ocorrências repetidas; reportar o commit **mais antigo**, com autor e
data, e **quantos commits** contêm a ocorrência.

**Rationale:** o Risco M5 nº 2 do roadmap nomeia o ruído de repetir o mesmo segredo a cada
commit. A ação corretiva que o produto pede é revogar a chave no provedor (`README.md`), e
ela é única por segredo — não por commit. O commit mais antigo é o mais útil dos N: responde
"desde quando está exposta?", que decide a urgência.

**Alternativas consideradas:** (a) fingerprint do gitleaks, que inclui o commit
(`detect.go:714`) e portanto **não** deduplica entre commits — serve auditoria contínua, é
ruído numa varredura pontual; (b) reportar o commit mais recente — responde a pergunta menos
útil; (c) não deduplicar — o ruído que o risco nomeia.

**Consequences:** a saída precisa mostrar a contagem, senão o colapso é silencioso — e a
lição do M4 é que colapso silencioso esconde informação. `1 commit` não é impresso; a
contagem só aparece quando > 1.

### D3 — Reusar `parse_added_lines`, não escrever um segundo parser

**Decisão:** `history.py` fatia a saída por commit e passa cada fatia ao
`staged.parse_added_lines`.

**Rationale:** o DoD exige "sem segundo motor de detecção", e o M4 mediu o custo de dois
caminhos sobre a mesma coisa: cinco defeitos de reconciliação em três rodadas. O formato é o
mesmo diff unificado; a única diferença é o cabeçalho de commit que `git log` intercala.

**Alternativas consideradas:** (a) parser próprio para `log -p` — duplica conhecimento que
diverge na primeira mudança (viola DRY sobre lógica de negócio); (b) chamar `git show` por
commit — N processos em vez de 1, e o blueprint mediu que o processo único é o caminho
rápido.

**Consequences:** se `parse_added_lines` não servir, a decisão é revista **no plano**, não
contornada no código. O teste T1.1 é o que verifica isso.

### D4 — Repositório sem commits resolve-se por flag, não por caso especial

**Decisão:** confiar no `--all`, que faz o git sair com 0 e saída vazia; **nenhum** erro
novo é criado.

**Rationale:** medido no blueprint — `git log -p` sem `--all` sai 128 com
`fatal: does not have any commits yet`; com `--all`, sai 0 e vazio. O DoD nº 4 ("repositório
sem commits → mensagem específica, sem crash") é satisfeito por "nenhum segredo encontrado",
que é a mensagem correta: um repositório sem commits **não tem** segredo no histórico.

**Alternativas consideradas:** (a) detectar o caso e levantar erro tipado — inventa um erro
para uma situação que não é errada; (b) capturar o exit 128 e traduzir — só necessário se
não usássemos `--all`, e usamos.

**Consequences:** `history.py` não trata esse caso explicitamente; o teste T2.1 fixa o
comportamento para que uma mudança futura de flag não o quebre em silêncio.

## Drawbacks & Risks

| Risco | Probabilidade | Mitigação | Dono |
|---|---|---|---|
| Repositório grande tornar o comando inútil na prática | Baixa | Medido: 5.000 commits em 0,115 s. T4.1 mede de novo com o produto real, não só com o git | dev |
| A saída de `git log -p` crescer além da memória em repo enorme | Média | `run_git` hoje devolve `str`. T1.1 mede o pico de memória; se for problema, é caso para streaming — registrado, não antecipado | dev |
| Dedup esconder informação (lição do M4) | Média | A contagem de commits aparece na saída quando > 1; teste T2.1 verifica | dev |
| Segredo em commit reescrito continuar no reflog | Baixa | Fora do escopo do M5; declarado no blueprint e no backlog | — |
| `--diff-merges=first-parent` não existir em git antigo | Baixa | Introduzida no git 2.31 (2021). T2.1 verifica a versão e falha com mensagem clara se ausente | dev |

## Unresolved Questions

- Q1 — **A saída mostra o caminho do arquivo no commit antigo ou o atual?** Um arquivo
  renomeado depois aparece com o nome que tinha. Proposta: o nome no commit da introdução,
  porque é onde o achado está. Resolver em T3.1, ao escrever o `render`.
- Q2 — **Truncar a lista quando houver centenas de achados?** Proposta: não truncar no M5 —
  truncar esconde, e o roadmap manda documentar o custo em vez de mitigá-lo. Revisitar se o
  dogfooding mostrar problema.
- Q3 — **`run_git` devolve `str`; isso escala?** Um repositório muito maior que os 5.000
  commits medidos pode estourar a memória ao materializar a saída inteira. Proposta: medir o
  pico em T4.1 e só considerar streaming se o número justificar — antecipar seria YAGNI.

## Dependency Graph

```
T1.1 (history.py: comando + fatiamento por commit)
  └─> T2.1 (scan_history: matcher + dedup)
        └─> T3.1 (CLI --history + render)
              └─> T4.1 (benchmark)
```

## Dependencies

| Dependência | Versão | Tipo | Rule 9 — por que não reimplementar | CVE |
|---|---|---|---|---|
| `git` (binário) | ≥ 2.31 | runtime, já exigido desde o M1 | Reimplementar leitura de packfiles é reinventar a roda | n/a — fora do gerenciador de pacotes |
| `subprocess` | stdlib | runtime | stdlib | n/a |
| `pyyaml` | >=6.0.1,<7 | runtime, **já declarada no M3** | Não reimplementar parser YAML | Auditada no M3 |

**Nenhuma dependência nova.** `docs/PRD.md § NFR-1` preservado. Os três peers legíveis
convergem em chamar o binário do git (blueprint § Q7).

---

## Phase 1: Travessia

### T1.1 — `history.py`: comando e fatiamento por commit

#### Objective

Produzir, a partir do repositório, uma sequência de `(commit, autor, data, diff)`.

#### Why this step (action + reasoning)

**Ação:** rodar o comando decidido no ADR D1 e fatiar a saída por commit.
**Raciocínio:** `git log -p` intercala cabeçalhos de commit com diffs. Sem fatiar, o
`parse_added_lines` do M1 veria os cabeçalhos como conteúdo, e o achado perderia o commit —
que é justamente o que o DoD pede reportar.

#### Evidence

- Blueprint § Q1 (comando e flags), § Q4 (repo vazio), ADR D1
- `src/gitsafety/staged.py:76` — `parse_added_lines`, o consumidor da fatia

#### Files to edit

- `src/gitsafety/history.py` (NOVO)
- `tests/unit/test_history.py` (NOVO)

#### Deep file dependency analysis

Importa `run_git` de `git.py`. **Não** importa `scanner` — o casamento é da T2.1. Isso
mantém `history.py` testável sem regras.

#### Pseudo-code / Signatures

```python
_FORMATO = "%H%x1f%an%x1f%aI%x1f%s"   # unidade ASCII 0x1f separa; não ocorre em texto de commit

@dataclass(frozen=True)
class CommitInfo:
    sha: str
    author: str
    date: str      # ISO-8601 de %aI
    subject: str

def history_diff(cwd: Path) -> str: ...
def parse_commits(raw: str) -> list[tuple[CommitInfo, str]]: ...
```

#### TDD

```python
def test_commit_header_is_parsed_into_fields():
    assert parse_commits(BRUTO)[0][0].author == "Ana"

def test_diff_of_each_commit_is_isolated():
    # o diff do commit 2 não contém linha do commit 1
    assert "commit1" not in parse_commits(BRUTO)[1][1]

def test_empty_output_yields_no_commits():
    assert parse_commits("") == []

def test_commit_subject_containing_the_separator_does_not_break_parsing():
    # caso negativo: 0x1f no assunto — improvável, mas o parse não pode desalinhar
    ...

def test_commit_without_diff_is_kept_with_empty_diff():
    # commit vazio (--allow-empty) tem cabeçalho e nenhum diff
    ...
```

#### Acceptance Criteria

- [ ] `pytest tests/unit/test_history.py -k parse_commits` passa com os 5 testes acima
- [ ] `parse_commits("")` returns `[]` — verificado por `test_empty_output_yields_no_commits`
- [ ] O diff devolvido por commit **não** contém a linha de cabeçalho de outro commit —
      verificado por `test_diff_of_each_commit_is_isolated`
- [ ] `history_diff` usa exatamente as flags do ADR D1 — verificado por
      `test_history_diff_uses_the_decided_flags` que inspeciona os argumentos passados

#### DoD

- [ ] Todos os testes de T1.1 passam
- [ ] `ruff check` e `ruff format --check` limpos
- [ ] `history.py` não importa `scanner` — verificado por grep no teste
- [ ] Commit atômico referenciando T1.1

---

## Phase 2: Casamento

### T2.1 — `scan_history`: matcher reusado e dedup

#### Objective

Transformar as fatias em achados deduplicados, com o commit da introdução.

#### Why this step (action + reasoning)

**Ação:** passar cada fatia ao `parse_added_lines` e casar com as mesmas regras.
**Raciocínio:** o DoD exige "sem segundo motor". Reusar é a única forma de garantir que um
segredo detectado no hook também é detectado no histórico.

#### Evidence

- ADR D2 (dedup), D3 (reuso), D4 (repo vazio)
- Blueprint § Q3 — fingerprint do gitleaks e por que divergimos
- `ROADMAP.md § M5` DoD 2, 3 e 4

#### Files to edit

- `src/gitsafety/history.py`
- `tests/unit/test_history.py`
- `tests/functional/test_history_e2e.py` (NOVO)

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class HistoryFinding:
    finding: Finding      # reusa o do M0
    commit: CommitInfo    # onde foi introduzido
    commits: int          # em quantos commits a ocorrência aparece

def scan_history(cwd, rules=BUILTIN_RULES, *, config=None) -> list[HistoryFinding]: ...
```

A ordem de `git log` é do mais novo para o mais antigo, então a **última** ocorrência vista
de uma chave é a introdução. `--reverse` daria a ordem direta, mas o blueprint não mediu seu
custo — manter a ordem natural e inverter na estrutura é a escolha barata.

#### TDD

```python
def test_secret_introduced_and_later_removed_is_still_found(tmp_git_repo):
    # DoD nº 3 do ROADMAP — o teste que carrega o milestone
def test_same_secret_in_three_commits_yields_one_finding_with_count_three(tmp_git_repo):
    # ADR D2: colapso visível
def test_reported_commit_is_the_oldest(tmp_git_repo):
def test_repository_without_commits_reports_nothing_and_does_not_raise(tmp_git_repo):
    # DoD nº 4
def test_secret_pasted_in_a_merge_resolution_is_found(tmp_git_repo):
    # a lacuna medida no blueprint — o teste que prova que não copiamos o gitleaks
def test_same_matcher_as_file_scan(tmp_git_repo):
    # DoD nº 2: o mesmo segredo achado por scan_path é achado por scan_history
def test_allow_marker_in_a_historical_line_suppresses(tmp_git_repo):
def test_secret_in_two_different_files_yields_two_findings(tmp_git_repo):
    # caso negativo do dedup: arquivo faz parte da chave
```

#### Acceptance Criteria

- [ ] `test_secret_introduced_and_later_removed_is_still_found` passa — DoD nº 3
- [ ] `test_repository_without_commits_reports_nothing_and_does_not_raise` passa — DoD nº 4
- [ ] `test_secret_pasted_in_a_merge_resolution_is_found` passa — a divergência do gitleaks
- [ ] `assert scan_history(repo)[0].commits == 3` para o mesmo segredo em 3 commits
- [ ] `assert scan_history(repo)[0].commit.sha == sha_do_primeiro` — introdução, não a última
- [ ] O conjunto de segredos de `scan_history` **contém** o de `scan_path` no mesmo estado de
      árvore — verificado por `test_same_matcher_as_file_scan`

#### DoD

- [ ] Todos os testes de T2.1 passam
- [ ] `git diff --name-only` **não** contém `scanner.py` nem `staged.py` — reuso, não edição
- [ ] Os 1513 testes anteriores seguem verdes
- [ ] Commit atômico referenciando T2.1

---

## Phase 3: Interface

### T3.1 — `--history` na CLI e formato de saída

#### Objective

Expor o comando e imprimir commit, autor e data por achado.

#### Why this step (action + reasoning)

**Ação:** acrescentar a flag ao grupo mutuamente exclusivo e estender `render`.
**Raciocínio:** o `docs/PRD.md § NFR-3` limita `scan` a 4 flags; `--history` é a 5ª e precisa
ser justificada — ela é o FR-17, um alvo de varredura, não uma opção de tuning.

#### Evidence

- `ROADMAP.md § M5` DoD 1 — "reporta commit, autor e data"
- `src/gitsafety/cli.py:49-55` — o grupo `alvo` já existente
- Unresolved Question 1 — nome do arquivo no commit antigo

#### Files to edit

- `src/gitsafety/cli.py`
- `tests/functional/test_cli.py`
- `README.md`, `CHANGELOG.md`

#### TDD

```python
def test_history_flag_is_mutually_exclusive_with_staged(capsys):
    # caso negativo: --staged --history juntos → exit 2 com mensagem
def test_history_output_contains_commit_author_and_date(tmp_git_repo):
def test_history_output_shows_commit_count_only_when_greater_than_one(tmp_git_repo):
def test_history_exit_code_is_1_when_a_secret_is_found(tmp_git_repo):
def test_history_exit_code_is_0_on_clean_history(tmp_git_repo):
```

#### Acceptance Criteria

- [ ] `gitsafety scan --history --staged` sai com **exit 2** e mensagem do argparse
- [ ] A saída contém sha abreviado, autor e data ISO — verificado por
      `test_history_output_contains_commit_author_and_date`
- [ ] `2 commits` aparece quando a ocorrência está em 2; **não** aparece quando está em 1
- [ ] Exit 1 com achado, 0 sem — mesmos códigos do `scan` (contrato do M0)
- [ ] O segredo é mascarado por padrão; `--show-secrets` revela — herdado do M0, verificado

#### DoD

- [ ] Todos os testes de T3.1 passam
- [ ] `README.md` documenta a flag com exemplo de saída real
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] Commit atômico referenciando T3.1

---

## Phase 4: Medição

### T4.1 — Benchmark do histórico

#### Objective

Medir o custo do produto real, não só o do comando do git.

#### Why this step (action + reasoning)

**Ação:** medir `scan_history` em repositórios de 100, 1.000 e 5.000 commits.
**Raciocínio:** o blueprint mediu o **git** em 0,115 s; falta o custo do nosso parsing e das
53 regras sobre 79.949 linhas. O Risco M5 nº 1 só está respondido com esse número.

#### Files to edit

- `benchmarks/bench_history.py` (NOVO)
- `tests/functional/test_history_performance.py` (NOVO)

#### TDD

```python
def test_history_scan_of_5000_commits_stays_under_the_budget():
    m = measure_history(n_commits=5000)
    assert m["total_s"] < 10.0, m     # orçamento generoso; o número real vai ao log

def test_benchmark_reports_git_and_scan_separately():
    assert set(measure_history(n_commits=100)) >= {"git_s", "scan_s", "total_s", "commits"}
```

#### Acceptance Criteria

- [ ] O benchmark separa `git_s` de `scan_s` — saber qual domina decide onde otimizar
- [ ] `assert m["total_s"] < 10.0` para 5.000 commits
- [ ] Números registrados em `knowledge-base/implementations/m5-historico-implementation.md`
      com hardware e método
- [ ] O log declara se o Risco M5 nº 1 se materializa

#### DoD

- [ ] Os dois testes passam
- [ ] Commit atômico referenciando T4.1

---

## Coverage Matrix

| # | Afirmação do Goal / DoD | Tarefa | Como é verificada |
|---|---|---|---|
| 1 | `--history` percorre o histórico (ROADMAP DoD 1) | T1.1, T3.1 | `history_diff` + flag na CLI |
| 2 | Reporta **commit** (DoD 1) | T1.1, T3.1 | `CommitInfo.sha` no render |
| 3 | Reporta **autor** (DoD 1) | T1.1, T3.1 | `CommitInfo.author` |
| 4 | Reporta **data** (DoD 1) | T1.1, T3.1 | `CommitInfo.date` |
| 5 | Reusa o **mesmo** matcher (DoD 2) | T2.1 | `test_same_matcher_as_file_scan` + grep sem `scanner.py` no diff |
| 6 | Segredo introduzido e removido ainda é detectado (DoD 3) | T2.1 | `test_secret_introduced_and_later_removed_is_still_found` |
| 7 | Repo sem commits → sem crash (DoD 4) | T2.1 | `test_repository_without_commits_reports_nothing_and_does_not_raise` |
| 8 | Dedup por (regra, segredo, arquivo) (Risco nº 2) | T2.1 | `test_same_secret_in_three_commits_yields_one_finding_with_count_three` |
| 9 | Commit reportado é a introdução (ADR D2) | T2.1 | `test_reported_commit_is_the_oldest` |
| 10 | Colapso visível na saída (ADR D2) | T3.1 | `test_history_output_shows_commit_count_only_when_greater_than_one` |
| 11 | Segredo em resolução de merge é achado (ADR D1) | T2.1 | `test_secret_pasted_in_a_merge_resolution_is_found` |
| 12 | Custo medido (Risco nº 1) | T4.1 | `test_history_scan_of_5000_commits_stays_under_the_budget` |
| 13 | Nenhuma dependência nova | T1.1 | `## Dependencies` + `pyproject.toml` inalterado |
| 14 | `--staged` e `scan` não regridem | T2.1, T3.1 | Os 1513 testes anteriores verdes sem edição |
| 15 | Máscara por padrão (contrato do M0) | T3.1 | `test_history_masks_by_default` |

**Cobertura: 15/15 (100%)**

## Failure scenarios

O M5 chama um processo externo (`git`), então os modos de falha dele são nossos.

| Cenário | Comportamento exigido | Verificado por |
|---|---|---|
| `git` ausente do PATH | `CommandNotOnPathError` com mensagem clara, exit 2 | Reusa o do M1; `test_history_without_git_on_path` |
| Não é repositório git | `NotAGitRepositoryError`, exit 2 | `test_history_outside_a_repository` |
| Repositório sem commits | Saída "nenhum segredo", exit 0 | `test_repository_without_commits_reports_nothing_and_does_not_raise` |
| `git` versão < 2.31 (sem `--diff-merges`) | Erro claro nomeando a flag e a versão mínima | `test_history_requires_git_2_31` |
| `git` escreve em stderr mas continua (auto-gc) | Não abortar; o gitleaks trata isso em `sources/git.go:246` | `test_history_tolerates_stderr_noise` |
| Saída do git com bytes inválidos | `errors="replace"`, sem `UnicodeDecodeError` | `test_history_with_invalid_utf8_in_a_commit` |

## Concurrency tests

**(none — single-threaded.)** `history.py` roda um único `subprocess` e itera a saída em
sequência. Não há thread, lock, fila nem estado compartilhado. Se um dia a travessia for
paralelizada, esta seção deixa de valer e o plano correspondente precisa de testes de corrida.

## Global Definition of Done

- [ ] Os 4 itens do DoD do `ROADMAP.md § M5` verificados por teste nomeado
- [ ] Coverage Matrix 15/15
- [ ] `ruff check` e `ruff format --check` limpos
- [ ] `/code-quality` sem `FAIL_HARD`
- [ ] `/review` com veredito `READY_TO_MERGE`
- [ ] Benchmark registrado com hardware e método
- [ ] `CHANGELOG.md` e `README.md` atualizados
- [ ] Nenhuma dependência nova em `pyproject.toml`

## Final Phase: Integration Validation (MANDATORY)

Fora da suíte, num repositório de verdade:

1. Clonar/criar repo, commitar segredo, removê-lo, rodar `gitsafety scan --history` —
   confirmar que aparece com o commit da introdução.
2. Criar conflito de merge e colar credencial na resolução — confirmar que aparece.
3. Rodar num repositório sem commits — confirmar exit 0 e mensagem.
4. Rodar no próprio repositório do gitsafety e conferir o tempo.
5. Confirmar que `gitsafety scan` e `gitsafety scan --staged` seguem idênticos.
