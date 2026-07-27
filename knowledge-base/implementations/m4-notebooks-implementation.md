---
slug: m4-notebooks
milestone_id: M4
date: 2026-07-27
status: IMPLEMENTATION_COMPLETE
plan: knowledge-base/plans/m4-notebooks-plan.md
blueprint: knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md
---

# M4 — Notebooks Jupyter

## O que mudou, e por quê

O blueprint reenquadrou o milestone antes de uma linha ser escrita. A hipótese de partida
era "notebooks vazam e nós não detectamos". A medição desmentiu metade: um notebook com 5
segredos plantados, varrido pela v0.4.0, produzia **4 achados**. Varrer o JSON como texto já
encontra o que está nas saídas salvas — que é justamente o vetor que o `docs/PRD.md § 2`
nomeia.

O que não funcionava era **localizar**. As linhas reportadas eram do JSON — 17, 31, 50 — e um
notebook aberto no Jupyter não tem linha 50. O gitleaks tem a mesma lacuna e a resolve na
apresentação (`detect/utils.go:41-43`, acrescentando `?plain=1` ao link), o que serve a quem
escreve links para o GitHub; nós escrevemos caminhos locais.

O 5º segredo — o falso negativo — era um valor partido entre elementos de `source`. O Jupyter
quebra uma linha longa em vários elementos do array, e o JSON insere `",\n   "` no meio.
Nenhuma regex de linha atravessa isso; juntar antes de varrer, sim.

## Resultado

| | v0.4.0 | v0.5.0 |
|---|---|---|
| Segredos achados (notebook de 5) | 4 | **5** |
| Localização | linha do JSON | célula + linha dentro dela |
| Testes | 542 | **590** |

Exemplo real, do repositório de validação de integração:

```
linhas no JSON:  17, 31, 50
gitsafety scan:  analise.ipynb :: célula 2 (código):2   aws-access-key-id
                 analise.ipynb :: célula 3 (saída):1    github-personal-access-token
                 analise.ipynb :: célula 4 (saída):1    postgres-connection-string
```

## Decisões que carregam o milestone

| Decisão | Alternativa recusada | Por quê |
|---|---|---|
| `json` da stdlib | `nbformat` do PyPI | O `NFR-1` autoriza **uma** dependência de runtime, gasta no M3. E a validação de esquema do `nbformat` é o oposto do que queremos: um notebook que ele rejeita ainda pode conter a credencial |
| `"".join(source)` sem separador | juntar com `\n` | Os elementos já trazem o `\n` quando há quebra; inserir um deslocaria a numeração e manteria o falso negativo do valor partido |
| Chaves `source` **e** `input` | só `source` | `input` é o nome no `nbformat` v3 — Risco M4 nº 1, falso negativo silencioso em notebook antigo |
| Tabela dos 4 `output_type` | só `stream` | `stream` é o do `print`, o mais citado; `execute_result` é o de `os.environ` sozinho numa célula, e `error` guarda o traceback com os valores da chamada que falhou |
| Parse falho → `None` → varre como texto | falhar, ou pular | Pular é o falso negativo silencioso que o ADR D3 do M0 proíbe; falhar recusaria um arquivo que ainda pode ter a chave. Texto é o comportamento dos milestones anteriores — degradação para estado **conhecido** |
| Localização codificada no `path` do `Finding` | campo novo na dataclass | Mantém o milestone aditivo: `cli.py` não muda e os quatro milestones que consomem `Finding` seguem intocados |

## Medição (T3.1)

Mesma máquina, medição pareada sobre o **mesmo** notebook, `indent=1` como o Jupyter grava,
melhor de 3 rodadas. `benchmarks/bench_notebook.py`.

Os dois lados passam por `scan_path`, variando só a extensão (`.ipynb` vs `.txt`) — mesma
travessia, mesma leitura, mesmas 53 regras. `indent=1` como o Jupyter grava, melhor de 3
rodadas. `benchmarks/bench_notebook.py`.

| células | bytes | parseado | texto | razão |
|---|---|---|---|---|
| 20 | 25.663 | 0,0314 s | 0,0227 s | 1,38× |
| 50 | 64.063 | 0,0759 s | 0,0549 s | 1,38× |
| 100 | 128.064 | 0,1599 s | 0,1450 s | 1,10× |
| 200 | 256.164 | 0,3078 s | 0,2276 s | **1,35×** |

**O teto da Unresolved Question Q3 era 5×; o custo real é 1,35×.** Cabe com folga.

**Duas correções de método, ambas no sentido de piorar o número que eu publicaria.** A
primeira medição deu 0,36× porque eu gerava o notebook com `json.dumps` sem indentação —
uma linha única de 240 KB é adversário fraco para o caminho de texto. Com `indent=1`, 0,41×.
E esse 0,41× ainda estava errado: comparava `scan_path` (com travessia e leitura) contra
`_scan_text` (conteúdo já em memória) e eu chamava isso de pareado. Pareado de verdade, e
com o texto sempre varrido (correção do F1), a razão é 1,35×. Um número que não mede o que
diz medir não é evidência, ainda que a conclusão sobreviva.

## O que o review independente pegou — e que eu não tinha pego

O `/review` devolveu **NEEDS_FIXES** com um BLOCKER que era meu, e certo.

Ao fazer o caminho parseado autoritativo (`continue` após varrer os segmentos), eu
reintroduzi no `gitsafety scan` a classe de defeito que este produto existe para eliminar.
Medido, mesmos bytes como `.ipynb` e como `.txt`:

| Vetor | `.ipynb` (v0.5.0-rc) | texto (v0.4.0) |
|---|---|---|
| `display_data` só com `text/html` | **0** | 1 |
| `execute_result` só com `text/html` (repr de DataFrame) | **0** | 1 |
| `application/json` | **0** | 1 |
| `text/markdown` | **0** | 1 |
| `metadata` do notebook (parâmetros papermill) | **0** | 1 |
| `metadata` da célula | **0** | 1 |
| `attachments` de markdown | **0** | 1 |
| `output_type` desconhecido / ausente | **0** | 1 |

Pior: os dois caminhos passaram a **discordar**. No mesmo notebook com `text/html`, o hook
barrava o commit e o `scan` dava all-clear — quem auditasse um repositório existente
receberia silêncio.

**A causa não foi esquecer um formato; foi a forma.** O schema define `data` como um
*mimebundle* — dicionário com qualquer mime-type, e `text/plain` não é obrigatório. Toda
lista de formatos conhecidos é uma lista desatualizada. O plano chegou a considerar "varrer
todos os mime-types" e rejeitou por causa do base64 de `image/png`, mas nunca pesou a perda
de cobertura relativa ao release anterior — e `metadata` e `attachments` não aparecem no
plano, são lacuna, não trade-off.

A correção é estrutural: o texto é **sempre** varrido, e o parsing só enriquece. Assim o
parsing não pode subtrair cobertura por construção, e não por vigilância.

Outros cinco defeitos do mesmo review, todos confirmados por execução:

| # | Defeito | Consequência |
|---|---|---|
| F2 | `traceback` é array de **linhas** no schema, não `multiline_string` | Juntar sem separador grudava `token=AKIA…` em `ValueError:`, e o delimitador de fim do padrão deixava de casar |
| F3 | `RecursionError` fora do `except` | Um `.ipynb` aninhado derrubava a varredura dos **demais** arquivos do diretório |
| F4 | v3 real guarda células em `worksheets[].cells` | A chave `input`, que eu afirmava mitigar o Risco M4 nº 1, era **inalcançável**; e o teste validava um híbrido que não existe |
| F5 | `break` por presença de chave | `source: []` vazio escondia o `input` |
| F7 | Duas saídas na mesma célula com localização idêntica | Usuário não distinguia qual |

**A lição, que já é a terceira vez neste projeto:** o teste escrito por quem escreveu o
código herda o viés do código. `test_output_without_text_plain_produces_no_segment`
*consagrava* o defeito como contrato. O que faltava não era mais um caso, era o **oráculo**
— `achados(.ipynb) ⊇ achados(mesmo conteúdo como texto)` — que afirma a relação entre os
caminhos em vez de enumerar o que lembramos de cobrir. Ele falhava em 10 dos 12 casos.

E vale registrar que **inverti a ordem do TDD** nesta task: escrevi `notebook.py` antes de
`tests/unit/test_notebook.py`. Nos M0–M3 a ordem foi respeitada. Não afirmo causalidade,
mas foi a task com mais defeitos escapados, e o teste escrito depois do código é exatamente
o que o RED-first evita. As correções foram feitas RED-first.

## Caveat honesto — a assimetria entre `scan` e o hook

O `scan` localiza por célula. **O hook não** — ele reporta a linha do diff:

```
gitsafety scan .   →  nb.ipynb :: célula 4 (saída):1
git commit         →  nb.ipynb:12
```

É o ADR D5 operando como decidido: `--staged` varre as linhas adicionadas do
`git diff --staged`, não o arquivo, e mapear a linha do diff de volta para a célula exigiria
ler o arquivo — outro caminho de código, com seu próprio risco de divergir do primeiro. O
hook **bloqueia corretamente** (validado: exit 1, zero commits), que é a função dele; o que
falta é o refinamento da mensagem. Registrado como item de backlog, não como defeito
silencioso.

## Wiring triad

| Task | Caller | Teste de integração | Sinal em runtime |
|---|---|---|---|
| T1.1 `notebook.py` | `scanner._scan_notebook` | `tests/functional/test_notebook_scan.py` | Localização por célula na saída do `scan` |
| T2.1 bifurcação | `scan_path` ← `cli.main` | 7 testes funcionais + hook e2e | Achados e `skipped` no resumo |
| T3.1 benchmark | `tests/functional/test_notebook_performance.py` | teste de razão ≤ 5× | Números no relatório |

## Validação de integração (fora da suíte)

| O que | Resultado |
|---|---|
| Notebook de 5 segredos do blueprint | **5/5** achados (era 4) |
| 10 vetores do F1 (`text/html`, `metadata`, `attachments`, …) | Todos reportados; oráculo de cobertura verde |
| `.ipynb` com 60 mil níveis de aninhamento + `.py` com segredo no mesmo diretório | O `.py` é reportado; a varredura não aborta (F3) |
| Notebook realista com markdown + `execute_result` + `error` | 3/3, cada um na célula certa |
| Notebook truncado | degrada para texto, ainda acha, sem stack trace |
| Notebook > 1 MB | aparece em `skipped` com `TOO_LARGE` (Risco M4 nº 2) |
| Hook com segredo **apenas** na saída salva | commit bloqueado, exit 1, 0 commits no repo |
| Remoção da saída → novo commit | aceito |
| `gitsafety install` sem o binário no PATH | recusa com mensagem clara, exit ≠ 0 |

## DoD do ROADMAP § M4

- [x] `.ipynb` lido como JSON; código **e saídas salvas** verificados — `_OUTPUT_TEXT_PATHS`, 4 tipos
- [x] Finding aponta célula e linha dentro dela — `Segment.locate`
- [x] `.ipynb` malformado → sem stack trace — degrada para texto (D4)
- [x] Teste com segredo **apenas** na saída salva — `test_secret_only_in_saved_output_is_found` + hook e2e

## Gates

| Gate | Verdicto |
|---|---|
| Suíte | 590 passando |
| `ruff check` / `format` | limpo |
| `/code-quality` | `FAIL_SOFT` — 0 HARD; os 6 achados são de `.claude/skills/`, cobertos pelo ADR 0001; `vulture src/ benchmarks/` não acha nada no produto |
| `--staged` não regride (D5) | `git diff --name-only` não contém `staged.py` nem `cli.py`; os 7 testes e2e do M1 seguem verdes |
