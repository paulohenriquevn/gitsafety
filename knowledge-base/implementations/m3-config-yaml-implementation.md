---
slug: m3-config-yaml
milestone_id: M3
date: 2026-07-27
plan: knowledge-base/plans/m3-config-yaml-plan.md
blueprint: knowledge-base/discoveries/blueprints/m3-config-yaml-blueprint.md
status: IMPLEMENTATION_COMPLETE
---

# M3 — Log de implementação

## Resumo

`.gitsafety.yml` com três chaves, 542 testes verdes, **uma** dependência de runtime
adicionada — a única que o `docs/PRD.md § NFR-1` autoriza. A partir daqui o orçamento de
dependências está esgotado.

## O defeito de design que a implementação revelou

O plano dizia, no ADR D3, que a defesa contra regex patológica seria "medir contra entrada
adversarial". Implementei exatamente isso: sonda de 4.000 caracteres, cronometrada.

**A suíte de testes pendurou.**

A causa é estrutural e vale mais que o milestone: **uma regex patológica explode durante a
própria medição**. O `compilado.search(sonda)` precisa retornar antes que a verificação de
tempo possa ser avaliada — e é justamente o retorno que nunca chega. A defesa não pode
depender de executar aquilo de que protege.

A correção reordenou as camadas:

1. **Defesa primária, estática** — `has_nested_quantifier` reconhece a *forma* perigosa
   (`(a{1,50}){1,50}`, `(a+)+`, `(\d{2,4})*`) **sem executá-la**. Note que
   `has_free_quantifier`, do M2, não alcança esse caso: todos os limites estão definidos.
2. **Rede secundária, progressiva** — sondas de 16, 32 e 64 caracteres, com aborto no
   primeiro degrau lento. Nunca se roda uma entrada longa numa regex que já foi lenta numa
   curta, então o custo do pior caso fica limitado pelo primeiro degrau.

O detector novo teve um falso positivo próprio, também corrigido: `(?:` começa com `?`, e
a primeira versão contava esse `?` como quantificador — o que faria **todo** grupo
não-capturante acusar. Nosso `unique_token` gera `(?<!…)` e `(?!…)`, e o catálogo usa
`(?:…)` em quase toda regra; sem o tratamento do prefixo de grupo, o M3 teria quebrado o
M2 inteiro.

## Benchmark — custo de carregar a config

**Ambiente:** i7-1355U, 16 GB, Python 3.10.12.

| Regras de usuário | Tempo de carga |
|---|---|
| 0 | 2,060 ms |
| 10 | 4,470 ms |
| 50 | 10,600 ms |

- Custo marginal: **0,171 ms por regra de usuário**.
- Somado ao overhead do hook medido no M1 (~40 ms): **~50,6 ms**.
- Teto do `docs/PRD.md § NFR-2`: 1.000 ms → **20× de folga**.

A validação adversarial, que é o que protege o commit, custa fração de milissegundo por
regra. O medo de que a defesa fosse cara não se confirmou.

## Verificação dos DoD do `ROADMAP.md § M3`

| # | DoD | Status | Evidência |
|---|---|---|---|
| 1 | `ignore`, `allow`, `rules` implementadas | ✅ | 21 testes de config + execução real |
| 2 | `# gitsafety: allow` suprime o finding da linha | ✅ | `test_inline_marker_suppresses_only_its_own_line` |
| 3 | YAML malformado → exit 2 com a linha | ✅ | 3 casos parametrizados cobrindo `ParserError` **e** `ScannerError` |
| 4 | Sem config a ferramenta funciona | ✅ | `test_missing_config_file_returns_empty_config` |
| 5 | `--config PATH` | ✅ | Execução real; teto de 4 flags verificado por teste |

## Evidência de execução real

| Cenário | Resultado |
|---|---|
| Sem config | 1 finding, exit 1 |
| `allow` com o valor | 0 findings, exit 0 |
| `ignroe:` (erro de digitação) | exit 2 — *"chave desconhecida `ignroe`. Você quis dizer `ignore`?"* |
| Regex patológica `(a{1,50}){1,50}b` | exit 2 **sem travar**, com explicação da forma |
| Regex `.*` | exit 2, sugerindo limite superior |
| Regra de usuário legítima | Detectada e **mascarada**: `INT_••••••2345` |

## Desvios em relação ao plano

| Desvio | Motivo |
|---|---|
| `has_nested_quantifier` acrescentado; medição virou secundária | O plano previa medição como defesa principal. A implementação provou que não funciona — a medição explode junto com a regex. |
| Sonda progressiva (16/32/64) no lugar da única de 4.000 | Aborto precoce limita o custo do pior caso ao primeiro degrau. |
| `TYPE_CHECKING` para a anotação de `Config` em `scanner`/`staged` | `config` importa desses módulos; a anotação em string sozinha disparou `F821` no lint, e o `TYPE_CHECKING` resolve sem ciclo em runtime. |
| Exemplo de YAML malformado trocado | O do plano (`indentação inconsistente`) é **aceito** pelo PyYAML. Substituído por três casos reais, cobrindo as duas classes de exceção. |

## Limitações conhecidas, declaradas

1. **A análise estática de aninhamento é heurística.** Reconhece a forma clássica, não
   toda construção patológica. Por isso a sonda progressiva continua existindo como rede.
2. **`allow` largo demais silencia detecção legítima.** É poder que o usuário pede
   explicitamente; documentado no README como última opção.
3. **`ignore` largo demais esconde arquivos sem aviso** (ADR D6) — decisão do usuário, num
   arquivo que ele escreveu.
4. **PyYAML é agora superfície de CVE do produto.** Pinado `>=6.0.1,<7`, superfície de uso
   de **uma** função. Todo `/deps-audit` seguinte precisa auditá-lo.

<promise>IMPLEMENTATION_COMPLETE</promise>
