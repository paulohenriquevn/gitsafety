# Review — M3: configuração `.gitsafety.yml`

**Data:** 2026-07-27 · **Slug:** `m3-config-yaml` · **Milestone:** M3
**Base do diff:** `v0.3.0..HEAD`

> **Método declarado.** Verificadores determinísticos, hard gates do `cycle-review` e
> cross-validation manual. Os agentes especialistas **não** foram gerados — mesma
> limitação declarada em M0, M1 e M2.

## Hard gates

| # | Gate | Resultado |
|---|---|---|
| 1 | Testes verdes | ✅ 542/542 |
| 2 | Nenhum segredo commitado | ✅ |
| 3 | Sem commit direto em `main` | ✅ `develop` |
| 4 | Nenhum trailer de coautoria | ✅ |
| 5 | `CHANGELOG.md` atualizado | ✅ |

**Nenhum BLOCKER.**

## Cross-validation

| # | Requisito | Verificação | Status |
|---|---|---|---|
| 1 | `ignore`, `allow`, `rules` | 21 testes + execução real | ✅ |
| 2 | `# gitsafety: allow` suprime a linha | Teste + execução real | ✅ |
| 3 | YAML malformado → exit 2 com a linha | 3 casos, duas classes de exceção | ✅ |
| 4 | Sem config a ferramenta funciona | Teste dedicado | ✅ |
| 5 | `--config PATH` | Execução real | ✅ |
| 6 | Regex inválida não derruba o processo | Erro tipado nomeando a regra | ✅ |
| 7 | Regex patológica não pendura o commit | Rejeitada **sem travar**, verificado com `timeout` | ✅ |
| 8 | Dependência pinada, superfície mínima | `pyyaml>=6.0.1,<7`; só `safe_load` | ✅ |
| 9 | Chave desconhecida não passa em silêncio | Erro com sugestão, verificado na prática | ✅ |
| 10 | Config vale no modo staged | `is_allowed` chamada dos dois caminhos | ✅ |
| 11 | Ignorado não vira ruído | Fora de `skipped` (D6) | ✅ |
| 12 | Chamadores do M0-M2 não quebram | 542 testes verdes sem edição dos anteriores | ✅ |
| 13 | Custo da config medido | 0, 10 e 50 regras | ✅ |
| 14 | Teto de 4 flags respeitado | Teste que conta as flags | ✅ |

**14/14.**

## Achados

### HIGH-1 — a defesa medida explodia junto com o que ela media *(corrigido)*

O plano previa, no ADR D3, detectar regex patológica **medindo** o tempo de execução
contra uma entrada adversarial. Implementado literalmente, isso **pendurou a suíte de
testes**: `search()` precisa retornar antes que o cronômetro seja lido, e é justamente o
retorno que nunca chega.

É um erro de raciocínio, não de código: uma defesa não pode depender de executar aquilo de
que protege. Corrigido invertendo as camadas — análise **estática** da forma perigosa como
defesa primária (`has_nested_quantifier`), medição progressiva com aborto precoce como rede
secundária.

**É o achado mais importante do milestone**, e ele só apareceu porque a implementação
seguiu o plano ao pé da letra em vez de contorná-lo.

### MEDIUM-1 — o detector novo acusava todo grupo não-capturante *(corrigido)*

`(?:` começa com `?`, e a primeira versão de `has_nested_quantifier` contava esse `?` como
quantificador. Como `unique_token` gera `(?<!…)`/`(?!…)` e o catálogo usa `(?:…)` em quase
toda regra, o M3 teria invalidado o M2 inteiro. Corrigido consumindo o prefixo de grupo
especial antes da análise.

### MEDIUM-2 — anotação de tipo sem import disparava `F821` *(corrigido)*

`"Config | None"` como string em `scanner` e `staged` — sem o import correspondente. O
lint pegou. Resolvido com `TYPE_CHECKING`, que satisfaz o analisador sem criar ciclo em
runtime.

### LOW-1 — o exemplo de YAML malformado do plano não era malformado

`ignore:\n  - a\n   - b\n` é **aceito** pelo PyYAML. O teste passou a usar três casos
reais, cobrindo `ParserError` **e** `ScannerError` — o que também fortaleceu a cobertura,
já que o precedente captura as duas justamente porque uma sozinha deixa metade escapar.

### LOW-2 — 6 soft caps no ferramental, sob ADR 0001

Os mesmos de M0-M2. Nenhum no produto.

### INFO-1 — PyYAML é agora superfície de CVE

Primeira dependência de runtime do produto. Pinada, com superfície de uma função. Todo
`/deps-audit` seguinte precisa auditá-la.

### INFO-2 — a análise de aninhamento é heurística

Reconhece a forma clássica, não toda construção patológica. Por isso a sonda progressiva
permanece como rede. Declarado no log.

## Verdicto

**`READY_TO_MERGE`**

Zero BLOCKER. Um HIGH que era erro de raciocínio do plano, encontrado pela implementação e
corrigido na causa; dois MEDIUM corrigidos; dois LOW; dois INFO rastreados.
