# Blueprint: Configuração em YAML e regex vinda do usuário (M3)

**Slug:** `m3-config-yaml`
**Plano de origem:** `knowledge-base/discoveries/plans/m3-config-yaml-plan.md` (v1.0)
**Data:** 2026-07-27
**Questões:** 6 respondidas, 0 BLOCKED

> **Limitação herdada.** `detect-secrets`, `ripsecrets` e `secretlint` seguem ilegíveis
> pelo deny-glob `Read(**/*secret*)`, como declarado desde o M0.

## Context

O `ROADMAP.md § M3` acrescenta a config de três chaves e nomeia dois riscos. O segundo é
o que distingue o milestone: **regex vinda do usuário é entrada não confiável executada
pelo nosso motor**, e o M2 construiu suas garantias mecânicas apenas para os padrões
nossos.

O resultado mais consequente desta descoberta é negativo, e por isso mesmo importante:
**não há precedente a copiar** para a defesa contra regex patológica de usuário.

## Objective

Travar três decisões antes do `/to-plan` do M3: a superfície de uso do parser de YAML, o
formato do erro de config malformada, e o que fazer com um regex de usuário.

## Coverage Corner 1 — Integration Tests

### Q4 — Como a config é validada estruturalmente antes do uso

**ggshield** — `knowledge-base/references/ggshield/ggshield/core/config/utils.py:56-57`:

```python
if not isinstance(data, dict):
    raise ValueError(f"{path} should be a dictionary.")
```

Verifica o **tipo do topo** logo após o parse. É o detalhe que separa validação real de
validação de fachada: um YAML sintaticamente válido que seja uma lista, ou uma string
solta, passa pelo parser e explode depois, longe da origem — com uma mensagem que não
ajuda ninguém.

**gitleaks** — `knowledge-base/references/gitleaks/config/rule.go:64-70`:

```go
func (r *Rule) Validate() error {
	if r.validated {
		return nil
	}
	// Ensure |id| is present.
	if strings.TrimSpace(r.RuleID) == "" {
```

Dois traços: a validação é **memoizada** (`r.validated`), e a primeira invariante checada
é a mais básica — id presente. Validar cedo e uma vez só.

**Leitura para o M3:** validar na carga, na fronteira, e validar **a forma antes do
conteúdo** — tipo do topo, depois tipo de cada chave, depois o conteúdo de cada item.
`rules/error-handling.md § 3`: validar na entrada, falhar rápido.

## Coverage Corner 2 — Dependencies

### Q5 — Versão do parser de YAML e como é pinada

`knowledge-base/references/ggshield/pyproject.toml:50`:

```toml
"pyyaml>=6.0.1,<7",
```

Piso em `6.0.1` — não em `6.0`. A diferença importa: `PyYAML 6.0` tinha um problema de
build com Cython 3 que quebrava instalação em vários ambientes; `6.0.1` é a correção.
Teto no major seguinte, que é a disciplina padrão para dependência de parsing: uma major
nova pode mudar o comportamento de `safe_load` sem aviso.

**Leitura para o M3:** adotar o mesmo especificador. É a **única** dependência de runtime
que o `docs/PRD.md § NFR-1` autoriza, e ela está sendo gasta aqui — a partir do M3 o
orçamento de dependências está esgotado.

## Coverage Corner 3 — Tools

### Q6 — Onde a config é procurada e em que ordem

`knowledge-base/references/ggshield/ggshield/core/config/utils.py:113-121`:

```python
def find_local_config_path() -> Optional[Path]:
    try:
        project_root_dir = get_project_root_dir(Path())
    except GitExecutableNotFound:
        project_root_dir = Path()
    for filename in USER_CONFIG_FILENAMES:
        path = project_root_dir / filename
        if path.exists():
            return path
```

Três coisas:

1. **A raiz do projeto vem do git**, não do diretório atual — a config é do repositório,
   não de onde o usuário está.
2. **Degrada com elegância**: sem git, cai para o diretório atual (`:116-117`), em vez de
   falhar. Config é conveniência, não infraestrutura crítica.
3. **Primeiro nome que existir vence** (`:118-121`) — ordem fixa, sem mesclagem.

**Leitura para o M3:** o gitsafety tem um nome só (`.gitsafety.yml`), então a lista de
nomes é degenerada — mas a busca a partir da **raiz do repositório** transfere direto, e
o fallback para o diretório atual quando não há git também (nosso `scan` funciona fora de
repositório desde o M0).

## Coverage Corner 4 — Techniques

### Q1 — Como o YAML é carregado, e qual a superfície de uso

`knowledge-base/references/ggshield/ggshield/core/config/utils.py`:

| Linha | Conteúdo |
|---|---|
| `:5-6` | `import yaml.parser` / `import yaml.scanner` — importa os módulos de exceção **explicitamente** |
| `:44-47` | `def load_yaml_dict(path)` → `if not path.exists(): return None` |
| `:51` | `data = yaml.safe_load(f) or {}` |
| `:73` | `stream = yaml.dump(data, indent=2, default_flow_style=False)` (só na escrita) |

**A superfície inteira é `safe_load` e `dump`.** Nunca `yaml.load`, que executa
construtores arbitrários e é a porta clássica de execução de código via arquivo de
configuração.

O `:46-47` é o contrato de config opcional: arquivo ausente devolve `None`, não erro. É o
`docs/PRD.md § FR-22` — a ferramenta funciona sem config.

O `or {}` no `:51` cobre o YAML **vazio**: `safe_load` de um arquivo em branco devolve
`None`, e sem o `or {}` o código seguinte quebraria com `NoneType`.

### Q2 — Como arquivo malformado é reportado

`knowledge-base/references/ggshield/ggshield/core/config/utils.py:49-54`:

```python
with path.open() as f:
    try:
        data = yaml.safe_load(f) or {}
    except (yaml.parser.ParserError, yaml.scanner.ScannerError) as e:
        message = f"{path} is not a valid YAML file:\n{str(e)}"
        raise ValueError(message)
```

**Duas** classes de exceção, não uma: `ParserError` (estrutura inválida) e `ScannerError`
(token inválido). Capturar só a primeira deixa metade dos YAMLs malformados escapar como
exceção não tratada.

E o `str(e)` do PyYAML **já contém arquivo, linha e coluna** — o `problem_mark` da
exceção. O `docs/PRD.md § FR-23` exige "erro apontando a linha"; a informação vem do
parser, não precisa ser reconstruída.

Note que o erro é traduzido para `ValueError`, um tipo de domínio, em vez de propagar a
exceção da biblioteca. É `rules/error-handling.md § 2` aplicado.

### Q3 — Regex vinda do usuário: as duas metades do Risco nº 2

**Primeira metade — regex inválida na compilação.**

`knowledge-base/references/gitleaks/config/config.go`:

| Linha | Conteúdo |
|---|---|
| `:124` | `pathPat = regexp.MustCompile(vr.Path)` |
| `:127` | `regexPat = regexp.MustCompile(vr.Regex)` |
| `:343` | `allowlistRegexes = append(allowlistRegexes, regexp.MustCompile(a))` |
| `:347` | `allowlistPaths = append(allowlistPaths, regexp.MustCompile(a))` |

**`MustCompile` entra em pânico** com regex inválida. Nos quatro pontos, sobre valores que
vêm da config do usuário. O gitleaks valida outras coisas com cuidado — `rule.go:92`
verifica `SecretGroup` contra `NumSubexp()` e devolve erro tipado —, mas a compilação em
si não tem rede.

Na prática isso significa que um `.toml` com regex malformada derruba o processo com stack
trace de Go, em vez de dizer ao usuário qual linha da config dele está errada.

**Segunda metade — regex patológica na execução.**

Busca por `ReDoS`, `catastrophic`, `timeout` e `deadline` em `gitleaks/` e em
`ggshield/ggshield/`: **nenhuma ocorrência**.

**E isso não é descuido — é consequência do motor** (ADR D2 do plano). O gitleaks roda em
**RE2**, cuja garantia de projeto é execução em tempo linear no tamanho da entrada: com
RE2, backtracking catastrófico **não existe**, e uma defesa contra ele seria código morto.
O ggshield delega a detecção ao serviço remoto do GitGuardian, então não executa regex de
usuário no cliente.

**A conclusão é o achado mais importante deste milestone:** para este problema **não há
precedente a copiar**. Nenhum dos peers legíveis precisa da defesa que nós precisamos, e
copiar a ausência deles seria transplantar uma decisão cuja premissa não vale aqui
(`rules/architecture.md § 6`). O `re` do Python faz backtracking; desde o M1 nossa regex
roda dentro do `git commit`; e a partir do M3 ela pode vir de um arquivo que o usuário
escreveu.

## Cross-cutting Comparison

| Dimensão | ggshield | gitleaks | Decisão para o M3 |
|---|---|---|---|
| Função de parse | `yaml.safe_load` (`utils.py:51`) | TOML (fora de escopo) | `safe_load`, nunca `load` |
| Arquivo ausente | `return None` (`:46-47`) | — | Config opcional (FR-22) |
| Arquivo vazio | `or {}` (`:51`) | — | Adotar — sem isso, `NoneType` adiante |
| Malformado | `ParserError` **e** `ScannerError` → `ValueError` (`:52-54`) | — | Adotar as duas classes |
| Linha do erro | vem do `str(e)` do PyYAML | — | Não reconstruir; o parser já dá |
| Tipo do topo | `isinstance(data, dict)` (`:56-57`) | — | Adotar, e estender às três chaves |
| Descoberta | raiz do git, com fallback (`:113-121`) | — | Adotar |
| Pin da dependência | `pyyaml>=6.0.1,<7` (`pyproject.toml:50`) | — | Idêntico |
| Regex inválida | — | `MustCompile` → **panic** (`config.go:124,127`) | **Divergir**: `re.compile` em `try`, erro tipado com a linha |
| Regex patológica | **nenhuma defesa** | **nenhuma defesa** | **Sem precedente** — decisão nossa (ADR D3) |
| Validação estrutural | tipo do topo | memoizada, id primeiro (`rule.go:64-70`) | Validar forma antes de conteúdo |

## ADRs

### D1 — Superfície mínima do parser: `safe_load` e nada mais

**Decisão:** o M3 usa exatamente uma função do PyYAML — `yaml.safe_load` — e pina
`pyyaml>=6.0.1,<7`.

**Rationale:** `utils.py:51` e `pyproject.toml:50`. `yaml.load` executa construtores
arbitrários e é a porta clássica de execução de código via arquivo de configuração — num
produto de segurança, usá-la seria contradição. O piso em `6.0.1`, e não `6.0`, tem motivo:
a `6.0` tinha problema de build com Cython 3. O teto no major é a disciplina padrão para
parser: uma major nova pode mudar `safe_load` sem aviso.

Esta é a **única** dependência de runtime que o `docs/PRD.md § NFR-1` autoriza. A partir
do M3 o orçamento está esgotado, e qualquer dependência futura exige revisar o NFR.

**Alternativas consideradas:** (a) `yaml.load` com `Loader=SafeLoader` — equivalente em
segurança, mas mais verboso e fácil de alguém "simplificar" removendo o loader; (b)
`tomllib` da stdlib, zero dependências — rejeitada, o `docs/PRD.md § FR-20` decidiu YAML
por ser o que o público-alvo lê; (c) parser próprio — Regra 9, jamais.

**Consequências:** o gitsafety passa a ter uma dependência de runtime e, com ela, uma
superfície de CVE. O `/deps-audit` de todo milestone seguinte precisa auditá-la.

### D2 — Erro de config aponta arquivo e linha, com erro tipado

**Decisão:** capturar `yaml.parser.ParserError` **e** `yaml.scanner.ScannerError`,
traduzir para erro de domínio do gitsafety, e preservar o `str(e)` do PyYAML — que já traz
arquivo, linha e coluna.

**Rationale:** `utils.py:52-54`. Capturar só `ParserError` deixa metade dos YAMLs
malformados escapar como exceção não tratada — token inválido levanta `ScannerError`.
Traduzir para erro de domínio é `rules/error-handling.md § 2`; preservar o `str(e)` é o
que satisfaz o `FR-23` sem reconstruir informação que o parser já produziu.

**Alternativas consideradas:** (a) capturar `yaml.YAMLError` (a base) — pega mais casos,
mas também pega erros que talvez devessem propagar; as duas classes específicas são a
escolha do precedente e cobrem o malformado; (b) reformatar a mensagem do PyYAML —
perderia o `problem_mark`, que é justamente o valor.

**Consequências:** a mensagem de erro carrega o estilo do PyYAML, não o nosso. Aceitável:
ela é precisa, e precisão vale mais que uniformidade estética num erro de config.

### D3 — Regex de usuário: validar na carga **e** limitar na execução

**Decisão:** todo padrão vindo do `rules:` do usuário é (a) compilado em `try/except` na
carga, com erro tipado apontando a linha; (b) submetido à mesma análise de quantificador
livre do M2; (c) medido contra entrada adversarial na carga, e **rejeitado** se exceder o
teto.

**Rationale:** aqui **não há precedente a copiar**, e a ausência é explicada, não
ignorada. O gitleaks usa `MustCompile` (`config.go:124,127,343,347`), que entra em pânico
— aceitável para eles porque RE2 torna a segunda metade do problema inexistente, e porque
um panic num scanner de linha de comando é diferente de um panic dentro de um hook de
commit. Nenhum peer trata patologia porque nenhum precisa.

Nós precisamos das duas metades: o `re` do Python faz backtracking, e desde o M1 a regex
roda dentro do `git commit`. Uma regex patológica na config do usuário não é bug do
usuário — é o **nosso** hook pendurando o **commit** dele.

**Alternativas consideradas:** (a) `MustCompile`-equivalente, deixando propagar —
rejeitada, transforma erro de digitação do usuário em stack trace; (b) validar só na carga,
sem medir — rejeitada, a análise estática do M2 já se provou insuficiente sozinha (ADR D6
daquele milestone); (c) medir em cada execução, com timeout — rejeitada, o `re` do Python
não suporta timeout sem thread, e thread dentro de hook é complexidade desproporcional;
(d) aceitar sem defesa e documentar o risco — rejeitada, é o usuário pagando por uma
decisão nossa.

**Consequências:** a carga da config fica mais lenta (compila e mede cada regra do
usuário). Como acontece uma vez por invocação e o M2 mediu 5,7 ms por regra sobre 1.000
arquivos, o custo sobre uma entrada adversarial curta é irrelevante. Um usuário com regex
legítima porém lenta será rejeitado — falso negativo de configuração, preferível ao
commit pendurado.

### D4 — Validar a forma antes do conteúdo

**Decisão:** a validação da config acontece em camadas: tipo do topo (`dict`), depois tipo
de cada chave conhecida, depois conteúdo de cada item. Chave desconhecida é **erro**, não
silêncio.

**Rationale:** `utils.py:56-57` valida o tipo do topo; `rule.go:64-70` valida a invariante
mais básica primeiro. Sobre chave desconhecida: com três chaves apenas, um `ignroe:` com
erro de digitação seria ignorado em silêncio e o usuário concluiria que o gitsafety não
funciona — quando na verdade a config dele nunca foi lida. Erro explícito com sugestão é
`rules/error-handling.md § 2`.

**Alternativas consideradas:** (a) ignorar chave desconhecida — comportamento comum e
errado; o silêncio custa uma sessão de depuração ao usuário; (b) avisar sem falhar —
avisos em ferramenta de linha de comando são rolados para cima e não lidos; (c) validar
com um schema de terceiro (`pydantic`, `voluptuous`) — gastaria a segunda dependência num
produto que autoriza uma.

**Consequências:** uma config com chave a mais falha em vez de degradar. É o
comportamento desejado num arquivo de três chaves.

## Recommendations

1. **`yaml.safe_load`, `pyyaml>=6.0.1,<7`** (D1). Única dependência autorizada; a partir
   daqui o orçamento está esgotado.
2. **Capturar as duas classes de erro do PyYAML** e preservar o `str(e)` (D2) — a linha
   vem do parser.
3. **Regex de usuário: compilar em `try`, analisar quantificador, medir contra
   adversarial, rejeitar se exceder** (D3). Sem precedente; a decisão é nossa.
4. **Validar a forma antes do conteúdo**, com chave desconhecida como erro (D4).
5. **Config ausente devolve vazio, não erro** (`utils.py:46-47`) — o `FR-22` exige que a
   ferramenta funcione sem config.
6. **`or {}` no resultado do parse** — YAML vazio devolve `None`, e sem isso quebra adiante.
7. **Procurar a config a partir da raiz do repositório**, com fallback para o diretório
   atual quando não houver git (`utils.py:113-121`).

## Blocked questions

Nenhuma. A segunda metade de Q3 foi respondida com "nenhum peer trata" — e, conforme o
ADR D2 do plano, isso é **achado**, não lacuna: a explicação (RE2 não faz backtracking;
o ggshield não executa regex de usuário no cliente) é o que impede a conclusão errada de
que também podemos ignorar o problema.
