# Review — M2: catálogo de padrões

**Data:** 2026-07-27 · **Slug:** `m2-catalogo-de-padroes` · **Milestone:** M2
**Base do diff:** `v0.2.0..HEAD`

> **Método declarado.** Verificadores determinísticos, hard gates do `cycle-review` e
> cross-validation manual. Os 5-7 agentes especialistas **não** foram gerados — mesma
> limitação declarada em M0 e M1.

## Hard gates

| # | Gate | Resultado |
|---|---|---|
| 1 | Testes verdes | ✅ 512/512 |
| 2 | Nenhum segredo commitado | ✅ |
| 3 | Sem commit direto em `main` | ✅ `develop` |
| 4 | Nenhum trailer de coautoria nos commits | ✅ 0 ocorrências |
| 5 | `CHANGELOG.md` atualizado | ✅ |

**Nenhum BLOCKER.**

## Cross-validation

| # | Requisito | Verificação | Status |
|---|---|---|---|
| 1 | ≥ 40 padrões nas 6 categorias | 53 regras; teste de contagem e de cobertura | ✅ |
| 2 | Cada padrão com acerto e não-acerto | 4 testes parametrizados sobre o catálogo | ✅ |
| 3 | Segredo mascarado | Saída real: 5 categorias, todas mascaradas | ✅ |
| 4 | Corpus limpo → zero findings | `test_clean_corpus_produces_zero_findings` | ✅ |
| 5 | Padrões em arquivo de dados | `catalog.py`, tupla literal única | ✅ |
| 6 | Nenhum padrão largo demais | fps obrigatórios + corpus + teste de sobreposição | ✅ |
| 7 | Nenhuma regex patológica | Análise estática **e** medição de tempo | ✅ |
| 8 | Sem dependência nova | `dependencies = []` | ✅ |
| 9 | Custo de 53 regras medido | 5,8× para 53× regras | ✅ |
| 10 | Decisão sobre pré-filtro com dado | `desnecessário`, registrado no log | ✅ |
| 11 | Exemplos em contexto de código | tps com atribuição e variável de ambiente | ✅ |
| 12 | `scanner`/`staged` inalterados | `git diff --name-only` não os contém | ✅ |
| 13 | Chaves de exemplo não acusam | No corpus e como fps | ✅ |
| 14 | Falha nomeia a regra | `pytest.param(id=rule.id)` | ✅ |

**14/14.**

## Achados

### HIGH-1 — falso negativo em string de conexão *(corrigido)*

Encontrado na **validação de integração**, após 511 testes unitários verdes.
`postgresql://app:senha@db.com/prod` não era detectado — o lookahead final de
`unique_token` rejeita `/`, e no uso real o host é sempre seguido do caminho do banco.

Os unitários passavam porque os exemplos da regra terminavam no host. **É o achado mais
importante do milestone**: falso negativo silencioso, a categoria mais cara, que só a
execução real revelou. Corrigido com `literal_marker` nas 5 regras de conexão, com teste
de regressão que reproduz o cenário exato.

A lição vale além do M2: cobertura de teste unitário alta não substitui execução real
quando os exemplos do teste são escolhidos pela mesma pessoa que escreveu o padrão.

### MEDIUM-1 — falso positivo no detector de quantificador *(corrigido)*

`has_free_quantifier` acusava `[\w./+-]` — o `+` dentro de classe de caracteres é
literal. O padrão é gerado pelo próprio `unique_token`, então a defesa acusava a si
mesma. Reescrito para percorrer o padrão distinguindo escapado / dentro de classe /
quantificador.

### LOW-1 — 6 soft caps no ferramental, sob ADR 0001

Os mesmos de M0 e M1. Nenhum no código do produto.

### INFO-1 — corpus limpo é sintético

Pode não conter a forma exata que causaria um falso positivo real. Declarado no log de
implementação.

### INFO-2 — regras do usuário (M3) não terão a garantia do ADR D2

Padrões vindos do `rules:` do YAML não passarão pela análise de quantificador nem pelo
teto de tempo. Risco a declarar no M3.

## Verdicto

**`READY_TO_MERGE`**

Zero BLOCKER. Um HIGH encontrado pela validação de integração e corrigido com regressão;
um MEDIUM corrigido; um LOW sob ADR; dois INFO rastreados.
