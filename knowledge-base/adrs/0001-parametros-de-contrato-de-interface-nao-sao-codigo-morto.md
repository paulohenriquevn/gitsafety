# ADR 0001 — Parâmetros exigidos por contrato de interface não são código morto

**Data:** 2026-07-27
**Status:** aceito
**Contexto do ciclo:** gate `/code-quality` do M0
**Exige:** entrada em `rules/code-quality-allowlist.txt` (golden rule § 4) e entrada de
CHANGELOG sob `[Unreleased] § Changed`

## Contexto

O gate `/code-quality` do M0 reportou 7 achados HARD de `dead_code_unallowlisted_python`,
todos no ferramental do ecossistema (`.claude/`), nenhum no código do produto
(`src/`, `tests/`, `benchmarks/`).

Um deles — import não usado em `.claude/scripts/check_xrefs.py:80` — era defeito real e
**foi corrigido**, não isentado.

Os outros 6 são de uma classe estrutural distinta: **parâmetros que existem porque um
contrato os exige, e cujo corpo legitimamente não os usa.**

| Achado | Por que o parâmetro existe |
|---|---|
| `critical_paths` em `detectors/__init__.py:57` | Assinatura de `BaseDetector.detect_mutation_score` — o contrato que todas as implementações concretas satisfazem |
| `critical_paths` em `detectors/{go,python,rust,typescript}.py` | Implementações que ainda levantam `NotImplementedError` (detector D4 de mutação, deferido). O parâmetro faz parte da assinatura herdada |
| `option_string` em `review/scripts/spawn_reviewers.py:118` | Assinatura de `argparse.Action.__call__`, definida pela biblioteca padrão |

## Decisão

Isentar os 6 achados via `rules/code-quality-allowlist.txt`, com sunset em **2026-10-25**
(90 dias, o teto permitido pelo golden rule § 4).

Não isentar o import não usado — esse foi removido.

## Rationale

Remover qualquer um dos 6 parâmetros quebraria o contrato que os justifica:

- Tirar `critical_paths` das implementações faria as subclasses divergirem da assinatura
  da base, violando LSP: `BaseDetector` deixaria de ser substituível pelas concretas.
- Tirar `option_string` quebraria a invocação feita pelo próprio `argparse`, porque a
  biblioteca padrão chama `Action.__call__` com quatro argumentos posicionais.

Ou seja: o detector está correto ao apontar "este nome não é lido", e errado ao concluir
"logo, é código morto". A conclusão não se sustenta quando o nome existe para satisfazer
um contrato externo.

**Alternativas consideradas:**

- **(a) Renomear para `_critical_paths` / `_option_string`.** Silenciaria o vulture, mas
  a convenção de prefixo `_` significa "privado", não "não usado", e o `option_string` é
  passado por nome pelo `argparse` em alguns caminhos. Trocaria um falso positivo por uma
  mentira de nomenclatura.
- **(b) Excluir `.claude/` inteiro do escopo do detector.** Tentada e **revertida**: as
  fixtures de autoteste da própria skill vivem sob `.claude/skills/code-quality/fixtures/`,
  e a exclusão cegou o teste `test_python_detector_flags_unused_function`. Um gate que
  não consegue testar a si mesmo é pior que o falso positivo que ele evitaria.
- **(c) Baixar `vulture.min_confidence` de 80 para 100.** Silenciaria os
  `critical_paths` (100% de confiança) — na verdade não, são justamente os de 100%. E
  reduziria a sensibilidade global do detector para resolver um caso pontual.
- **(d) Implementar o detector D4 agora, eliminando os stubs.** Fora do escopo do M0;
  mutação é trabalho de outro milestone, e antecipar viola YAGNI.

## Consequências

- Os 6 achados param de bloquear o `/review`, mas continuam **visíveis** no relatório de
  auditoria, na seção de allowlist — não somem.
- O sunset de 2026-10-25 força reavaliação. Quando o detector D4 for implementado, os 5
  achados de `critical_paths` desaparecem sozinhos e as entradas devem ser removidas.
- Se o `vulture` ganhar suporte a reconhecer parâmetros de método abstrato, as entradas
  ficam obsoletas e devem ser retiradas na mesma ocasião.
- **Nenhum achado no código do produto foi isentado.** `src/`, `tests/`, `benchmarks/` e
  `conftest.py` estão limpos sem qualquer exceção.

## Defeito de escopo corrigido junto

A investigação revelou que `PythonDetector.detect_dead_code` invocava
`vulture <repo_root>` **sem exclusão nenhuma**, auditando `.venv/` (bibliotecas de
terceiros) e `knowledge-base/references/` (repositórios clonados para estudo). Eram
147 achados HARD, dos quais 140 vinham de código que o time não escreveu e não pode
corrigir.

Corrigido em `DEAD_CODE_EXCLUDE_GLOBS`, com testes de regressão em
`skills/code-quality/tests/test_python_detector_exclusions.py`. Um gate que reprova por
código alheio é pior que gate nenhum: ensina o time a ignorá-lo.
