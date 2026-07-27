---
slug: m2-catalogo-de-padroes
milestone_id: M2
date: 2026-07-27
plan: knowledge-base/plans/m2-catalogo-de-padroes-plan.md
blueprint: knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md
status: IMPLEMENTATION_COMPLETE
---

# M2 — Log de implementação

## Resumo

**53 regras** em 6 categorias (DoD pede ≥ 40), 512 testes verdes, zero dependências
novas. Zero falsos positivos no corpus limpo.

## Catálogo entregue

| Categoria | Regras | Exemplos |
|---|---|---|
| Cloud | 8 | AWS (4 prefixos), GCP, Azure, DigitalOcean, Heroku, Cloudflare |
| Controle de versão e pacotes | 11 | GitHub (5 tipos de token), GitLab, npm, PyPI, RubyGems, crates.io |
| IA e dados | 6 | OpenAI, Anthropic, Hugging Face, Cohere, Replicate, W&B |
| Pagamentos e SaaS | 19 | Stripe, Twilio, SendGrid, Slack, Sentry, Shopify, Atlassian, JWT |
| Chaves privadas | 4 | PEM, PuTTY, PKCS#8, age |
| Banco de dados | 5 | PostgreSQL, MySQL, MongoDB, Redis, AMQP |

## Benchmark de escala — a pergunta do milestone, respondida

**Ambiente:** i7-1355U, 16 GB, Python 3.10.12. Corpus do M0: 1.000 arquivos.

| Regras | Tempo | Findings |
|---|---|---|
| 1 | 0,0617 s | 10 |
| 10 | 0,0970 s | 10 |
| **53** | **0,3583 s** | 10 |

- **53× mais regras → 5,8× mais tempo.** Sublinear: a travessia de arquivo domina.
- Custo marginal: **5,7 ms por regra** por 1.000 arquivos.
- Orçamento de 5 s: **14× de folga**.

**Decisão sobre o pré-filtro por palavra-chave: `desnecessário` (YAGNI).** A Unresolved
Question Q3 do plano foi respondida com dado: o custo não escala com o número de regras.
Extrapolando para o hook do M1, o overhead sobe de ~40 ms para ~49 ms — ainda 20× abaixo
do teto de 1 s do `NFR-2`.

## Otimização medida, não especulativa

Ao comparar com o M0 notei que **uma** regra havia ficado mais lenta. Isolei a causa:

| Padrão | Tempo (1.000 arquivos) |
|---|---|
| M0: `AKIA[0-9A-Z]{16}` (literal) | 0,0280 s |
| M2 inicial: `(?:AKIA\|ASIA\|ABIA\|ACCA)…` | 0,0473 s |
| M2 final: `A(?:KIA\|SIA\|BIA\|CCA)…` | 0,0299 s |

**Alternância no topo derrota a otimização de prefixo literal do `re`.** Fatorar o `A`
comum recupera quase toda a perda. Aplicado também à regra de GitHub App
(`(?:ghu\|ghs)_` → `gh[us]_`). Efeito no catálogo completo: 0,5656 → **0,3583 s** (37%),
e a suíte caiu de 14,5 s para 6,5 s.

## Falso positivo

Corpus limpo gerado por código, com as formas que um padrão largo demais confundiria:
SHA-256, SHA-1, MD5, UUID v4, ULID, base64 de PNG, chave pública SSH, cabeçalho PEM
**público**, certificado, e URLs de banco locais sem senha.

**Resultado: 0 findings**, na primeira execução, sem ajuste de regra.

## Verificação dos DoD do `ROADMAP.md § M2`

| # | DoD | Status | Evidência |
|---|---|---|---|
| 1 | ≥ 40 padrões, cada um com acerto e não-acerto | ✅ | 53 regras; 4 testes parametrizados percorrem o catálogo inteiro |
| 2 | Segredo mascarado; `--show-secrets` revela | ✅ | Saída real de 5 categorias diferentes, todas mascaradas |
| 3 | Corpus limpo → zero findings | ✅ | `test_clean_corpus_produces_zero_findings` |
| 4 | Padrões em arquivo de dados versionado | ✅ | `catalog.py` com tupla literal única |

## Dois defeitos encontrados e corrigidos durante a implementação

**1. Falso positivo no próprio detector de quantificador.** A primeira versão de
`has_free_quantifier` acusava `[\w./+-]` — o `+` ali está **dentro de classe de
caracteres** e é literal. Pior: esse padrão é gerado pelo próprio `unique_token`. Um
detector ruidoso acaba desligado, e é assim que uma defesa morre. Reescrito para percorrer
o padrão caractere a caractere, distinguindo escapado / dentro de classe / quantificador.

**2. Falso negativo em string de conexão** — **encontrado só na validação de integração**,
depois de 511 testes verdes. `postgresql://app:senha@db.com/prod` não era detectado: o
lookahead final de `unique_token` rejeita `/`, e no uso real o host é sempre seguido do
caminho do banco. Os testes unitários passavam porque os exemplos da regra terminavam no
host. As 5 regras de conexão passaram a usar `literal_marker`, como os blocos PEM.

O segundo caso é a lição do milestone: **a validação de integração pegou o que 511 testes
unitários não pegaram**, e era um falso negativo silencioso — a categoria mais cara.

## Desvios em relação ao plano

| Desvio | Motivo |
|---|---|
| `Rule` migrou de `rules.py` para `patterns.py` | `rules.py` acumulava tipo **e** registro; o acoplamento produziu import circular assim que o catálogo virou módulo. Separar resolveu a causa. `rules.py` virou fachada, e `scanner.py`/`staged.py` seguem intocados. |
| Terceiro construtor `literal_marker` | Blocos PEM começam com `-`, que `unique_token` recusa de propósito. Enfraquecer a guarda seria pior — ela protege contra a regra que nunca casa. Construtor estreito e nomeado deixa explícito quais padrões dispensam delimitação. |
| Slack webhook ancorado no esquema `https://` | O padrão começava em `hooks.slack.com`, precedido pela `/` de `https://`, que o lookbehind exclui. O padrão estava subespecificado. |
| `per-file-ignores` para E501 em `clean_corpus.py` | O arquivo embute o **conteúdo** de arquivos em literais; ali comprimento é dado, e quebrar mudaria o corpus que a métrica mede. |
| 53 regras, não 40 | As 6 categorias do README pediram isso. O plano dizia para cobrir as categorias e não perseguir um número. |

## Limitações conhecidas, declaradas

1. **O corpus limpo é sintético.** Pode não conter a forma exata que causaria um falso
   positivo real. Mitigado por incluir as formas conhecidas de quase-acerto.
2. **`sk_test_` da Stripe entra como false positive da regra** — chave de ambiente de
   teste. Onde o provedor não distingue teste de produção no formato, a limitação fica
   para o `allow:` do M3.
3. **Padrões vindos do `rules:` do usuário (M3) não terão a garantia do ADR D2** — nem
   análise de quantificador, nem teto de tempo. Risco a declarar naquele milestone.
4. **A amostra de regras do gitleaks foi dirigida, não exaustiva** (D2 do blueprint):
   podem existir formatos de provedor fora do molde que não inventariamos.

<promise>IMPLEMENTATION_COMPLETE</promise>
