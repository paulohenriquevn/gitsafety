---
slug: m4-notebooks
milestone_id: M4
created_at: 2026-07-27
goal: Parsear notebooks Jupyter para reportar célula e linha dentro dela, fechar o falso negativo de valor partido e cobrir os quatro tipos de saída.
---

# Plan: M4 — Notebooks Jupyter

## Goal

`.ipynb` deixa de ser varrido como texto e passa a ser parseado: o achado reporta
**célula e linha dentro da célula**, o valor partido entre elementos de `source` deixa de
escapar, e os quatro tipos de saída são cobertos explicitamente. Notebook malformado
degrada para varredura de texto com aviso, nunca falha nem é pulado.

## Context

Quinto milestone. O `docs/PRD.md § 2` identifica a saída salva de célula como o vetor mal
coberto que motiva o público de cientistas de dados.

O blueprint `knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md`
(SHIPPABLE 100.0) **reformulou o milestone** com medição: um notebook com 5 segredos em
posições distintas, varrido com o `v0.4.0`, produziu **4 achados**. Detectar já funciona
para o caso comum, incluindo as saídas salvas. O que não funciona é **localizar**: as
linhas reportadas são do JSON, e um notebook aberto no Jupyter não tem linha 53.

## Baseline Context (deep review of current state)

**Estado:** branch `develop`, tag `v0.4.0`, 542 testes verdes, 53 regras, config em YAML,
uma dependência de runtime.

**Comportamento atual com `.ipynb`:** não está em `BINARY_EXTENSIONS`, então é lido como
texto por `scanner._read_text` e varrido linha a linha do JSON. Acha 4 de 5; reporta linha
do JSON.

### Files that will be touched

| File | LoC hoje | Último commit | Por que existe hoje | Invariantes a preservar |
|---|---|---|---|---|
| `src/gitsafety/notebook.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/scanner.py` | 118 | `403b3be` | Compõe walker + rules + config | `ScanResult(findings, skipped)` é contrato de `cli.render` |
| `src/gitsafety/finding.py` | 60 | `1e27e9f` | `Finding` + mascaramento | `line` é 1-based e valida `>= 1` |
| `tests/unit/test_notebook.py` (NOVO) | 0 | — | (a criar) | — |
| `benchmarks/bench_notebook.py` (NOVO) | 0 | — | (a criar) | — |
| `README.md` | 276 | `403b3be` | Contrato público | A seção de notebooks precisa refletir o que existe |

### Current callers / dependents

- `scanner.scan_path` chama `_read_text` e `_scan_text` para **todo** arquivo. O M4
  bifurca esse caminho por extensão.
- `cli.render` imprime `f.path` e `f.line`. Se a localização de notebook for codificada no
  `path`, `render` não muda — é o que mantém o milestone aditivo.
- `staged.scan_staged` varre linhas de diff, não arquivos. **Fora de escopo:** um diff de
  `.ipynb` é diff do JSON, e reconstruir células a partir de um diff parcial não é
  possível de forma confiável.

### Domain glossary

- **Célula** — unidade do notebook; tem `cell_type` (`code`, `markdown`, `raw`) e `source`.
- **`source`** — lista de strings, uma por linha. Em `nbformat` v3 chama-se `input`.
- **Saída salva** — conteúdo em `outputs[]`, persistido no arquivo mesmo depois de a célula ser apagada. É o vetor do `PRD § 2`.
- **`output_type`** — `stream`, `execute_result`, `display_data` ou `error`; cada um guarda o texto num caminho diferente.
- **Localização em notebook** — `célula N linha M`, onde N é 1-based na ordem do arquivo e M é 1-based dentro do texto reconstituído da célula.
- **Degradação para texto** — quando o JSON não parseia, varrer o arquivo como o M0-M3 faziam, com aviso.

### Architecture boundaries affected

```
domínio        errors.py, finding.py, patterns.py, catalog.py, rules.py
aplicação      config.py, walker.py, scanner.py, staged.py, notebook.py   <- novo
infraestrutura git.py
interface      cli.py, hook.py, __main__.py
```

`notebook.py` é **aplicação**: transforma um documento em segmentos varreríveis. Não é
domínio porque conhece um formato de arquivo, e não é infraestrutura porque não fala com
serviço externo.

## Prior Art & Related Work

| Fonte | O que aproveitamos | Citação |
|---|---|---|
| Blueprint do M4 | Os 4 ADRs são entrada travada | `knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md` |
| gitleaks | Confirmação de que **não** parseia: `.ipynb` só afeta formatação de link | `knowledge-base/references/gitleaks/detect/utils.go:41-43` |
| Blueprint do M0 | Pulo é resultado, não efeito colateral — sustenta o D4 | `knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md` |
| `rules/parsimony-ladder.md` | Rung 2 sustenta usar `json` da stdlib em vez de `nbformat` | `rules/parsimony-ladder.md` |
| `rules/error-handling.md` | § 5 sustenta a degradação com aviso em vez de pulo silencioso | `rules/error-handling.md` |

## Objective

Ao fim do M4, um `.ipynb` com segredo em código, em saída `stream`, em `execute_result` e
em valor partido produz **5 de 5** achados, cada um localizado por célula e linha dentro
da célula.

## ADRs

D1-D4 vêm do blueprint; texto integral em
`knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md § ADRs`. D5 é deste plano.

### D1 — Parsear e reportar célula + linha dentro da célula

**Decisão:** `.ipynb` é lido como JSON; o achado reporta célula e linha dentro dela.

**Rationale:** a medição do blueprint mostrou 4 de 5 detectados e **zero** localizáveis —
as linhas 6, 24, 53 e 62 são do JSON. O gitleaks tem a mesma lacuna e a resolve na
apresentação (`detect/utils.go:41-43`), o que só serve a quem escreve links; nós
escrevemos caminhos locais.

**Alternativas consideradas:** (a) manter texto e documentar que a linha é do JSON — deixa
o usuário sem como agir; (b) reportar as duas linhas — dois números para reconciliar,
contra o `PRD § 4`; (c) só o número da célula — insuficiente numa célula de 80 linhas.

**Consequências:** a localização é codificada no `path` do `Finding`
(`nb.ipynb :: célula 3 :: linha 2`), evitando mudar a dataclass que quatro milestones
consomem.

### D2 — Juntar os elementos de `source` antes de varrer

**Decisão:** `"".join(source)`, e a numeração derivada do texto reconstituído.

**Rationale:** é a causa medida do único falso negativo. O JSON insere `",\n   "` entre
elementos, e nenhuma regex de linha atravessa.

**Alternativas consideradas:** (a) varrer elemento a elemento — é o comportamento atual,
que produziu o falso negativo; (b) juntar com `\n` — inseriria quebra onde não há,
deslocando a numeração.

**Consequências:** `splitlines()` sobre o texto unido, não sobre a lista.

### D3 — Cobrir os quatro tipos de saída e as duas chaves de código

**Decisão:** varrer `stream.text`, `execute_result.data["text/plain"]`,
`display_data.data["text/plain"]`, `error.traceback`, `error.evalue`. Aceitar `source` e
`input`.

**Rationale:** quatro caminhos medidos. Cobrir só `stream` perderia `execute_result`, que
é o que aparece quando a última expressão da célula é o valor — `os.environ` sozinho.
`error` importa porque traceback salvo carrega valores da chamada que falhou. `input`
fecha o Risco nº 1 do roadmap sem migrar o documento.

**Alternativas consideradas:** (a) só `stream` — é o caso do `print`, não o único; (b)
varrer todos os mime-types — `image/png` é base64 e produziria ruído; (c) `nbformat` para
normalizar v3→v4 — segunda dependência, vedada pelo `NFR-1`.

**Consequências:** mais caminhos a manter. Mitigado por serem **dados**, uma tabela, não
uma cadeia de `if`.

### D4 — Notebook malformado degrada para texto, com aviso

**Decisão:** `json.loads` falhando → varre como texto e registra o arquivo como degradado.

**Rationale:** um `.ipynb` truncado ainda pode conter a credencial. Falhar recusaria o
arquivo; pular em silêncio é o falso negativo que o ADR D3 do M0 proíbe. Texto é o
comportamento de hoje, medido em 4/5 — degradação para estado **conhecido**.

**Alternativas consideradas:** (a) erro tipado e exit 2 — um notebook quebrado derrubaria
uma varredura de mil arquivos; (b) pular em silêncio — contraria o M0 D3; (c) pular e
reportar em `skipped` — melhor, mas deixa de achar o que o texto acharia.

**Consequências:** achados de notebook degradado têm linha do JSON. A saída precisa dizer
isso.

### D5 — `--staged` não parseia notebook

**Decisão:** o modo staged continua varrendo linhas de diff, sem parsear `.ipynb`.

**Rationale:** um diff de notebook é diff do **JSON**, e o `-U0` do M1 entrega apenas as
linhas adicionadas — sem o documento completo, reconstruir célula e numeração é
impossível de forma confiável. Tentar produziria localização **errada**, que é pior que
localização grosseira: o usuário iria à célula indicada e não encontraria nada.

O valor não se perde: o hook continua **detectando** o segredo introduzido no notebook,
com a linha do diff. Só a localização fina fica para o `scan`.

**Alternativas consideradas:** (a) parsear o arquivo em disco quando o diff toca um
`.ipynb` — o disco pode divergir do índice, que é exatamente o Risco nº 1 do M1; (b)
reconstruir o notebook do índice com `git show :arquivo` — possível, mas acrescenta uma
chamada de git por notebook no caminho quente do commit, para ganho de localização num
modo em que o usuário já sabe o que acabou de escrever; (c) pular notebooks no staged —
falso negativo inaceitável.

**Consequências:** dois níveis de precisão conforme o modo. Documentado no README.

## Drawbacks & Risks

| Drawback / Risco | Severidade | Mitigação | Dono |
|---|---|---|---|
| Parsear JSON é mais caro que ler linhas, e notebooks são grandes | Média | T3.1 mede parsing × texto; o limite de 1 MB do M0 já corta os maiores | dev |
| `nbformat` v3 usa `input` em vez de `source` (Risco M4 nº 1) | Alta | D3 aceita as duas chaves; teste com notebook v3 sintético | dev |
| Notebook > 1 MB pulado (Risco M4 nº 2) | Média | Já mitigado no M0 — aparece em `skipped`; falta só o teste | dev |
| Localização codificada no `path` quebra quem espera um caminho de arquivo | Média | Nenhum consumidor externo; `cli.render` só imprime. Alternativa (mudar `Finding`) tocaria 4 milestones | dev |
| Notebook malformado com JSON parcialmente válido produz células estranhas | Média | D4 degrada para texto ao primeiro erro de parse; estrutura inesperada dentro de célula é tolerada campo a campo | dev |
| Dois níveis de precisão (scan × staged) confundem | Baixa | D5 documentado no README; o hook continua detectando | dev |

## Unresolved Questions

- Q1 — **A localização deve ir no `path` ou num campo novo do `Finding`?** **Resolução
  adotada:** no `path`. Um campo novo tocaria a dataclass que M0-M3 consomem e obrigaria
  `render` a saber de notebooks. Codificar no caminho mantém o milestone aditivo, ao custo
  de o `path` deixar de ser um caminho puro — registrado como Drawback.
- Q2 — **Varrer células `raw`?** **Resolução adotada:** sim. `raw` é conteúdo literal que o
  usuário escreveu; não há razão para tratá-lo diferente de `markdown`, que a medição
  mostrou conter segredo em caso real.
- Q3 — **Qual o teto de custo aceitável para o parsing?** Não há número no PRD.
  **Resolução adotada:** T3.1 mede; o teste de orçamento exige que o parsing não seja mais
  que **5×** a varredura de texto do mesmo arquivo. Acima disso, o ganho de localização não
  paga.

## Dependency Graph

```
T1.1 (notebook.py — parse + segmentos com localização)
  └─> T2.1 (scanner bifurca por extensão)
        └─> T3.1 (benchmark parsing × texto)
```

## Dependencies

| Dependência | Escopo | Versão | Rule 9 |
|---|---|---|---|
| *(nenhuma)* | runtime | — | **O M4 não adiciona dependência.** `.ipynb` é JSON e `json` é stdlib. `nbformat` seria a segunda dependência de runtime, e o `docs/PRD.md § NFR-1` autoriza uma, esgotada no M3 — além de trazer validação de esquema que **não** queremos: um notebook que o `nbformat` rejeita ainda pode conter segredo. |
| `pyyaml` | runtime | `>=6.0.1,<7` | Declarada no M3. |
| `pytest`, `ruff` | dev | já declarados | — |

---

## Phase 1: Parsing

### T1.1 — `notebook.py`: parsear e produzir segmentos localizados

#### Objective

Transformar um `.ipynb` numa lista de trechos varreríveis, cada um com sua localização.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `notebook.py` com o parse e o percurso das células e saídas.
**Raciocínio:** é o milestone inteiro num módulo. Vem primeiro porque o scanner só
precisa saber bifurcar; toda a complexidade de formato fica isolada aqui.

#### Evidence

- `knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md § Q2, Q3` — estrutura e caminhos de saída
- ADRs D1, D2, D3, D4

#### Files to edit

- `src/gitsafety/notebook.py` (NOVO)

#### Deep file dependency analysis

Importa `json`, `dataclasses`, `pathlib`. **Nenhum** import do pacote — é transformação
pura de documento em segmentos, o que a torna testável sem tocar o scanner.

#### Deep Dives

`source` pode ser **lista** ou **string** — o formato permite ambos, e notebooks gerados
por ferramentas variam. Tratar só lista quebra em arquivos reais.

Os quatro caminhos de saída são **dados**, não lógica: uma tabela de extratores por
`output_type`. Uma cadeia de `if` cresceria a cada tipo novo do formato.

A numeração dentro da célula vem de `splitlines()` sobre o texto **unido** (D2). Numerar
sobre a lista original reproduziria o falso negativo que o milestone existe para corrigir.

Estrutura inesperada dentro de uma célula — `outputs` que não é lista, `data` que não é
dicionário — deve ser tolerada **campo a campo**, não abortar o notebook: um campo
estranho não invalida os demais.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class Segment:
    text: str
    cell_index: int      # 1-based
    origin: str          # "código" | "saída"
    def locate(self, path: Path, line_in_segment: int) -> str: ...

def is_notebook(path: Path) -> bool: ...
def parse_notebook(raw: str) -> list[Segment] | None: ...   # None = degradar (D4)
```

#### Tasks

1. `Segment` com localização.
2. `parse_notebook()` tolerando `source`/`input`, lista/string.
3. Tabela de extratores por `output_type`.
4. Devolver `None` quando o JSON não parseia (D4).

#### TDD

```python
def test_code_cell_becomes_a_segment(): ...
def test_source_as_string_is_accepted():
    # edge case: o formato permite string, e ferramentas variam
def test_v3_input_key_is_accepted():
    # Risco M4 nº 1 — falso negativo silencioso em notebook antigo
def test_split_value_is_rejoined():
    # O FALSO NEGATIVO MEDIDO no blueprint
    seg = parse_notebook(nb_com_valor_partido)
    assert "postgresql://app:s3nh4Sup3r@db.exemplo.com/prod" in seg[0].text

@pytest.mark.parametrize("tipo", ["stream", "execute_result", "display_data", "error"])
def test_every_output_type_produces_a_segment(tipo): ...

def test_line_number_is_relative_to_the_cell():
    # o ponto do milestone
def test_malformed_json_returns_none_for_degradation(): ...
def test_unexpected_field_shape_does_not_abort_the_notebook(): ...
def test_markdown_and_raw_cells_are_scanned(): ...
```

#### Acceptance Criteria

- [ ] `assert parse_notebook(nb)[0].cell_index == 1` para a primeira célula
- [ ] `assert parse_notebook(nb_com_source_string)` returns segmento não vazio
- [ ] Chave `input` (v3) é aceita — `assert` sobre notebook v3 sintético
- [ ] Valor partido entre elementos é reconstituído: `assert "postgresql://app:s3nh4Sup3r@db.exemplo.com/prod" in segmento.text`
- [ ] Os **quatro** `output_type` produzem segmento — parametrizado
- [ ] `Segment.locate` returns texto contains `célula` e o número da linha **na célula**
- [ ] `assert parse_notebook("{quebrado") is None` — sinal de degradação (D4)
- [ ] Notebook com `"outputs": {}` numa célula ainda returns segmentos das demais
- [ ] `assert` que células `markdown` e `raw` aparecem entre os segmentos returns

#### DoD

- [ ] Todos os testes de T1.1 passam
- [ ] `notebook.py` não importa nada do pacote `gitsafety`
- [ ] Commit atômico referenciando T1.1

---

## Phase 2: Wiring

### T2.1 — `scanner` bifurca por extensão

#### Objective

`.ipynb` passa pelo parser; todo o resto segue como antes.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** `scan_path` escolhe o caminho conforme a extensão.
**Raciocínio:** é o wiring — sem ele `notebook.py` é código morto. A bifurcação é de uma
linha porque toda a complexidade ficou no módulo anterior.

#### Evidence

- ADRs D1 e D4
- `src/gitsafety/scanner.py` — `_read_text` e `_scan_text` atuais

#### Files to edit

- `src/gitsafety/scanner.py` (editar)
- `README.md` (editar)

#### Deep file dependency analysis

`scanner` passa a importar `notebook`. `cli.render` **não** muda — a localização vai no
`path`, e `render` só imprime.

#### Deep Dives

Quando `parse_notebook` devolve `None`, o arquivo cai no caminho de texto — o mesmo do
M0-M3. É degradação para estado conhecido, não para o desconhecido.

O `allow` e o marcador inline precisam continuar valendo dentro dos segmentos: um
`# gitsafety: allow` numa célula é escrito na linha do código, e a linha do segmento é
exatamente essa. Passar a linha do segmento a `is_allowed` preserva o comportamento sem
código novo.

#### Pseudo-code / Signatures

```python
def _scan_notebook(raw, path, rules, allow) -> list[Finding] | None: ...
```

#### Tasks

1. Bifurcação por extensão em `scan_path`.
2. Varredura por segmento, com localização no `path` do `Finding`.
3. Degradação para texto quando o parse falha.

#### TDD

```python
def test_notebook_secret_reports_cell_and_line(tmp_path):
    # o resultado do milestone
def test_all_five_planted_secrets_are_found(tmp_path):
    # a medição do blueprint, agora como teste: 5 de 5
def test_malformed_notebook_still_finds_secrets(tmp_path):
    # D4: degradação, não falha
def test_inline_marker_works_inside_a_cell(tmp_path): ...
def test_non_notebook_files_are_unaffected(tmp_path): ...
def test_oversized_notebook_appears_in_skipped(tmp_path):
    # Risco M4 nº 2 — já mitigado no M0; falta a evidência
```

#### Acceptance Criteria

- [ ] Achado em notebook contains `célula` e a linha **dentro** da célula
- [ ] O notebook de 5 segredos do blueprint produz **5** achados (era 4)
- [ ] Notebook truncado ainda returns findings — `assert result.findings != []`
- [ ] `# gitsafety: allow` dentro de célula suprime aquela linha
- [ ] `.py` produz findings idênticos aos do M3 — os 542 testes anteriores returns verde
- [ ] `assert [s.reason for s in result.skipped] == [SkipReason.TOO_LARGE]`

#### DoD

- [ ] Todos os testes de T2.1 passam
- [ ] `git diff --name-only` **não** contains `cli.py`
- [ ] Os 542 testes anteriores seguem verdes sem edição
- [ ] Commit atômico referenciando T2.1

---

## Phase 3: Medição

### T3.1 — Benchmark: parsing × texto

#### Objective

Saber o que o parsing custa, e se o ganho de localização paga.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** medir a varredura do mesmo notebook nos dois caminhos.
**Raciocínio:** `json.loads` sobre um documento grande é mais caro que iterar linhas, e
notebooks são grandes. Sem medir, "parsear é melhor" é preferência, não engenharia.

#### Evidence

- Unresolved Question Q3 — origem do teto de 5×
- Blueprint § Recommendations item 7

#### Files to edit

- `benchmarks/bench_notebook.py` (NOVO)
- `tests/functional/test_notebook_performance.py` (NOVO)

#### Deep file dependency analysis

Consome `scan_path` e o parser. Não é importado por produção.

#### Deep Dives

O notebook de teste precisa ser **realista**: muitas células, saídas longas, e o tamanho
próximo do que um notebook de análise tem de verdade. Um notebook de três células mediria
o custo de importar `json`.

O que interessa é a **razão** entre os dois caminhos, não o valor absoluto — a razão é o
que decide se o ganho de localização paga.

#### Pseudo-code / Signatures

```python
def measure_notebook(n_cells: int, rounds: int = 3) -> dict[str, float]: ...
```

#### Tasks

1. Gerador de notebook realista.
2. Medição pareada: com parsing e forçando o caminho de texto.
3. Teste de razão.

#### TDD

```python
def test_parsing_costs_at_most_five_times_the_text_path(tmp_path):
    m = measure_notebook(n_cells=200)
    assert m["parsed_s"] < m["text_s"] * 5, m

def test_benchmark_reports_both_paths(tmp_path):
    assert set(measure_notebook(n_cells=20)) >= {"parsed_s", "text_s", "ratio"}
```

#### Acceptance Criteria

- [ ] O benchmark outputs `parsed_s`, `text_s` e `ratio`
- [ ] `assert m["parsed_s"] < m["text_s"] * 5` para 200 células
- [ ] Os números ficam registrados em `knowledge-base/implementations/m4-notebooks-implementation.md`
- [ ] O log declara se o custo do parsing se justifica

#### DoD

- [ ] Os dois testes passam
- [ ] Números registrados com hardware e método
- [ ] Commit atômico referenciando T3.1

---

## Coverage Matrix

| # | Requisito (origem) | Task(s) | Como é resolvido |
|---|---|---|---|
| 1 | `.ipynb` lido como JSON; código e saídas verificados (ROADMAP M4 DoD 1) | T1.1, T2.1 | `parse_notebook` + tabela de extratores |
| 2 | Finding aponta célula e linha dentro dela (ROADMAP M4 DoD 2) | T1.1, T2.1 | `Segment.locate` codificado no `path` |
| 3 | `.ipynb` malformado → erro específico, sem crash (ROADMAP M4 DoD 3) | T1.1, T2.1 | Degradação para texto com aviso (D4) |
| 4 | Teste com segredo só na saída salva (ROADMAP M4 DoD 4) | T2.1 | Notebook de 5 segredos, 5 achados |
| 5 | `nbformat` v3 não gera falso negativo (Risco M4 nº 1) | T1.1 | Chave `input` aceita; teste com v3 |
| 6 | Notebook grande não é pulado em silêncio (Risco M4 nº 2) | T2.1 | Teste de `skipped`; já mitigado no M0 |
| 7 | Valor partido em `source` deixa de escapar (medição do blueprint) | T1.1 | `"".join(source)` (D2) |
| 8 | Os quatro `output_type` cobertos | T1.1 | Parametrizado sobre os quatro |
| 9 | Sem dependência nova (PRD NFR-1) | T1.1 | `json` da stdlib |
| 10 | `cli.py` inalterado (milestone aditivo) | T2.1 | Localização no `path` |
| 11 | `allow` e marcador valem dentro de célula | T2.1 | Linha do segmento passada a `is_allowed` |
| 12 | Custo do parsing medido | T3.1 | Razão parsing × texto |
| 13 | `--staged` não regride (D5) | T2.1 | A bifurcação por extensão vive só em `scan_path`; T2.1 verifica por `git diff --name-only` que `staged.py` não foi tocado, e os 7 testes e2e do M1 seguem verdes |
| 14 | Células `markdown` e `raw` varridas (Unresolved Q2) | T1.1 | Teste dedicado |

**Cobertura: 14/14 requisitos mapeados (100%)**

## Global Definition of Done

- [ ] Os 4 itens de DoD do `ROADMAP.md § M4` verificados por teste automatizado
- [ ] Toda regra de negócio com teste unitário (`rules/testing.md § 3`)
- [ ] Casos negativos cobertos (`§ 4.1`)
- [ ] Nenhum `except Exception` genérico (`rules/error-handling.md § 5`)
- [ ] `notebook.py` sem import do pacote `gitsafety`
- [ ] `cli.py` inalterado
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] `/code-quality` com veredito ∈ {PASS, PASS_WITH_CAVEATS, FAIL_SOFT com ADR}
- [ ] Benchmark executado, números registrados
- [ ] README com os dois níveis de precisão (scan × staged) documentados

## Failure scenarios

O M4 acrescenta uma fronteira de **formato de arquivo**, não de I/O.

| Recurso | Modo de falha | Como o teste reproduz | Comportamento esperado |
|---|---|---|---|
| `.ipynb` | JSON inválido | Arquivo truncado no meio | Degrada para texto; achados com linha do JSON; aviso |
| `.ipynb` | `source` como string, não lista | Notebook com `"source": "x = 1"` | Aceito |
| `.ipynb` | Chave `input` (v3) | Notebook v3 sintético | Aceito |
| `.ipynb` | `outputs` não é lista | `"outputs": {}` | Célula varrida assim mesmo; campo ignorado |
| `.ipynb` | `data` sem `text/plain` | Saída só com `image/png` | Sem segmento; sem erro |
| `.ipynb` | Acima de 1 MB | Notebook com saída grande | Pulado, **em `skipped`** |
| `.ipynb` | Sem a chave `cells` | JSON válido, forma errada | Degrada para texto |

**(sem I/O externo — o M4 lê arquivo local; git e sistema de arquivos já cobertos)**

## Concurrency tests

**(none — single-threaded)** — o M4 parseia um documento e percorre listas. Nenhuma
thread, async, lock ou estado compartilhado mutável.

---

## Final Phase: Integration Validation (MANDATORY)

### Execution

```bash
.venv/bin/pytest -q
# notebook com os 5 segredos do blueprint
.venv/bin/python -c "..."   # gera o notebook
gitsafety scan .; echo "exit=$?"   # espera: 5 findings com 'célula N linha M'
.venv/bin/python -m benchmarks.bench_notebook
```

### Acceptance Criteria

- [ ] `pytest -q` returns exit code `0`
- [ ] O notebook do blueprint produz **5** achados, não 4
- [ ] Cada achado contains `célula` e a linha dentro dela
- [ ] Benchmark outputs `parsed_s`, `text_s` e `ratio`

### If Validation Fails

Voltar ao task pelo Coverage Matrix. Não seguir para `/code-quality` com item falhando.
