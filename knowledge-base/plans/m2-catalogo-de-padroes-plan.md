---
slug: m2-catalogo-de-padroes
milestone_id: M2
created_at: 2026-07-27
goal: Elevar o catálogo de 1 para mais de 40 padrões de credencial, sem gerar falso positivo e sem que nenhuma regex possa pendurar o commit.
---

# Plan: M2 — Catálogo de padrões e mascaramento

## Goal

O gitsafety passa a detectar ≥ 40 padrões de credencial cobrindo as 6 categorias que o
`README.md` promete, cada um com teste de acerto **e** de não-acerto, com prova mecânica de
que nenhum padrão tem quantificador livre e de que nenhum demora mais que um teto por
entrada. Um corpus limpo de referência produz **zero findings**.

## Context

Terceiro milestone. O M0 plantou a forma (`Rule` congelada com casos anexos) e o M1 pôs o
motor dentro do `git commit`. O M2 escala a forma de 1 para 40+, e é aqui que os dois
riscos declarados no `ROADMAP.md § M2` deixam de ser teóricos.

O blueprint `knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md`
(SHIPPABLE 100.0) travou 5 ADRs. O achado que mais muda este milestone: o gitleaks roda em
**RE2, que não faz backtracking**; nós rodamos em `re` do Python, que faz. A disciplina de
quantificador limitado que para eles é higiene, para nós é **defesa** — desde o M1 uma
regex patológica não é lentidão, é o commit do usuário pendurado.

## Baseline Context (deep review of current state)

**Estado:** branch `develop`, tag `v0.2.0`, working tree limpo, 144 testes verdes. O
catálogo tem **uma** regra (`aws-access-key-id`), com lookaround de delimitação que já
antecipa a família 1 do blueprint.

### Files that will be touched

| File | LoC hoje | Último commit | Por que existe hoje | Invariantes a preservar |
|---|---|---|---|---|
| `src/gitsafety/rules.py` | 45 | `1e27e9f` | `Rule` + `BUILTIN_RULES` com 1 regra | `Rule` é congelada; `BUILTIN_RULES` é tupla; `pattern` compilado no import |
| `src/gitsafety/patterns.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/catalog.py` (NOVO) | 0 | — | (a criar) | — |
| `tests/unit/test_rules.py` | 112 | `1e27e9f` | Testes da regra AWS | Os 10 testes atuais devem continuar passando |
| `tests/unit/test_patterns.py` (NOVO) | 0 | — | (a criar) | — |
| `tests/unit/test_catalog.py` (NOVO) | 0 | — | (a criar) | — |
| `benchmarks/bench_catalog.py` (NOVO) | 0 | — | (a criar) | — |
| `README.md` | 253 | `7b87d98` | Contrato público | A tabela de categorias deve refletir o que existe |

### Current callers / dependents

- `scanner.scan_path` e `staged.scan_staged` recebem `rules: Sequence[Rule] = BUILTIN_RULES`.
  Ampliar a tupla **não** muda a assinatura de nenhum dos dois — é o que torna este
  milestone aditivo.
- `cli.render` imprime `f.rule_id`. Ids novos aparecem na saída sem mudança de código.
- Nenhum consumidor externo: nada publicado no PyPI.

### Domain glossary

- **Token único** — família de padrão em que o valor carrega a própria identidade (`AKIA…`, `ghp_…`) e basta delimitá-lo com `\b`.
- **Semi-genérico** — família em que o valor não é reconhecível sozinho e a regra exige palavra-chave, operador de atribuição e delimitador ao redor.
- **Quantificador livre** — `*`, `+` ou `{n,}` sem teto superior. Proibido no catálogo (ADR D2 do blueprint).
- **Backtracking catastrófico** — explosão exponencial de tentativas do motor `re` diante de quantificadores aninhados; em RE2 não existe, em Python sim.
- **True positive (tp)** — exemplo que a regra **deve** casar, em contexto de código.
- **False positive (fp)** — exemplo que a regra **não** deve casar; é a metade que costuma faltar.
- **Corpus limpo** — árvore de arquivos sabidamente sem segredo, usada para medir falso positivo de forma reprodutível.

### Architecture boundaries affected

```
domínio        errors.py, finding.py, patterns.py, rules.py, catalog.py
aplicação      walker.py, scanner.py, staged.py
infraestrutura git.py
interface      cli.py, hook.py, __main__.py
```

`patterns.py` (construtores) e `catalog.py` (os dados) são **domínio puro** — importam
apenas `re` e `dataclasses`. Nenhuma camada superior muda: o M2 é aditivo por construção.

## Prior Art & Related Work

| Fonte | O que aproveitamos | Citação |
|---|---|---|
| Blueprint do M2 | Os 5 ADRs são entrada travada | `knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md` |
| gitleaks | Duas famílias de padrão | `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:34,69` |
| gitleaks | Constantes de delimitação e janelas limitadas | `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:14-31` |
| gitleaks | Validação dos dois lados na construção da regra | `knowledge-base/references/gitleaks/cmd/generate/config/utils/validate.go:16-39` |
| gitleaks | Lista literal única como registro do catálogo | `knowledge-base/references/gitleaks/cmd/generate/config/main.go:30` |
| gitleaks | Exemplos em contexto de código, por template | `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:85,112` |
| Blueprint do M0 | `Rule` congelada, padrão compilado no import | `knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md` |
| `rules/testing.md § 4.1` | Edge case × negative case aplicado a cada regra | `rules/testing.md` |
| `rules/parsimony-ladder.md` | Rung 5 sustenta o D4 (não criar 40 arquivos) | `rules/parsimony-ladder.md` |

## Objective

Ao fim do M2, `gitsafety scan` detecta credenciais das 6 categorias do README; o teste do
catálogo prova que cada regra casa seus acertos e ignora seus não-acertos; um teste
mecânico prova que nenhum padrão tem quantificador livre; um teste de tempo prova que
nenhum demora mais que o teto; e o corpus limpo produz zero findings.

## ADRs

D1-D5 vêm do blueprint, restatados aqui em forma executável; texto integral em
`knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md § ADRs`.
D6-D7 são deste plano.

### D1 — Duas famílias de padrão, com o M2 privilegiando token único

**Decisão:** construtores `unique_token(...)` e `keyword_assignment(...)`. A maioria dos
≥ 40 padrões usa o primeiro.

**Rationale:** `generate.go:69-78` e `:34-46`. Token único é intrinsecamente seguro contra
falso positivo — `AKIA` + 16 maiúsculas não é outra coisa. Semi-genérico depende de
contexto e é onde o falso positivo mora; o `docs/PRD.md § 4` já decidiu não ligá-lo por
padrão.

**Alternativas consideradas:** (a) só token único — deixaria de fora string de conexão de
banco, que o README promete; (b) só semi-genérico — exigiria palavra-chave perto de um
`AKIA…`, gerando falso **negativo** no caso mais comum; (c) família por entropia —
não-objetivo declarado (`PRD § 5 NG4`).

**Consequências:** `Rule` não muda — ambas as famílias produzem um `re.Pattern`. O que
nasce é o construtor.

### D2 — Nenhum quantificador livre, verificado mecanicamente

**Decisão:** nenhum padrão do catálogo usa `*`, `+` ou `{n,}` sem teto. Um teste percorre
os padrões e falha se encontrar qualquer um.

**Rationale:** disciplina literal de `generate.go:14-31` — `{0,50}?`, `{0,20}`, `{0,5}`,
`{0,3}`, sem um único quantificador livre. No RE2 do gitleaks é higiene; no `re` do Python
é defesa, porque desde o M1 a regex roda dentro do `git commit`.

**Alternativas consideradas:** (a) permitir quantificador livre com timeout — timeout no
meio de um hook deixa o usuário sem resposta clara e mascara o defeito; (b) migrar para
`re2` do PyPI — gastaria a única dependência autorizada, reservada ao YAML do M3; (c)
confiar na revisão humana — é exatamente o defeito que passa em revisão.

**Consequências:** padrões vindos do `rules:` do YAML (M3) **não** terão essa garantia;
risco a declarar naquele milestone.

### D3 — Um teste percorre o catálogo inteiro, verificando os dois lados

**Decisão:** teste parametrizado sobre `BUILTIN_RULES` verificando, para cada regra, que
todos os tps casam e nenhum fp casa. Exemplos vivem junto da regra.

**Rationale:** `validate.go:16-39` faz isso e mata o processo em caso de falha. Não podemos
matar na importação, mas podemos tornar impossível uma regra chegar ao `main` sem os dois
lados verificados: o teste falha e o CI barra.

**Alternativas consideradas:** (a) teste por regra escrito à mão — com 40 regras alguém
esquece a 41ª, silenciosamente; (b) validar na importação com `assert` — `assert` some com
`python -O`; (c) validar só tps — metade do trabalho, justamente a que não protege contra o
Risco nº 1.

**Consequências:** regra sem exemplos faz o teste falhar **por ausência**, não passar por
omissão.

### D4 — Catálogo como módulo de dados com tupla literal única

**Decisão:** todas as regras em `catalog.py`, registradas numa tupla literal única,
agrupadas por categoria.

**Rationale:** o gitleaks usa arquivo-por-regra + lista em `main.go:30`. Arquivo-por-regra
paga por si com 131 regras; com 40 seria cerimônia (`parsimony-ladder.md` rung 5). O que
transfere é a **lista literal única**: regra fora da tupla não existe, e a tupla é onde o
revisor vê o catálogo inteiro.

**Alternativas consideradas:** (a) arquivo por regra — desproporcional a 40; reavaliar acima
de ~100; (b) carregar de YAML/JSON — adia a falha para runtime; (c) descoberta por
introspecção — remove o ponto único de revisão, que é o valor da lista.

**Consequências:** `catalog.py` fica grande. Aceitável para dados; a lógica fica fora.

### D5 — Exemplos em contexto de código, não valor nu

**Decisão:** os tps de cada regra incluem o segredo em atribuição, variável de ambiente ou
JSON — não apenas o valor solto.

**Rationale:** `generate.go:85,112` monta exemplos por template de linguagem. Um padrão que
casa `AKIAIOSFODNN7EXAMPLE` mas falha em `AWS_KEY="AKIAIOSFODNN7EXAMPLE"` passaria no teste
com valor nu e falharia no uso real, porque o sufixo delimitador exige a aspa.

**Alternativas consideradas:** (a) só valor nu — testa o regex, não a regra; (b) gerador de
contextos como o gitleaks — bom, mas seria abstração para um caso
(`parsimony-ladder.md` rung 1).

**Consequências:** mais exemplos por regra; arquivo de teste maior. É o preço de testar a
regra.

### D6 — Teto de tempo por regra, medido, além da análise estática

**Decisão:** um teste mede o tempo de cada regra contra entradas adversariais e falha se
qualquer uma exceder um teto por entrada.

**Rationale:** o D2 é análise **estática** — pega quantificador livre, mas não pega toda
construção patológica (alternância aninhada com prefixos comuns, por exemplo, pode
degradar sem nenhum quantificador livre). A única prova de que nenhuma regra pendura o
commit é medir. `rules/testing.md § 4.1`: o caso adversarial é caso negativo, e ele existe.

**Alternativas consideradas:** (a) só a análise estática do D2 — insuficiente pelo motivo
acima; (b) só medição, sem D2 — a medição depende das entradas escolhidas e pode não
alcançar o pior caso; a análise estática é a rede que não depende de imaginação; (c)
timeout em produção — mascara o defeito em vez de impedi-lo, e no meio de um hook deixa o
usuário sem resposta.

**Consequências:** é preciso construir entradas adversariais — cadeias longas de
caracteres que casam parcialmente o prefixo de cada família. Elas viram fixture.

### D7 — Corpus limpo nomeado e versionado, para a métrica de falso positivo

**Decisão:** o corpus de referência para "zero findings" é gerado por código
determinístico, versionado no repositório, e cobre as formas em que um falso positivo
apareceria: hashes, UUIDs, base64, chaves de exemplo de documentação, e código real de
várias linguagens.

**Rationale:** o `ROADMAP.md § M2` pede "repositório limpo de referência produz zero
findings", mas sem nomear o corpus a métrica não é reprodutível — e uma métrica não
reprodutível não detecta regressão. Gerar por código, em vez de commitar arquivos de um
projeto real, evita trazer licença de terceiro e mantém o corpus legível no diff.

**Alternativas consideradas:** (a) usar o próprio repositório do gitsafety como corpus —
tentador e **errado**: ele contém `AKIAIOSFODNN7EXAMPLE` nos testes de propósito; (b) usar
um dos peers clonados — traz licença de terceiro para dentro da métrica e o conteúdo muda
quando o clone for atualizado; (c) não medir — deixa o DoD sem evidência.

**Consequências:** o corpus é sintético e pode não conter a forma exata que causaria um
falso positivo real. Limitação a declarar; mitigada por incluir as formas conhecidas de
quase-acerto.

## Drawbacks & Risks

| Drawback / Risco | Severidade | Mitigação | Dono |
|---|---|---|---|
| Um dos 40 padrões é largo demais e gera falso positivo | Alta | Cada regra tem fps obrigatórios (D3); corpus limpo mede o agregado (D7); família token único é a base (D1) | dev |
| Uma regex degrada por construção sem ter quantificador livre | Alta | D6 mede tempo com entradas adversariais, além da análise estática do D2 | dev |
| 40 regras tornam a varredura 40× mais lenta | Média | T3.2 mede a escala 1 → 40 regras; se for linear e relevante, pré-filtro por palavra-chave vira tarefa, não suposição | dev |
| Padrões de provedor mudam de formato e o catálogo envelhece | Média | Cada regra cita a fonte do formato num comentário; o teste falha se o exemplo parar de casar | dev |
| Copiar padrão do gitleaks sem verificar em `re` do Python | Alta | Nenhum padrão é copiado literalmente: os construtores montam a partir das partes, e D2 + D6 verificam no nosso motor | dev |
| Chave de exemplo de documentação (AWS, Stripe) aparece em código real e vira falso positivo | Média | As chaves de exemplo conhecidas entram como fps das próprias regras; o `allow:` do M3 cobre o resto | dev |
| `catalog.py` grande vira difícil de revisar | Baixa | Agrupamento por categoria com comentário; a tupla literal dá visão única (D4) | dev |

## Unresolved Questions

- Q1 — **Qual o teto de tempo aceitável por regra?** Não há número no PRD. **Resolução
  adotada:** T2.2 assert `< 0.05` s por regra contra a pior entrada adversarial — folgado
  o bastante para não ser flaky em CI, apertado o bastante para pegar degradação de ordem
  de grandeza. Revisável com dado.
- Q2 — **Quantos padrões, exatamente?** O `ROADMAP.md` pede ≥ 40. **Resolução adotada:**
  cobrir as 6 categorias do README com os provedores nomeados, e parar quando as
  categorias estiverem cobertas — não perseguir um número. Se ficar abaixo de 40, o DoD
  não é atendido e a lacuna é declarada em vez de preenchida com padrões de baixo valor.
- Q3 — **O pré-filtro por palavra-chave é necessário?** O gitleaks tem `Keywords` na
  estrutura da regra. **Resolução adotada:** não implementar agora. T3.2 mede se 40 regras
  custam o suficiente para justificá-lo; sem esse dado, seria otimização especulativa
  (`parsimony-ladder.md` rung 1).

## Dependency Graph

```
T1.1 (patterns.py — construtores das duas famílias)
  └─> T1.2 (catalog.py — as 40+ regras com exemplos)
        ├─> T2.1 (teste do catálogo: dois lados de cada regra)
        ├─> T2.2 (teste mecânico de quantificador + teto de tempo)
        └─> T3.1 (corpus limpo + métrica de falso positivo)
              └─> T3.2 (benchmark de escala 1 -> 40 regras)
```

## Dependencies

| Dependência | Escopo | Versão | Rule 9 |
|---|---|---|---|
| *(nenhuma)* | runtime | — | **O M2 não adiciona dependência de runtime.** Construir padrão é montagem de string e `re.compile`; a stdlib cobre. Confirmado pelo Q6 do blueprint: o gerador do gitleaks importa só `fmt`, `strings` e um wrapper interno de `regexp`. |
| `pytest` | dev | `>=9.0.3,<10` | Já declarado. Piso mantido por `GHSA-6w46-j5rx-g56g`. |
| `ruff` | dev | `>=0.6,<1` | Já declarado. |

Nenhuma dependência nova → nenhuma superfície de CVE nova.

---

## Phase 1: Construtores e catálogo

### T1.1 — `patterns.py`: construtores das duas famílias

#### Objective

Montar padrões a partir de partes verificadas, em vez de escrever 40 regexes à mão.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `patterns.py` com `unique_token()` e `keyword_assignment()`.
**Raciocínio:** escrever 40 regexes à mão garante que ao menos uma saia sem delimitação ou
com quantificador livre — é erro de digitação com consequência de segurança. Centralizar a
montagem faz a disciplina do D2 valer por construção, não por revisão. Vem primeiro porque
o catálogo inteiro depende dela.

#### Evidence

- `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:69-78` — família token único
- `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:34-46` — família semi-genérica
- `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:14-31` — as constantes de delimitação

#### Files to edit

- `src/gitsafety/patterns.py` (NOVO)

#### Deep file dependency analysis

Domínio puro: importa só `re`. Consumido por T1.2.

#### Deep Dives

O `secretSuffix` do gitleaks — `)(?:[\x60'"\s;]|\\[nr]|$)` — é um grupo **não capturante**
que consome o delimitador. Em Python, consumir o delimitador impede que dois segredos
adjacentes separados por um único caractere sejam ambos encontrados. Usar **lookahead**
`(?=[...]|$)` em vez de consumir preserva a posição e evita esse falso negativo. É uma
divergência consciente do precedente, motivada pela diferença de uso: nós rodamos
`finditer` sobre a linha inteira.

O `\b` do `secretPrefixUnique` não funciona quando o prefixo começa com caractere não-word.
Todos os nossos prefixos (`AKIA`, `ghp_`, `sk-`) começam com letra, então `\b` serve —
mas o construtor deve rejeitar prefixo que comece com não-word, em vez de gerar
silenciosamente um padrão que nunca casa.

#### Pseudo-code / Signatures

```python
FREE_QUANTIFIER_RE = re.compile(r"(?<!\\)[*+]|\{\d+,\}")

def unique_token(secret_regex: str, *, case_insensitive: bool = False) -> Pattern[str]: ...
def keyword_assignment(keywords: Sequence[str], secret_regex: str) -> Pattern[str]: ...
def has_free_quantifier(pattern: str) -> bool: ...
```

#### Tasks

1. `unique_token()` com `\b` na frente e lookahead delimitador atrás.
2. `keyword_assignment()` com janelas limitadas e operador de atribuição.
3. `has_free_quantifier()` para o teste do D2.
4. Rejeitar prefixo iniciado por não-word em `unique_token`.

#### TDD

```python
# tests/unit/test_patterns.py
def test_unique_token_matches_the_value_alone():
    p = unique_token(r"AKIA[0-9A-Z]{16}")
    assert p.search("AKIAIOSFODNN7EXAMPLE")

def test_unique_token_matches_the_value_inside_an_assignment():
    # D5: é a forma em que o segredo aparece de verdade
    p = unique_token(r"AKIA[0-9A-Z]{16}")
    assert p.search('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')

def test_unique_token_does_not_match_inside_a_longer_run():
    # caso negativo: delimitação
    p = unique_token(r"AKIA[0-9A-Z]{16}")
    assert p.search("XAKIAIOSFODNN7EXAMPLEX") is None

def test_unique_token_finds_two_adjacent_secrets():
    # a divergência consciente: lookahead em vez de consumir o delimitador
    p = unique_token(r"AKIA[0-9A-Z]{16}")
    texto = "AKIAIOSFODNN7EXAMPLE AKIA1234567890ABCDEF"
    assert len(p.findall(texto)) == 2

def test_unique_token_rejects_a_prefix_starting_with_non_word():
    # caso negativo: geraria padrão que nunca casa
    with pytest.raises(ValueError):
        unique_token(r"-abc[0-9]{5}")

def test_keyword_assignment_requires_the_keyword_nearby(): ...
def test_keyword_assignment_requires_an_assignment_operator(): ...

@pytest.mark.parametrize("livre", [r"a*", r"a+", r"a{2,}", r"(ab)*"])
def test_has_free_quantifier_detects_unbounded(livre):
    assert has_free_quantifier(livre) is True

@pytest.mark.parametrize("limitado", [r"a{0,50}?", r"a{1,3}", r"[A-Z]{16}", r"a\*"])
def test_has_free_quantifier_accepts_bounded_and_escaped(limitado):
    # `a\*` é asterisco literal, não quantificador — não pode acusar
    assert has_free_quantifier(limitado) is False
```

#### Acceptance Criteria

- [ ] `unique_token` casa o valor sozinho **e** dentro de `AWS_KEY = "…"`
- [ ] `unique_token` **não** casa dentro de cadeia maior (`XAKIA…X`)
- [ ] `p.findall` encontra **2** segredos adjacentes separados por espaço
- [ ] `unique_token` raises `ValueError` para prefixo iniciado por não-word
- [ ] `keyword_assignment` returns padrão que casa `token = "abc123"` e **não** casa `token abc123` (sem operador)
- [ ] `has_free_quantifier` returns `True` para `a*`, `a+`, `a{2,}`; `False` para `a{0,50}?`, `a\*`

#### DoD

- [ ] Todos os testes de T1.1 passam
- [ ] `grep '^import\|^from' src/gitsafety/patterns.py` outputs apenas `re` e `typing`
- [ ] Commit atômico referenciando T1.1

---

### T1.2 — `catalog.py`: as regras

#### Objective

≥ 40 padrões cobrindo as 6 categorias do README, cada um com tps e fps.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `catalog.py` com as regras e reapontar `BUILTIN_RULES`.
**Raciocínio:** é o entregável do milestone. Vem depois dos construtores porque cada regra
os usa; escrever regras antes significaria reescrevê-las quando o construtor mudasse.

#### Evidence

- `knowledge-base/references/gitleaks/cmd/generate/config/main.go:30` — lista literal única
- ADRs D4 e D5
- `README.md § O que ele detecta` — as 6 categorias que precisam ser cobertas

#### Files to edit

- `src/gitsafety/catalog.py` (NOVO)
- `src/gitsafety/rules.py` (editar — `Rule` ganha `true_positives`/`false_positives`; `BUILTIN_RULES` passa a vir do catálogo)

#### Deep file dependency analysis

`catalog.py` importa `patterns.py` e `rules.py`. `rules.py` mantém `Rule` e reexporta
`BUILTIN_RULES` para não quebrar `scanner.py` e `staged.py`, que já o importam de lá.

#### Deep Dives

Ampliar `Rule` com `true_positives` e `false_positives` é mudança de dataclass congelada
usada por dois módulos. Como os campos novos têm default (tupla vazia), a construção
existente segue válida — mas o teste do D3 deve **exigir** que sejam não-vazios para toda
regra do catálogo, senão o default vira a porta pela qual uma regra entra sem exemplos.

As chaves de exemplo das documentações oficiais (AWS `AKIAIOSFODNN7EXAMPLE`, Stripe
`sk_test_…`) aparecem em código real e em tutoriais. Elas entram como **fps das próprias
regras** onde for possível distingui-las; onde não for, a limitação é declarada e o `allow:`
do M3 cobre.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: Pattern[str]
    true_positives: tuple[str, ...] = ()
    false_positives: tuple[str, ...] = ()

CLOUD_RULES: tuple[Rule, ...] = (...)
VCS_RULES: tuple[Rule, ...] = (...)
AI_RULES: tuple[Rule, ...] = (...)
SAAS_RULES: tuple[Rule, ...] = (...)
KEY_RULES: tuple[Rule, ...] = (...)
DB_RULES: tuple[Rule, ...] = (...)
BUILTIN_RULES = CLOUD_RULES + VCS_RULES + AI_RULES + SAAS_RULES + KEY_RULES + DB_RULES
```

#### Tasks

1. Ampliar `Rule` com os dois campos de exemplo.
2. Escrever as regras por categoria, cada uma com ≥ 2 tps em contexto e ≥ 2 fps.
3. Compor `BUILTIN_RULES` e reexportar de `rules.py`.

#### TDD

Os testes deste task são os de T2.1 (percorrem o catálogo). O RED aqui é `ImportError`.

#### Acceptance Criteria

- [ ] `len(BUILTIN_RULES) >= 40`
- [ ] `assert all(len(g) >= 1 for g in (CLOUD_RULES, VCS_RULES, AI_RULES, SAAS_RULES, KEY_RULES, DB_RULES))`
- [ ] `assert rule.true_positives and rule.false_positives` para toda regra do catálogo
- [ ] `from gitsafety.rules import BUILTIN_RULES` continua funcionando — `pytest` de `scanner` e `staged` verde sem edição
- [ ] `pytest tests/unit/test_rules.py` returns exit `0` sem edição dos testes do M0

#### DoD

- [ ] Todos os testes de T1.2 e T2.1 passam
- [ ] `git diff --name-only` **não** contains `scanner.py` nem `staged.py`
- [ ] Commit atômico referenciando T1.2

---

## Phase 2: Provas mecânicas

### T2.1 — Teste do catálogo: os dois lados de cada regra

#### Objective

Nenhuma regra existe sem ter seus acertos e não-acertos verificados.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** teste parametrizado sobre `BUILTIN_RULES`.
**Raciocínio:** implementa o ADR D3. Com 40 regras, teste escrito à mão por regra garante
que alguém esquecerá a 41ª — e o esquecimento é silencioso, que é o pior tipo.

#### Evidence

- `knowledge-base/references/gitleaks/cmd/generate/config/utils/validate.go:16-39`
- ADR D3

#### Files to edit

- `tests/unit/test_catalog.py` (NOVO)

#### Deep file dependency analysis

Importa `BUILTIN_RULES`. Não é importado por produção.

#### Deep Dives

O `parametrize` precisa usar o `id` da regra como identificador do caso, senão a saída de
falha diz "caso 27" e ninguém sabe qual regra quebrou. `pytest.param(rule, id=rule.id)`
resolve.

Um fp que casa **outra** regra do catálogo não é falha da regra sob teste — mas é sinal de
sobreposição entre regras, que vale reportar. Este teste verifica a regra isolada; a
sobreposição é verificada separadamente.

#### Pseudo-code / Signatures

```python
CASOS = [pytest.param(r, id=r.id) for r in BUILTIN_RULES]
```

#### Tasks

1. Teste de tps: toda regra casa todos os seus.
2. Teste de fps: nenhuma regra casa qualquer um dos seus.
3. Teste de exemplos obrigatórios: nenhuma regra tem listas vazias.
4. Teste de ids únicos.

#### TDD

```python
# tests/unit/test_catalog.py
@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_matches_all_of_its_true_positives(rule):
    for tp in rule.true_positives:
        assert rule.pattern.search(tp), f"{rule.id} não casou: {tp!r}"

@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_rejects_all_of_its_false_positives(rule):
    for fp in rule.false_positives:
        assert rule.pattern.search(fp) is None, f"{rule.id} casou indevidamente: {fp!r}"

@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_carries_examples_on_both_sides(rule):
    # sem isto, o default de tupla vazia deixa uma regra entrar sem exemplos
    assert rule.true_positives and rule.false_positives

def test_catalog_has_at_least_forty_rules():
    assert len(BUILTIN_RULES) >= 40

def test_rule_ids_are_unique(): ...
def test_every_readme_category_is_covered(): ...
```

#### Acceptance Criteria

- [ ] Todo tp de toda regra casa — `assert rule.pattern.search(tp)`
- [ ] Nenhum fp de nenhuma regra casa — `assert ... is None`
- [ ] Nenhuma regra tem lista de exemplos vazia
- [ ] `len(BUILTIN_RULES) >= 40`
- [ ] `assert len(ids) == len(set(ids))` sobre `[r.id for r in BUILTIN_RULES]`
- [ ] A saída de falha contains o `rule.id` — obtido com `pytest.param(rule, id=rule.id)`

#### DoD

- [ ] Todos os testes de T2.1 passam
- [ ] Commit atômico referenciando T2.1

---

### T2.2 — Quantificador livre e teto de tempo

#### Objective

Provar que nenhuma regra pode pendurar o `git commit`.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** teste mecânico de quantificador (D2) e teste de tempo com entradas adversariais (D6).
**Raciocínio:** desde o M1 a regex roda dentro do `git commit`. Regex patológica não é
lentidão — é o commit do usuário pendurado sem explicação. O gitleaks não precisa desta
prova porque RE2 não faz backtracking; nós precisamos.

#### Evidence

- `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:14-31` — quantificadores limitados
- ADRs D2 e D6
- Unresolved Question Q1 — origem do teto de 0,05 s

#### Files to edit

- `tests/unit/test_catalog.py` (editar)

#### Deep file dependency analysis

Usa `has_free_quantifier` de T1.1 e `BUILTIN_RULES` de T1.2.

#### Deep Dives

As entradas adversariais precisam **quase** casar: uma cadeia que satisfaz o prefixo e
falha no fim é o que força o motor a voltar atrás. Para `AKIA[0-9A-Z]{16}`, a entrada ruim
é `"AKIA" + "A" * 200` — prefixo certo, comprimento errado, repetido.

Medir tempo em teste é fonte clássica de flakiness. Mitigação: teto folgado (0,05 s contra
um custo esperado na casa dos microssegundos), e a asserção é sobre **ordem de grandeza**,
não sobre precisão.

#### Pseudo-code / Signatures

```python
ADVERSARIAL = ["A" * 500, "AKIA" + "A" * 500, "a=" + "x" * 500, ...]
```

#### Tasks

1. Teste de quantificador livre sobre todos os padrões.
2. Corpus adversarial.
3. Teste de tempo por regra.

#### TDD

```python
@pytest.mark.parametrize("rule", CASOS)
def test_no_rule_uses_a_free_quantifier(rule):
    assert not has_free_quantifier(rule.pattern.pattern), rule.id

@pytest.mark.parametrize("rule", CASOS)
def test_no_rule_takes_too_long_on_adversarial_input(rule):
    for entrada in ADVERSARIAL:
        inicio = time.perf_counter()
        rule.pattern.search(entrada)
        assert time.perf_counter() - inicio < 0.05, f"{rule.id} lenta em {entrada[:20]!r}"
```

#### Acceptance Criteria

- [ ] `has_free_quantifier` returns `False` para **todo** padrão do catálogo
- [ ] Nenhuma regra excede `0.05` s em nenhuma entrada adversarial
- [ ] `ADVERSARIAL` contains `"AKIA" + "A" * 500` — prefixo certo, comprimento errado
- [ ] A mensagem de falha contains `rule.id` e os primeiros 20 caracteres da entrada

#### DoD

- [ ] Todos os testes de T2.2 passam
- [ ] Commit atômico referenciando T2.2

---

## Phase 3: Falso positivo e escala

### T3.1 — Corpus limpo e métrica de falso positivo

#### Objective

Provar que o catálogo não acusa em código legítimo.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** gerar corpus limpo por código e medir findings.
**Raciocínio:** é o DoD do `ROADMAP.md § M2` ("zero findings em repositório limpo") e a
métrica do `docs/PRD.md § 8`. Sem corpus nomeado, a métrica não é reprodutível, e métrica
não reprodutível não detecta regressão.

#### Evidence

- `ROADMAP.md § M2` DoD nº 3
- `docs/PRD.md § 8` — falso positivo como métrica de sucesso
- ADR D7

#### Files to edit

- `tests/fixtures/clean_corpus.py` (NOVO)
- `tests/functional/test_false_positive_rate.py` (NOVO)

#### Deep file dependency analysis

O corpus é gerado, não commitado como árvore — evita trazer licença de terceiro e mantém o
diff legível.

#### Deep Dives

O corpus precisa conter justamente o que **quase** parece segredo: hash SHA-256 (64 hex),
UUID v4, base64 de dados legítimos, chave pública SSH, e as chaves de exemplo das
documentações oficiais. Um corpus de código trivial não testaria nada.

Atenção ao paradoxo: se o corpus contém as chaves de exemplo das docs (que **são** o
formato real), as regras vão casá-las. Ou elas entram como fps das regras (e o catálogo as
ignora), ou o corpus as exclui e a limitação é declarada. Escolha: entram como fps onde
distinguível.

#### Pseudo-code / Signatures

```python
def build_clean_corpus(root: Path) -> int: ...   # devolve nº de arquivos
```

#### Tasks

1. Gerador de corpus com as formas de quase-acerto.
2. Teste de zero findings.
3. Registro do número no log de implementação.

#### TDD

```python
def test_clean_corpus_produces_zero_findings(tmp_path):
    build_clean_corpus(tmp_path)
    resultado = scan_path(tmp_path)
    assert resultado.findings == [], [f"{f.rule_id}: {f.secret}" for f in resultado.findings]

def test_clean_corpus_contains_near_miss_shapes(tmp_path):
    # um corpus trivial não provaria nada
    n = build_clean_corpus(tmp_path)
    conteudo = "".join(p.read_text() for p in tmp_path.rglob("*.py"))
    assert "sha256" in conteudo.lower() and "uuid" in conteudo.lower()
```

#### Acceptance Criteria

- [ ] `scan_path(corpus).findings == []` — zero findings
- [ ] `assert` que o corpus contains SHA-256 de 64 hex, UUID v4, base64 e `ssh-rsa AAAA…`
- [ ] O número de arquivos e `findings == []` registrados em `knowledge-base/implementations/m2-catalogo-de-padroes-implementation.md`
- [ ] A mensagem de falha contains `f"{f.rule_id}: {f.secret}"` de cada finding indevido

#### DoD

- [ ] Os dois testes passam
- [ ] Commit atômico referenciando T3.1

---

### T3.2 — Benchmark de escala: 1 regra → 40 regras

#### Objective

Medir o custo de multiplicar o catálogo por 40 e decidir, com dado, se o pré-filtro é
necessário.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** medir a varredura com 1, 10 e todas as regras.
**Raciocínio:** o M0 mediu 69.000 arquivos/s com **uma** regra. O motor aplica cada regra a
cada linha, então 40 regras poderiam custar 40×. Isso levaria o overhead do hook de 0,04 s
para perto de 1 s — o limite do `NFR-2`. É a Unresolved Question Q3 e o gargalo real deste
milestone: sem medir, o pré-filtro por palavra-chave é otimização especulativa; com o
dado, vira tarefa ou vira não-problema.

#### Evidence

- `knowledge-base/implementations/m0-esqueleto-cli-implementation.md` — 69.068 arquivos/s com 1 regra
- `knowledge-base/implementations/m1-hook-pre-commit-implementation.md` — overhead de 0,04 s
- `docs/PRD.md § NFR-2` — `< 1 s`
- Unresolved Question Q3

#### Files to edit

- `benchmarks/bench_catalog.py` (NOVO)
- `tests/functional/test_catalog_performance.py` (NOVO)

#### Deep file dependency analysis

Reusa `build_corpus` de `benchmarks/bench_scan.py` (M0) para que os números sejam
comparáveis com os daquele milestone.

#### Deep Dives

O que interessa é a **forma da curva**, não o valor absoluto: se o custo por regra for
constante, 40 regras custam 40× e o pré-filtro se justifica; se a travessia de arquivo
dominar, o número de regras quase não importa e o pré-filtro é YAGNI.

Comparar com o M0 exige o **mesmo corpus** — daí reusar o gerador em vez de escrever outro.

#### Pseudo-code / Signatures

```python
def measure_with_n_rules(root: Path, n_rules: int) -> dict[str, float]: ...
```

#### Tasks

1. Medição com 1, 10 e todas as regras sobre o corpus do M0.
2. Cálculo do custo marginal por regra.
3. Teste de orçamento comparando com o `NFR-2`.

#### TDD

```python
def test_full_catalog_stays_within_the_scan_budget(tmp_path):
    build_corpus(tmp_path, n_files=1000, secrets_every=100)
    m = measure_with_n_rules(tmp_path, n_rules=len(BUILTIN_RULES))
    assert m["total_s"] < 5.0, m      # mesmo orçamento do M0

def test_cost_per_rule_is_reported(tmp_path):
    # o número que decide sobre o pré-filtro
    build_corpus(tmp_path, n_files=200, secrets_every=50)
    m = measure_with_n_rules(tmp_path, n_rules=len(BUILTIN_RULES))
    assert m["ms_per_rule_per_1k_lines"] > 0
```

#### Acceptance Criteria

- [ ] `python benchmarks/bench_catalog.py` outputs `total_s` para 1, 10 e `len(BUILTIN_RULES)` regras
- [ ] `assert m["total_s"] < 5.0` com o catálogo completo sobre 1.000 arquivos
- [ ] `ms_per_rule_per_1k_lines` é calculado e registrado no log de implementação
- [ ] O log declara `pré-filtro: justificado` ou `pré-filtro: desnecessário`, com o número que sustenta

#### DoD

- [ ] Os dois testes passam
- [ ] Números registrados com hardware e método
- [ ] Decisão sobre o pré-filtro tomada com dado, não com suposição
- [ ] Commit atômico referenciando T3.2

---

## Coverage Matrix

| # | Requisito (origem) | Task(s) | Como é resolvido |
|---|---|---|---|
| 1 | ≥ 40 padrões nas 6 categorias (ROADMAP M2 DoD 1) | T1.2 | `catalog.py`; teste de contagem e de cobertura por categoria |
| 2 | Cada padrão com teste de acerto e não-acerto (ROADMAP M2 DoD 1) | T2.1 | Parametrizado sobre `BUILTIN_RULES`, os dois lados |
| 3 | Segredo mascarado; `--show-secrets` revela (ROADMAP M2 DoD 2) | T2.1 | Entregue no M0, mas o M2 multiplica por 40 os `rule_id` que passam pelo renderizador: T2.1 acrescenta teste de **regressão** verificando que um finding de cada categoria nova sai mascarado |
| 4 | Corpus limpo → zero findings (ROADMAP M2 DoD 3) | T3.1 | Corpus gerado com formas de quase-acerto |
| 5 | Padrões em arquivo de dados versionado (ROADMAP M2 DoD 4) | T1.2 | `catalog.py` com tupla literal única (D4) |
| 6 | Nenhum padrão largo demais (Risco M2 nº 1) | T1.1, T2.1, T3.1 | Delimitação por construção + fps obrigatórios + corpus |
| 7 | Nenhuma regex patológica (Risco M2 nº 2) | T2.2 | Análise estática (D2) **e** medição de tempo (D6) |
| 8 | Sem dependência de runtime nova (PRD NFR-1) | T1.1 | Só `re` da stdlib |
| 9 | Custo de 40 regras medido (gargalo do milestone) | T3.2 | Escala 1 → 10 → 40 regras, custo marginal calculado |
| 10 | Decisão sobre pré-filtro com dado (Unresolved Q3) | T3.2 | Declarada no log de implementação |
| 11 | Exemplos em contexto de código (D5) | T1.2, T2.1 | tps incluem atribuição e variável de ambiente |
| 12 | `scanner`/`staged` inalterados (milestone aditivo) | T1.2 | `BUILTIN_RULES` segue importável de `gitsafety.rules` |
| 13 | Chaves de exemplo de documentação não acusam | T1.2, T3.1 | Entram como fps das regras; corpus as contains |
| 14 | Falha de teste nomeia a regra | T2.1, T2.2 | `pytest.param(..., id=rule.id)` |

**Cobertura: 14/14 requisitos mapeados (100%)**

## Global Definition of Done

- [ ] Os 4 itens de DoD do `ROADMAP.md § M2` verificados por teste automatizado
- [ ] Toda regra com exemplos nos dois lados (`rules/testing.md § 4.1`)
- [ ] Nenhum quantificador livre no catálogo, verificado mecanicamente
- [ ] Nenhuma regra excede o teto de tempo em entrada adversarial
- [ ] Corpus limpo produz zero findings
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] `/code-quality` com veredito ∈ {PASS, PASS_WITH_CAVEATS, FAIL_SOFT com ADR}
- [ ] Benchmark de escala executado; decisão sobre pré-filtro registrada
- [ ] README com a tabela de categorias refletindo o que existe

## Failure scenarios

O M2 não acrescenta fronteira externa — é domínio puro sobre o que M0 e M1 já construíram.
Os modos de falha são de **conteúdo do catálogo**, não de I/O:

| Recurso | Modo de falha | Como o teste reproduz | Comportamento esperado |
|---|---|---|---|
| Regra do catálogo | Padrão não casa seu próprio exemplo | Regra com tp que o padrão não alcança | Teste do catálogo falha nomeando a regra |
| Regra do catálogo | Padrão casa seu próprio contra-exemplo | Regra com fp que o padrão alcança | Teste do catálogo falha nomeando regra e exemplo |
| Regra do catálogo | Quantificador livre | Padrão com `.*` | `has_free_quantifier` acusa; teste falha |
| Regra do catálogo | Degradação em entrada adversarial | `"AKIA" + "A" * 500` | Teste de tempo falha nomeando regra e entrada |
| Catálogo | Regra sem exemplos | Regra com listas vazias | Teste de exemplos obrigatórios falha |
| Catálogo | Id duplicado | Duas regras com o mesmo id | Teste de unicidade falha |
| Código legítimo | Falso positivo agregado | Corpus com hash, UUID, base64 | Zero findings; falha lista regra e valor |

**(sem I/O externo — o M2 é domínio puro; sistema de arquivos e git já foram cobertos em M0 e M1)**

## Concurrency tests

**(none — single-threaded)** — o M2 acrescenta dados e construtores puros. Nenhuma thread,
async, lock ou estado compartilhado mutável. `re.Pattern` compilado é imutável e seguro
para uso concorrente, mas não usamos concorrência.

---

## Final Phase: Integration Validation (MANDATORY)

### Execution

```bash
.venv/bin/pytest -q                                      # suíte inteira
.venv/bin/python -c "from gitsafety.rules import BUILTIN_RULES; print(len(BUILTIN_RULES))"
cd $(mktemp -d) && printf 'k="AKIAIOSFODNN7EXAMPLE"\ng="ghp_0123456789abcdefghijklmnopqrstuvwx"\n' > s.py
gitsafety scan .; echo "exit=$?"                          # espera: 2 findings, exit 1
.venv/bin/python benchmarks/bench_catalog.py             # escala 1 -> 40 regras
```

### Acceptance Criteria

- [ ] `pytest -q` returns exit code `0`
- [ ] `len(BUILTIN_RULES) >= 40`
- [ ] Um arquivo com duas credenciais de provedores diferentes produz **2** findings
- [ ] `echo $?` outputs `1` após o scan com credenciais
- [ ] Benchmark outputs tempo com 1, 10 e todas as regras

### If Validation Fails

Voltar ao task pelo Coverage Matrix. Não seguir para `/code-quality` com item falhando —
`cycle-implement § Stop conditions` proíbe a promessa de conclusão em estado parcial.
