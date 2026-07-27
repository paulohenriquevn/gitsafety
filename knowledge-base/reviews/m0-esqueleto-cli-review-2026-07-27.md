# Review — M0: esqueleto ponta a ponta da CLI

**Data:** 2026-07-27
**Slug:** `m0-esqueleto-cli` · **Milestone:** M0
**Base do diff:** `0ed2131..HEAD` — 8 commits, 39 arquivos
**Domínio detectado:** CLI (`detect_domain.py`: `argparse`, `stdout`, `exit code`, 236 hits)

> **Método declarado.** O `cycle-review` prevê 5-7 agentes especialistas em paralelo. Esta
> revisão foi conduzida com os **verificadores determinísticos** do `/review`
> (`detect_domain.py`), os hard gates do `cycle-review`, e cross-validation manual entre
> plano, código e testes. Os agentes não foram gerados. A consequência honesta: esta
> revisão não tem o benefício de olhos independentes, que é justamente o valor do
> pipeline multi-agente. Ela cobre o verificável mecanicamente; não substitui revisão
> humana antes de um release público.

## Hard gates (`cycle-review` § Hard gates)

| # | Gate | Resultado |
|---|---|---|
| 1 | Testes verdes na branch | ✅ 92/92 (`pytest -q`) |
| 2 | Nenhum segredo commitado | ✅ nenhum `.env`, `credentials*`, `*.pem`, `*.key` rastreado |
| 3 | Não há commit direto em `main` | ✅ branch `develop`; `main` sem commits |
| 4 | Nenhum trailer `Co-Authored-By` | ✅ 0 ocorrências em 8 commits |
| 5 | `CHANGELOG.md` atualizado | ✅ alterado no diff |

**Nenhum BLOCKER.**

## Cross-validation: plano ↔ implementação ↔ teste

Cada linha da Coverage Matrix do plano, verificada contra o código real:

| # | Requisito | Verificação | Status |
|---|---|---|---|
| 1 | `pip install -e .` expõe `gitsafety` | Binário executado de `/tmp` → exit 0 | ✅ |
| 2 | `scan` aplica `AKIA[0-9A-Z]{16}` | 4 acertos + 6 não-acertos testados | ✅ |
| 3 | Imprime `arquivo:linha regra` | Saída real conferida | ✅ |
| 4 | Exit 0/1/2 testados | 3 testes + 3 execuções reais | ✅ |
| 5 | Suíte com um comando, verde em CI | `pytest -q` verde em 3.10 **e** 3.11 | ✅ |
| 6 | Binários pulados | `test_walk_reports_binary_file_as_skipped_*` | ✅ |
| 7 | Arquivos > 1 MB pulados | fronteira inclusiva testada nos dois lados | ✅ |
| 8 | Segredo mascarado por padrão | `SECRET not in capsys.out` | ✅ |
| 9 | `--show-secrets` revela | testado + execução real | ✅ |
| 10 | Falha explícita, sem erro genérico | `PathNotFoundError` tipado; `main` não tem `except Exception` | ✅ |
| 11 | Pulo é resultado, não efeito colateral | `(files, skipped)` → `ScanResult` → linha na saída | ✅ |
| 12 | Sem dependência de runtime | `dependencies = []` | ✅ |
| 13 | Dados de benchmark | 3 execuções registradas com σ | ✅ |
| 14 | Formato de regra compatível com M2 | `Rule` congelada com casos anexos | ✅ |
| 15 | Nenhuma dependência com CVE | `pytest 9.1.1` instalado, acima de 9.0.3 | ✅ |

**15/15.**

## Wiring triad

| Símbolo | Chamador em produção | Cobertura de teste |
|---|---|---|
| `scan_path` | 2 | 16 |
| `walk` | 4 | 10 |
| `mask` | 1 | 6 |
| `is_binary_path` | 1 | 4 |
| `render` | 1 (`cli.main`) | indireta, via 14 testes de `main()` |
| `build_parser` | 1 (`cli.main`) | indireta, via 14 testes de `main()` |

`render` e `build_parser` não têm teste direto. **Aceito**: são internos da camada de
interface e são exercidos pela fronteira (`main()`), o que `rules/testing.md § 4` prefere
— testar comportamento, não estrutura.

## Fronteiras de arquitetura

- Domínio (`errors`, `rules`, `finding`) não importa de aplicação nem de interface. ✅
- `print` e `sys.exit` existem **apenas** em `cli.py` e `__main__.py`. ✅
- Nenhuma abstração especulativa: sem interface com implementador único. ✅

## Achados

### MEDIUM-1 — README anunciava flags inexistentes *(corrigido nesta revisão)*

**Encontrado:** a seção "Todas as flags" listava `--staged`, `--history` e `--config`
como se existissem. O binário do M0 tem apenas `--show-secrets` e `--version`. Um leitor
que copiasse `gitsafety scan --history` receberia erro.

Era decisão consciente (Unresolved Question Q2 do plano: o README descreve o contrato do
produto M0-M5), e o `--help` do binário nunca mentiu — há teste garantindo isso. Mas o
README é o que a pessoa lê primeiro.

**Corrigido:** cada flag marcada com ✅ disponível / ⏳ em construção, e nota explicando
que o `--help` sempre lista só o que existe.

### LOW-1 — 6 achados de dead code no ferramental, em allowlist

Todos em `.claude/`, nenhum no produto. São parâmetros exigidos por contrato de interface
(`critical_paths` em stubs de `BaseDetector`, `option_string` em `argparse.Action`).
Isentados via ADR 0001 com sunset em 2026-10-25. Advisory, não bloqueia.

### INFO-1 — três divergências documentação-vs-parser no ecossistema

Encontradas e corrigidas durante o ciclo:

1. `discover-plan-thresholds.txt` em `KEY = VALUE`, parser exigia `|` → **todo** plano de
   descoberta reprovava como INVALID. Corrigido com testes de regressão.
2. `code-quality-languages.txt` documentava "um identificador por linha", parser exigia
   `LINGUAGEM|MANIFESTO|STATUS`. Corrigido.
3. `code-quality-allowlist.txt` e `code-quality-golden-rule.md § 4` documentam 4 campos;
   parser exige 6. Formato real documentado no arquivo; **corrigir o golden rule exige
   ADR próprio** (é documento LOCKED) — pendência aberta.

Padrão recorrente: arquivos de configuração cujo comentário de cabeçalho contradiz o
parser que os consome, sem teste cobrindo o parsing. Candidato a gate próprio.

## Verdicto

**`READY_TO_MERGE`**

Zero BLOCKER, zero HIGH. Um MEDIUM encontrado e corrigido dentro da própria revisão; um
LOW documentado em ADR com sunset; um INFO com uma pendência rastreada.

**Ressalva declarada:** revisão sem agentes independentes (ver § Método). Para um M0 sem
release publicado e com 92 testes cobrindo o comportamento, o risco é aceitável. Antes de
um release público — M6 —, uma revisão com olhos independentes é recomendada.
