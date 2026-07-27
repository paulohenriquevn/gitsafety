# Blueprint: Catálogo de padrões de credencial (M2)

**Slug:** `m2-catalogo-de-padroes`
**Plano de origem:** `knowledge-base/discoveries/plans/m2-catalogo-de-padroes-plan.md` (v1.0)
**Data:** 2026-07-27
**Questões:** 7 respondidas, 0 BLOCKED

> **Ressalva de amostragem (D2 do plano).** As 131 regras do gitleaks não foram lidas
> exaustivamente. Foram lidos integralmente os `utils` (onde vive o molde) e `main.go`,
> mais uma amostra dirigida de regras. Conclusões sobre "o conjunto de regras" valem para
> o molde; casos fora do molde podem existir e não foram inventariados.
>
> **Ressalva de motor (D3 do plano).** Go usa **RE2**, que não tem backtracking por
> construção. Python usa `re`, que tem. **Uma regex segura no gitleaks pode ser
> patológica em Python.** Toda recomendação abaixo carrega essa ressalva.

## Context

O `ROADMAP.md § M2` pede ≥ 40 padrões e nomeia dois riscos que escalam com o catálogo:
padrão largo demais (falso positivo) e regex patológica (commit pendurado, desde que o M1
pôs o motor dentro do `git commit`). Esta descoberta procura a disciplina que permite a um
projeto manter **131 regras** sem cair em nenhum dos dois.

## Objective

Travar quatro decisões antes do `/to-plan` do M2: o molde de construção dos padrões, o
mecanismo que impede padrão largo e regex patológica, a organização do catálogo em escala,
e a forma de validar cada regra contra os próprios exemplos.

## Coverage Corner 1 — Integration Tests

### Q4 — Como cada regra é validada contra seus próprios exemplos

`knowledge-base/references/gitleaks/cmd/generate/config/utils/validate.go:16-39` — a
função inteira:

```go
func Validate(rule config.Rule, truePositives []string, falsePositives []string) *config.Rule {
	r := &rule
	d := createSingleRuleDetector(r)
	for _, tp := range truePositives {
		if len(d.DetectString(tp)) < 1 {
			logging.Fatal()....Msg("Failed to Validate. True positive was not detected by regex.")
		}
	}
	for _, fp := range falsePositives {
		findings := d.DetectString(fp)
		if len(findings) != 0 {
			logging.Fatal()....Msg("Failed to Validate. False positive was detected by regex.")
		}
	}
	return r
}
```

Três coisas importam, e a terceira é a que muda o projeto:

1. **Os dois lados são verificados** — o true positive precisa casar, e o false positive
   precisa **não** casar. Não é "testa se detecta"; é "testa se detecta o certo e ignora o
   errado".
2. **A validação usa o detector de verdade** (`createSingleRuleDetector`, `:69`), não uma
   chamada direta de regex. Prova a regra no motor em que ela vai rodar.
3. **`logging.Fatal()` — o processo morre.** A validação não roda num teste separado que
   alguém pode pular: roda na **construção da regra**. Uma regra que falha seus próprios
   exemplos **não chega a existir**, e o catálogo inteiro não é gerado.

Esse terceiro ponto é a diferença entre "temos testes de regra" e "é impossível ter uma
regra sem teste". `ValidateWithPaths` (`:41`) é a variante para regras baseadas em caminho.

### Q5 — Organização de suíte com muitos casos

`knowledge-base/references/ggshield/tests/unit/` — a suíte é dividida por módulo espelhando
a estrutura do pacote, e os casos em volume ficam em `pytest.mark.parametrize`.

**[confiança reduzida]** — esta questão recebeu o menor orçamento (D1: ggshield 0,5h) e foi
respondida por inspeção de estrutura, não por leitura profunda dos arquivos. A conclusão é
suficiente para o M2 (parametrize por regra, arquivo por família) mas não é um levantamento
exaustivo do estilo de teste do ggshield.

## Coverage Corner 2 — Dependencies

### Q6 — O catálogo adiciona dependência de runtime?

`knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:7-12`:

```go
import (
	"fmt"
	"strings"

	"github.com/zricethezav/gitleaks/v8/regexp"
)
```

Dois pacotes da biblioteca padrão de Go e **um pacote interno do próprio gitleaks** — que é
um wrapper sobre o `regexp` padrão, não uma dependência de terceiro.

**Veredito: o M2 não adiciona dependência de runtime.** Construir padrões é montagem de
string e compilação de regex; `re` e f-strings da stdlib cobrem tudo. O `dependencies = []`
do `pyproject.toml` permanece.

## Coverage Corner 3 — Tools

### Q7 — Como o catálogo é gerado, versionado e revisado

`knowledge-base/references/gitleaks/cmd/generate/config/main.go`:

| Citação | Conteúdo |
|---|---|
| `:18` | `//go:generate go run $GOFILE ../../../config/gitleaks.toml` |
| `:20` | `func main()` |
| `:30` | `rules.AdafruitAPIKey(),` — uma entrada por regra, numa lista literal |
| `:286` | `f, err := os.Create(gitleaksConfigPath)` |
| `:288` | `logging.Fatal()...Msg("Failed to create rules.toml")` |

O fluxo é **código → artefato gerado**: as regras são funções Go, `main.go` as reúne numa
lista e escreve `config/gitleaks.toml`. O TOML é **artefato derivado**, não fonte da
verdade.

Para a revisão, isso significa que uma regra nova aparece no diff em dois lugares: o
arquivo da regra (com seus exemplos) e o TOML gerado. O revisor lê o primeiro; o segundo é
consequência.

**Tradução para o nosso escopo:** nós não geramos TOML (formato cortado no
`docs/PRD.md § 10`), então a etapa de geração não se aplica. O que transfere é a **lista
literal única** (`main.go:30`) como ponto de registro: uma regra que não está na lista não
existe, e a lista é o lugar onde o revisor vê o catálogo inteiro.

## Coverage Corner 4 — Techniques

### Q1 — O molde de construção de regex

Há **duas famílias**, e a distinção entre elas é a decisão de projeto mais importante deste
milestone.

**Família 1 — token único** (`generate.go:69-78`), para segredos com prefixo próprio:

```go
func GenerateUniqueTokenRegex(secretRegex string, isCaseInsensitive bool) *regexp.Regexp {
	if isCaseInsensitive { sb.WriteString(caseInsensitive) }
	sb.WriteString(secretPrefixUnique)   // \b(
	sb.WriteString(secretRegex)
	sb.WriteString(secretSuffix)         // )(?:[\x60'"\s;]|\\[nr]|$)
	return regexp.MustCompile(sb.String())
}
```

É a família do `AKIA…`, `ghp_…`, `sk-ant-…`: o próprio valor é reconhecível, então basta
**delimitar** (`\b`) e verificar o que vem depois. Não precisa de palavra-chave por perto.

**Família 2 — semi-genérica** (`generate.go:34-46`), para segredos sem formato próprio:

```go
func GenerateSemiGenericRegex(identifiers []string, secretRegex string, isCaseInsensitive bool) *regexp.Regexp {
	sb.WriteString(identifierCaseInsensitivePrefix)   // [\w.-]{0,50}?(?i:
	writeIdentifiers(&sb, identifiers)                 // adafruit|...
	sb.WriteString(identifierCaseInsensitiveSuffix)    // )
	sb.WriteString(operator)                           // (?:=|>|:{1,3}=|\|\||:|=>|\?=|,)
	...
}
```

É a família de "senha", "token", "api_key": o valor sozinho não é reconhecível, então a
regra exige uma **palavra-chave próxima** seguida de um **operador de atribuição**.

### Q2 — Como o catálogo evita padrão largo e regex patológica

As constantes de `generate.go:14-31`, literais:

| Constante | Valor | Papel |
|---|---|---|
| `caseInsensitive` | `` `(?i)` `` | |
| `identifierCaseInsensitivePrefix` | `` `[\w.-]{0,50}?(?i:` `` | Janela **limitada a 50** antes da palavra-chave, com quantificador **preguiçoso** |
| `identifierCaseInsensitiveSuffix` | `` `)` `` | |
| `identifierSuffix` | `` `)(?:[ \t\w.-]{0,20})[\s'"]{0,3}` `` | Janela **limitada a 20** e a **3** entre palavra-chave e valor |
| `operator` | `` `(?:=\|>\|:{1,3}=\|\|\|\|:\|=>\|\?=\|,)` `` | Exige **operador de atribuição** entre chave e valor |
| `secretPrefixUnique` | `` `\b(` `` | **Delimitador de palavra** — o mecanismo antifalso-positivo da família 1 |
| `secretPrefix` | `` `[\x60'"\s=]{0,5}(` `` | Janela **limitada a 5** |
| `secretSuffix` | `` `)(?:[\x60'"\s;]\|\\[nr]\|$)` `` | Exige **delimitador depois** do valor: aspas, espaço, `;`, `\n`, `\r` ou fim |

**Duas disciplinas, uma para cada risco do M2:**

**Contra padrão largo demais (Risco nº 1):** o valor nunca é procurado sozinho. Ou ele tem
prefixo próprio e é delimitado por `\b` (família 1), ou precisa de palavra-chave **mais**
operador de atribuição **mais** delimitador depois (família 2). Três âncoras. Um valor
alfanumérico solto no meio de um texto não casa.

**Contra regex patológica (Risco nº 2):** **todo quantificador é limitado.** `{0,50}`,
`{0,20}`, `{0,5}`, `{0,3}`, `{1,3}` — não há um único `*` ou `+` sem teto no molde. E o
`{0,50}?` é **preguiçoso**, o que reduz o espaço de busca antes mesmo do teto.

**A ressalva que muda tudo para nós (D3):** o gitleaks roda em **RE2**, que não tem
backtracking — para eles, a disciplina de quantificador limitado é higiene, não
necessidade. Em Python, com `re`, ela é **necessidade**. Copiar o molde nos dá a disciplina
certa; copiar sem entender por quê nos deixaria sem defesa quando alguém acrescentar um
`.*` "só desta vez".

### Q3 — Como 131 regras são organizadas

- **Um arquivo por regra** em `cmd/generate/config/rules/` — `adafruit.go`, `age.go`,
  `airtable.go`… Encontrar a regra do provedor X é adivinhar o nome do arquivo.
- **Uma função por regra**, devolvendo `*config.Rule`, com os exemplos dentro
  (`Validate(r, tps, fps)`).
- **Uma lista literal única** em `main.go:30+` registrando cada regra: `rules.AdafruitAPIKey(),`.

O registro explícito é o que impede regra órfã: escrever o arquivo não basta, é preciso
entrar na lista. E a lista é onde o revisor vê o catálogo inteiro num só lugar.

`GenerateSampleSecrets` (`generate.go:85`) gera os true positives a partir de um mapa de
templates por linguagem (`:112-113`): `string {i}Token = "{s}";` para C#,
`var {i}Token string = "{s}"` para Go. Assim cada regra é testada contra a forma que o
segredo teria em código real, não contra a string nua.

## Cross-cutting Comparison

| Dimensão | gitleaks | Decisão para o M2 |
|---|---|---|
| Famílias de padrão | token único vs semi-genérico (`generate.go:69`, `:34`) | **Adotar as duas**, com o M2 focando na família 1 |
| Delimitação (família 1) | `\b(` + sufixo delimitador | Adotar literalmente |
| Delimitação (família 2) | palavra-chave + operador + delimitador | Adotar; é o que o README já oferece como snippet opcional |
| Quantificadores | **todos limitados**; `{0,50}?` preguiçoso | **Adotar como regra inegociável** — em Python é necessidade, não higiene |
| Organização | arquivo por regra + lista literal única | Adaptar: módulo de dados único com lista literal (temos 40, não 131) |
| Validação | `logging.Fatal` na **construção** | Adaptar: teste que percorre o catálogo inteiro e falha se qualquer regra falhar os próprios exemplos |
| True positives | gerados por template de linguagem (`:112`) | Adotar a ideia: testar na forma que o segredo tem em código |
| Artefato gerado | TOML derivado do código | **Não se aplica** — TOML é não-objetivo (`PRD § 10`) |
| Motor de regex | RE2, sem backtracking | **`re` do Python tem backtracking** — exige teste de tempo próprio |

## ADRs

### D1 — Duas famílias de padrão, e o M2 privilegia a de token único

**Decisão:** o catálogo do M2 é construído em duas famílias — **token único** (valor com
prefixo reconhecível, delimitado por `\b`) e **semi-genérica** (palavra-chave + operador +
valor). A esmagadora maioria dos ≥ 40 padrões é da primeira; a segunda fica para o snippet
opcional que o README já documenta.

**Rationale:** `generate.go:69-78` e `:34-46` mostram a distinção. A família 1 é
intrinsecamente segura contra falso positivo porque o valor carrega a própria identidade
(`AKIA` + 16 maiúsculas não é outra coisa). A família 2 depende de contexto e é onde o
falso positivo mora — o `docs/PRD.md § 4` já decidiu não ligá-la por padrão.

**Alternativas consideradas:** (a) só família 1 — rejeitada, deixaria de fora as strings de
conexão de banco, que o README promete e que precisam de contexto; (b) só família 2 —
rejeitada, exigiria palavra-chave perto de um `AKIA…`, gerando falso **negativo** no caso
mais comum; (c) uma terceira família por entropia — rejeitada, é não-objetivo declarado
(`PRD § 5 NG4`).

**Consequências:** o `Rule` do M0 precisa acomodar as duas formas. Como ambas são apenas um
`re.Pattern` compilado, a dataclass não muda — muda o **construtor** que monta o padrão.

### D2 — Todo quantificador é limitado, sem exceção

**Decisão:** nenhum padrão do catálogo usa `*`, `+` ou `{n,}` sem teto. Todo quantificador
tem limite superior explícito, e a janela de contexto usa quantificador preguiçoso.

**Rationale:** é a disciplina literal de `generate.go:14-31` — `{0,50}?`, `{0,20}`,
`{0,5}`, `{0,3}`, `{1,3}`, sem um único quantificador livre. E aqui a diferença de motor é
decisiva: no RE2 do gitleaks isso é higiene, porque RE2 não faz backtracking. No `re` do
Python é **defesa necessária** — um `.*` aninhado num grupo alternado produz explosão
exponencial, e desde o M1 o motor roda dentro do `git commit`. Regex patológica não é
lentidão: é o commit do usuário pendurado.

**Alternativas consideradas:** (a) permitir quantificador livre e cobrir com timeout —
rejeitada, timeout no meio de um hook deixa o usuário sem resposta clara e mascara o
defeito em vez de impedi-lo; (b) migrar para uma engine sem backtracking (`re2` do PyPI) —
rejeitada, gastaria a única dependência autorizada (`PRD § NFR-1`), reservada ao YAML do
M3; (c) confiar na revisão humana — rejeitada, é exatamente o tipo de defeito que passa em
revisão e aparece em produção.

**Consequências:** um teste do catálogo precisa **verificar mecanicamente** a ausência de
quantificador livre, além do teste de tempo. Padrões de terceiros (o `rules:` do YAML no
M3) não terão essa garantia — é um risco a declarar lá.

### D3 — Validação percorre o catálogo inteiro e falha se qualquer regra falhar

**Decisão:** um teste percorre **todas** as regras do catálogo e, para cada uma, verifica
que todos os seus true positives casam e que nenhum dos seus false positives casa. Os
exemplos vivem junto da regra.

**Rationale:** `validate.go:16-39` faz exatamente isso, e o `logging.Fatal()` garante que
uma regra quebrada não chegue a existir. Não podemos matar o processo na importação de um
módulo — seria hostil —, mas podemos tornar impossível uma regra chegar ao `main` sem ter
seus dois lados verificados: o teste que percorre o catálogo falha, e o catálogo não passa
no CI.

**Alternativas consideradas:** (a) um teste por regra, escrito à mão — rejeitada, com 40
regras alguém esquece de escrever o teste da 41ª, e o esquecimento é silencioso; (b)
validar na importação com `assert` — rejeitada, `assert` some com `python -O` e a
validação viraria opcional sem ninguém perceber; (c) validar só true positives —
rejeitada, é metade do trabalho e justamente a metade que não protege contra o Risco nº 1.

**Consequências:** acrescentar regra sem exemplos faz o teste do catálogo falhar por
ausência, não passar por omissão. É o comportamento desejado.

### D4 — Catálogo como módulo de dados com lista literal única

**Decisão:** todas as regras num módulo de dados, registradas numa tupla literal única
(`BUILTIN_RULES`), agrupadas por categoria com comentário.

**Rationale:** o gitleaks usa arquivo-por-regra + lista literal em `main.go:30`. O
arquivo-por-regra paga por si com 131 regras; com 40, 131 arquivos seriam cerimônia — o
`rules/parsimony-ladder.md` rung 5 diz para não criar estrutura que o volume não justifica.
O que **transfere** é a **lista literal única**: uma regra que não está na tupla não
existe, e a tupla é onde o revisor vê o catálogo inteiro.

**Alternativas consideradas:** (a) um arquivo por regra — cerimônia desproporcional a 40
regras; reavaliar se o catálogo passar de ~100; (b) carregar de um YAML/JSON de dados —
rejeitada, o padrão precisa ser compilado e validado, e um arquivo de dados adia a falha
para o runtime; (c) descoberta automática por introspecção do módulo — rejeitada, remove o
ponto único onde o revisor vê o catálogo, que é justamente o valor da lista.

**Consequências:** o módulo de regras fica grande. Aceitável para dados; a lógica continua
fora dele.

### D5 — True positives na forma que o segredo tem em código real

**Decisão:** os exemplos de acerto de cada regra incluem o segredo **em contexto de
código** — atribuição, variável de ambiente, JSON —, não apenas o valor nu.

**Rationale:** `GenerateSampleSecrets` (`generate.go:85`) monta os exemplos a partir de um
mapa de templates por linguagem (`:112-113`). Um padrão que casa `AKIAIOSFODNN7EXAMPLE`
mas falha em `AWS_KEY="AKIAIOSFODNN7EXAMPLE"` passaria num teste com valor nu e falharia no
uso real — porque o `secretSuffix` exige delimitador depois, e a aspa é justamente esse
delimitador.

**Alternativas consideradas:** (a) só o valor nu — testa a regex, não a regra; (b) gerar os
contextos por template como o gitleaks — bom, mas o M0 já provou o padrão de `parametrize`
e um gerador seria abstração para um caso (`parsimony-ladder.md` rung 1).

**Consequências:** cada regra carrega mais exemplos, e o arquivo de testes cresce. É o
preço de testar a regra em vez do regex.

## Recommendations

1. **Adotar a família de token único como base do catálogo** (D1) — `\b` na frente,
   delimitador atrás. É onde estão AWS, GitHub, OpenAI, Stripe, Slack.
2. **Nenhum quantificador livre, verificado por teste mecânico** (D2). Em Python isso é
   defesa, não estilo, porque desde o M1 a regex roda dentro do `git commit`.
3. **Teste que percorre o catálogo inteiro** verificando os dois lados de cada regra (D3).
   Regra sem exemplos falha por ausência.
4. **Tupla literal única como registro** (D4) — o revisor vê o catálogo num lugar só.
5. **Exemplos em contexto de código**, não valor nu (D5) — o `secretSuffix` só é exercido
   assim.
6. **Teste de tempo por regra**, além do teste de quantificador: a análise estática não
   pega tudo, e é a única prova de que nenhuma regra pendura o commit.
7. **Medir falso positivo contra um corpus limpo real** e registrar o número — o
   `ROADMAP.md § M2` pede "zero findings em repositório limpo de referência", e sem um
   corpus nomeado a métrica não é reprodutível.

## Blocked questions

Nenhuma. Q5 foi respondida com **[confiança reduzida]** — recebeu o menor orçamento e foi
resolvida por inspeção de estrutura, não por leitura profunda. A conclusão basta para o M2,
mas não é levantamento exaustivo do estilo de teste do ggshield.
