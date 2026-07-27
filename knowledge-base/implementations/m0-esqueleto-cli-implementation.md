---
slug: m0-esqueleto-cli
milestone_id: M0
date: 2026-07-27
plan: knowledge-base/plans/m0-esqueleto-cli-plan.md
blueprint: knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md
status: IMPLEMENTATION_COMPLETE
---

# M0 — Log de implementação

## Resumo

Sete tasks entregues em ordem de dependência, cada uma com RED antes de GREEN e commit
atômico. 92 testes, todos verdes em Python 3.10 e 3.11. Zero dependências de runtime.

## Tasks e evidência

| Task | Commit | Testes | Evidência de que fechou |
|---|---|---|---|
| T1.1 — empacotamento | `c807480` | 3 | `gitsafety --version` returns `0` a partir de `/tmp`; console script resolvido por `sysconfig`, não pelo `PATH` |
| T1.2 — contrato de erro | `8789f6f` | 8 | `ExitCode(IntEnum)` 0/1/2; toda subclasse de `GitsafetyError` carrega `exit_code` |
| T2.1 — regra AWS | `1e27e9f` | 16 | 4 acertos e 6 não-acertos; padrão compilado no import |
| T2.2 — mascaramento | `1e27e9f` | 9 | `mask` preserva bordas e oculta miolo; segredo curto é ocultado por inteiro |
| T2.3 — walker | `2d78996` | 22 | `(files, skipped)`; extensão antes de tamanho; fronteira de 1 MB inclusiva |
| T2.4 — scanner | `2d78996` | 13 | linha 1-based com e sem `\n` final; `finditer` para dois segredos na mesma linha |
| T3.1 — CLI (wiring) | `2896f97` | 14 | três exit codes observados no binário real; saída mascarada por padrão |
| T3.2 — CI | (este) | — | matriz 3.10/3.13 + verificação do piso do pytest |
| T3.3 — benchmark | (este) | 4 | números abaixo |

## Wiring triad (T3.1)

| Pilar | Evidência |
|---|---|
| **Caller real** | `cli.main` chama `scan_path`; `__main__.main` é o entry point declarado em `[project.scripts]` |
| **Teste de integração** | `tests/functional/test_cli.py` (14 testes) exerce `main()` de ponta a ponta; `test_installed_entry_point.py` invoca o binário instalado como subprocesso |
| **Sinal observável** | A linha `N arquivo(s) pulado(s)` na saída — torna visível em runtime o descarte que, sem ela, seria falso negativo silencioso (ADR D3) |

## Benchmark — dados medidos

**Ambiente:** 13th Gen Intel Core i7-1355U, 16 GB RAM, Python 3.10.12, Linux 6.8.0.
**Corpus:** 1.000 arquivos `.py` determinísticos em 20 subdiretórios, 1 segredo a cada 100.
**Método:** `benchmarks/bench_scan.py`, `time.perf_counter`, uma passada de aquecimento
descartada antes da medição (a primeira leitura mede o cache de página do SO, não o scanner).

| Execução | `total_s` | `per_file_ms` | `files_per_s` | Segredos achados |
|---|---|---|---|---|
| 1 | 0,0140 s | 0,0140 ms | 71.545,5 | 10 / 10 |
| 2 | 0,0145 s | 0,0145 ms | 69.182,4 | 10 / 10 |
| 3 | 0,0150 s | 0,0150 ms | 66.476,6 | 10 / 10 |
| **Média ± σ** | **0,0145 ± 0,0005 s** | **0,0145 ms** | **69.068 ± 2.537** | **10 / 10** |

**Orçamento vs. medido:** o teste assert `total_s < 5.0`. O medido é **0,0145 s** —
cerca de **345×** abaixo do orçamento.

**Leitura honesta desse número.** A folga é grande porque o orçamento foi fixado
folgado de propósito (Unresolved Question Q1 do plano): ele existe para pegar regressão
de ordem de grandeza, não para ser um alvo apertado. O número que importa entre
milestones é `files_per_s`, porque independe do tamanho do corpus.

**Extrapolação para o M1.** Um commit típico toca de 5 a 20 arquivos. A 0,0145 ms por
arquivo, a verificação custaria cerca de **0,3 ms** — três ordens de grandeza abaixo do
`< 1 s` do `docs/PRD.md § NFR-2`. A conclusão prática é que, no M1, o custo dominante
será invocar o interpretador Python (dezenas de ms), não varrer os arquivos. É onde a
otimização deve olhar, se algum dia precisar.

**O que este benchmark NÃO mede:** repositório real (arquivos maiores e mais
heterogêneos que o corpus sintético), disco frio, Windows/macOS, e o custo de startup do
processo. Cada um é candidato a medição futura no `cycle-analysis`.

## Verificação dos DoD do `ROADMAP.md § M0`

| # | DoD | Status | Evidência |
|---|---|---|---|
| 1 | `pip install -e .` expõe `gitsafety` no PATH | ✅ | `test_installed_command_reports_version_from_outside_the_repo`; execução real returns `0` de `/tmp` |
| 2 | `scan` percorre arquivos de texto, aplica `AKIA[0-9A-Z]{16}` e imprime `arquivo:linha regra` | ✅ | Saída real: `config.py:1   aws-access-key-id   AKIA••••••••••••MPLE` |
| 3 | Exit 0 / 1 / 2, cada um coberto por teste | ✅ | `test_exit_code_is_{zero,one,two}_*` + os três observados no binário |
| 4 | Suíte roda com um comando e verde em CI | ✅ | `pytest -q` → 92 passed; verde em 3.10 **e** 3.11 localmente; workflow com matriz 3.10/3.13 |
| 5 | Binários e arquivos > 1 MB pulados | ✅ | `test_walk_reports_binary_file_as_skipped_*`, `test_file_at_exactly_the_limit_*` |

## Desvios em relação ao plano

| Desvio | Motivo |
|---|---|
| Piso Python 3.9 → **3.10** e `pytest` 8.x → **>=9.0.3** | `/deps-audit` achou `GHSA-6w46-j5rx-g56g` no pytest, corrigido só em 9.0.3, que exige Python >=3.10. Registrado como ADR D8 antes de escrever código; `docs/PRD.md § NFR-1` e `README.md` atualizados. |
| Teste do entry point resolve o script por `sysconfig` em vez de confiar no `PATH` | Confiar no `PATH` testaria o ambiente do desenvolvedor, não o pacote instalado. A resolução por `sysconfig` é o que torna a asserção honesta. |
| `conftest.py` na raiz (não previsto no plano) | Necessário para que `benchmarks/` seja importável pelos testes: o pacote de produto está em `src/` e é resolvido pela instalação editável, mas `benchmarks/` não é distribuído. |
| Padrão da regra ganhou lookaround `(?<![A-Z0-9])...(?![A-Z0-9])` | Sem delimitação, `AKIA[0-9A-Z]{16}` casaria o prefixo de uma cadeia maior e reportaria segredo inexistente. Falso positivo é o que faz desinstalar a ferramenta (`docs/PRD.md § 4`). |

## Limitações conhecidas, declaradas

1. **Falso negativo por extensão** (ADR D1) — arquivo de texto com extensão da lista
   binária nunca é varrido. Mitigado pelo ADR D3: ele aparece na saída como pulado.
2. **Falso negativo por encoding** (ADR D2) — arquivo em UTF-16 ou legado tem
   caracteres substituídos e pode não casar o padrão. Revisável no M4.
3. **Falso negativo por tamanho** — arquivo acima de 1 MB não é varrido, mesmo contendo
   segredo. Há teste que documenta esse comportamento explicitamente.
4. **Uma única regra** — o M0 detecta apenas chave de acesso AWS. O catálogo de ≥ 40
   padrões é o M2.

<promise>IMPLEMENTATION_COMPLETE</promise>
