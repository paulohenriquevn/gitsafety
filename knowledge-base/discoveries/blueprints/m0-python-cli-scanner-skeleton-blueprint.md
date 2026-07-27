# Blueprint: Esqueleto de CLI Python para varredura de arquivos (M0)

**Slug:** `m0-python-cli-scanner-skeleton`
**Plano de origem:** `knowledge-base/discoveries/plans/m0-python-cli-scanner-skeleton-plan.md` (v1.1)
**Revisão de edge cases:** `knowledge-base/reviews/m0-python-cli-scanner-skeleton-edge-cases-2026-07-27.md`
**Data:** 2026-07-27
**Questões:** 8 respondidas, 0 BLOCKED
**Veredito `/discover-confidence`:** registrado ao final desta investigação

> **Limitação declarada de origem (D3 do plano).** Três dos seis peers clonados —
> `detect-secrets`, `ripsecrets`, `secretlint` — são ilegíveis: o glob de proteção
> `Read(**/*secret*)` em `.claude/settings.json` casa com o nome dos diretórios. O peer
> mais próximo do gitsafety (`detect-secrets`: Python + pre-commit) está entre eles.
> Pelo mesmo motivo, `ggshield/ggshield/cmd/secret/` — o comando de scan do ggshield —
> também é inacessível. Toda conclusão sobre a **política** de scan do ggshield (Q2, Q3)
> vem apenas das primitivas em `core/` e é marcada **[confiança reduzida]** na própria
> frase.

## Context

O `ROADMAP.md § M0` define cinco itens de DoD e dois riscos nomeados. Esta investigação
existe para atacar os dois riscos com precedente em vez de tentativa e erro:

- **Risco M0 nº 1** — "o empacotamento Python consumir mais tempo que a detecção".
- **Risco M0 nº 2** — "a fronteira 'arquivo de texto' ser mal definida: heurística de
  byte NUL erra em UTF-16, e pular um arquivo por engano é um falso negativo silencioso".

O resultado mais consequente da investigação é que **o risco nº 2 estava mal formulado**:
nenhum dos dois peers legíveis usa sniffing de byte NUL. A pergunta certa não era "como
detectar binário lendo o conteúdo" e sim "como evitar precisar detectar".

## Objective

Travar quatro decisões do M0 — empacotamento, descarte de arquivo, contrato de exit code
e layout de teste — cada uma com precedente citado em `arquivo:linha`, antes que
`/to-plan` decomponha o milestone.

## Coverage Corner 1 — Integration Tests

### Q4 — Como o ggshield organiza a suíte de testes

`knowledge-base/references/ggshield/tests/` tem **dois níveis**, não três:

| Diretório | Papel |
|---|---|
| `tests/unit/` | Lógica isolada |
| `tests/functional/` | Ponta a ponta, invocando a CLI de verdade |
| `tests/conftest.py`, `tests/factories.py`, `tests/factory_constants.py` | Fixtures e construtores de objeto de teste compartilhados |
| `tests/test_factories.py` | **Testes das próprias factories** — o andaime é testado |

O `Makefile` expõe os níveis como alvos separados e os compõe
(`knowledge-base/references/ggshield/Makefile:21-26`):

```
test: unittest functest
unittest:
functest:
```

Não existe camada "integration" nomeada. Para um cliente de serviço remoto isso faz
sentido: o que estaria na camada de integração é justamente a chamada de API, que os
testes funcionais exercem de ponta a ponta.

**Leitura para o gitsafety:** o `rules/testing.md § 2` pede três níveis, mas o M0 não tem
fronteira externa nenhuma — sem rede, sem banco, sem fila. Dois níveis (`unit/` e
`functional/`) cobrem o M0 honestamente; a camada de integração nasce no M1, quando o
`git` entra como fronteira real.

### Q5 — Como o gitleaks estrutura o caso de teste de uma regra

Achado que a revisão de edge cases (EC-1) corrigiu de rota: o padrão **não** está em
`detect/`, e sim em `knowledge-base/references/gitleaks/cmd/generate/config/rules/` —
**um arquivo por regra**, com o caso de teste embutido na própria definição.

`knowledge-base/references/gitleaks/cmd/generate/config/rules/adafruit.go` inteiro:

```go
func AdafruitAPIKey() *config.Rule {
	// define rule
	r := config.Rule{
		Description: "Identified a potential Adafruit API Key, ...",
		RuleID:      "adafruit-api-key",
		Regex:       utils.GenerateSemiGenericRegex([]string{"adafruit"}, utils.AlphaNumericExtendedShort("32"), true),
		Keywords:    []string{"adafruit"},
	}

	// validate
	tps := utils.GenerateSampleSecrets("adafruit", secrets.NewSecret(utils.AlphaNumericExtendedShort("32")))
	return utils.Validate(r, tps, nil)
}
```

A assinatura é `utils.Validate(rule, tps, fps)` — **true positives** e **false
positives** como argumentos posicionais. Aqui `fps` é `nil`; regras mais ruidosas passam
uma lista. A validação roda na **construção da regra**, não em um teste separado: uma
regra que não casa seu próprio segredo de exemplo não chega a existir.

**Leitura para o gitsafety:** é a resposta direta ao `rules/testing.md § 4.1`
(edge case vs negative case) aplicada a regras de detecção. O par (acerto, não-acerto)
mora junto da regra, não em arquivo distante. Isso é o layout que o M2 deve herdar, e o
M0 deve nascer já compatível com ele — uma regra é um dado com casos anexos, não um
regex solto.

## Coverage Corner 2 — Dependencies

### Q6 — Dependências de runtime do ggshield

`knowledge-base/references/ggshield/pyproject.toml:34-52` declara 17 dependências.
Classificando pelo nosso escopo:

| Dependência | Propósito | gitsafety precisa? |
|---|---|---|
| `click>=8.1.0,<9` | Framework de CLI | **Talvez** — `argparse` da stdlib cobre 4 flags (parsimony rung 2) |
| `pyyaml>=6.0.1,<7` | Parser de config | **Sim** — é a única dep externa que o `docs/PRD.md § NFR-1` autoriza |
| `charset-normalizer~=3.1.0` | Detecção de encoding | **Ver ADR D2** — trade-off central, não é decisão óbvia |
| `platformdirs`, `configupdater`, `python-dotenv`, `packaging`, `rich` | Ergonomia e config de produto | Não |
| `cryptography`, `oauthlib`, `pyjwt`, `requests`, `pygitguardian`, `marshmallow`, `marshmallow-dataclass` | Autenticação e API remota do GitGuardian | Não — não-objetivo (`docs/PRD.md § 5 NG2`) |

Confirma EC-9: a maioria serve ao backend comercial. Mas o exercício rendeu o achado
mais valioso da investigação, abaixo.

### O comentário que vale a investigação inteira

`knowledge-base/references/ggshield/pyproject.toml:36-39`:

```toml
# NB: kept at a tight bound on purpose — charset-normalizer 3.2+ changed its
# encoding detection and mis-decodes some valid UTF-8 content, which would
# degrade secret scanning (see _decode_bytes in core/scan/scannable.py).
"charset-normalizer~=3.1.0",
```

Um bump de minor version na biblioteca de detecção de encoding **degradou silenciosamente
a detecção de segredos** — conteúdo UTF-8 válido passou a ser mal decodificado, e um
segredo em conteúdo mal decodificado simplesmente não casa a regex. Sem exceção, sem log,
sem teste vermelho: só menos achados.

Esse é exatamente o modo de falha do risco nº 2 do M0, e ele veio de uma dependência, não
de código próprio. Registrado como ADR D2.

### Q7 — Parser de config e caminho de erro

`knowledge-base/references/ggshield/ggshield/core/config/utils.py`:

| Linha | Conteúdo |
|---|---|
| `:5-6` | `import yaml.parser` / `import yaml.scanner` — importa os módulos de exceção explicitamente |
| `:51` | `data = yaml.safe_load(f) or {}` — **`safe_load`**, nunca `load` |
| `:52` | `except (yaml.parser.ParserError, yaml.scanner.ScannerError) as e:` — captura as duas classes de erro de YAML |
| `:54` | `raise ValueError(message)` — traduz para erro de domínio |
| `:57` | `raise ValueError(f"{path} should be a dictionary.")` — valida o **tipo** do topo, não só a sintaxe |

O `:57` é o detalhe que separa validação real de validação de fachada: um YAML
sintaticamente válido que seja uma lista, ou uma string, passa pelo parser e quebra
depois, longe da origem. Validar a forma do topo na fronteira é `rules/error-handling.md
§ 2` aplicado.

**Leitura para o gitsafety:** o `FR-23` (config inválida → exit 2 apontando a linha) tem
precedente direto. `ParserError` e `ScannerError` do PyYAML já carregam `problem_mark`
com linha e coluna — a informação que o FR-23 exige já vem do parser, não precisa ser
reconstruída.

## Coverage Corner 3 — Tools

### Q8 — Ferramental de build, teste e lint

`knowledge-base/references/ggshield/Makefile` — alvos declarados:

| Linha | Alvo | Papel |
|---|---|---|
| `:5` | `all` | Entrada padrão |
| `:21` | `test: unittest functest` | **Composição** — um comando roda a pirâmide inteira |
| `:23` | `unittest` | Nível unitário isolado |
| `:26` | `functest` | Nível funcional isolado |
| `:29` | `coverage` | Cobertura como alvo separado, não acoplado a `test` |
| `:35` | `black` | Formatação |
| `:41` | `isort` | Ordenação de imports |
| `:44` | `lint: isort black flake8` | **Composição** — lint é a soma de três ferramentas |
| `:46` | `lock` | Congelamento de dependências |

Duas composições (`test` e `lint`) e o resto atômico. Quem chega no projeto roda `make
test` sem saber o que tem dentro; quem está iterando roda `make unittest`.

O gerenciador é `uv` (`knowledge-base/references/ggshield/uv.lock`), divergente do nosso
`pip`/`pipx` (EC-7). A **estrutura de alvos** transfere; o gerenciador não.

## Coverage Corner 4 — Techniques

### Q1 — Entry point e piso de versão

`knowledge-base/references/ggshield/pyproject.toml`:

| Linha | Conteúdo |
|---|---|
| `:33` | `requires-python = ">=3.9"` — **idêntico ao nosso alvo** |
| `:67` | `[project.scripts]` |
| `:68` | `ggshield = "ggshield.__main__:main"` |

Empacotamento moderno: `pyproject.toml` com `[project.scripts]`, apontando para
`__main__:main` do pacote. Nenhum `setup.py` executável envolvido no entry point.

O risco nº 1 do M0 ("empacotamento consumir mais tempo que a detecção") tem, portanto,
uma resposta de duas linhas. É a evidência mais barata desta investigação e a que mais
reduz risco.

### Q2 — Heurística de descarte de arquivo

Este é o resultado que reformula o risco nº 2 do M0.

**ggshield — descarte por extensão, sem ler conteúdo** [confiança reduzida: a política em
`cmd/secret/` não foi lida]:

`knowledge-base/references/ggshield/ggshield/utils/files.py:131-134`:

```python
def is_path_binary(path: Union[str, Path]) -> bool:
    ext = Path(path).suffix
    # `[1:]` because `ext` starts with a "." but extensions in `BINARY_EXTENSIONS` do not
    return ext[1:] in BINARY_EXTENSIONS
```

Nenhum sniffing. `BINARY_EXTENSIONS` é um conjunto em módulo dedicado —
`knowledge-base/references/ggshield/ggshield/utils/_binary_extensions.py`, 213 linhas,
com nota de manutenção no topo: *"for readability, keep this set sorted"*.

E o arquivo binário **não é descartado em silêncio**
(`knowledge-base/references/ggshield/ggshield/core/scan/file.py:69-77`):

```python
binary_paths: List[Path] = []
for path in ...:
    if is_path_binary(path):
        binary_paths.append(path)
    ...
return (files, binary_paths)
```

A função devolve **duas listas**. O que foi pulado continua visível para quem chamou.
Esse é o antídoto direto para a segunda metade do risco nº 2 ("pular um arquivo por
engano é um falso negativo silencioso"): o pulo é um dado de retorno, não um efeito
colateral.

**gitleaks — delega ao git e limita por tamanho:**

| Citação | Conteúdo |
|---|---|
| `knowledge-base/references/gitleaks/sources/git.go:329` | `if gitdiffFile.IsBinary {` — quem decide o que é binário é o **git**, não o gitleaks |
| `knowledge-base/references/gitleaks/detect/files.go:55-60` | `if d.MaxTargetMegaBytes > 0 { if rawLength > int64(d.MaxTargetMegaBytes) { ... } }` — limite de tamanho só é aplicado quando configurado (`> 0` = desligado por padrão) |
| `knowledge-base/references/gitleaks/cmd/root.go:292` | O limite vem da flag `--max-target-megabytes` |

**Conclusão dos dois:** nenhum peer legível faz sniffing de byte NUL. Um usa lista de
extensões, o outro delega ao git. A premissa do risco nº 2 do M0 — de que precisaríamos
de uma heurística de conteúdo, com o problema de UTF-16 embutido — **não se sustenta**.

### Q3 — Contrato de exit code

**ggshield** — `knowledge-base/references/ggshield/ggshield/core/errors.py`:

| Linha | Código | Significado |
|---|---|---|
| `:24` | `class ExitCode(IntEnum)` | Enum tipado, não inteiros soltos |
| `:30` | `SUCCESS = 0` | Nada encontrado |
| `:32` | `SCAN_FOUND_PROBLEMS = 1` | Segredo encontrado |
| `:34` | `USAGE_ERROR = 2` | Erro de uso / config |
| `:36` | `AUTHENTICATION_ERROR = 3` | (específico do produto remoto) |
| `:38` | `GITGUARDIAN_SERVER_UNAVAILABLE = 4` | (idem) |
| `:44` | `UNEXPECTED_ERROR = 128` | Falha não prevista |

O mecanismo (`:47-59`) é o que interessa: `_ExitError(click.ClickException)` é a base de
todas as exceções de domínio, e cada subclasse **carrega seu próprio exit code**
(`UnexpectedError`, `ParseError`, `AuthError`, `ServiceUnavailableError`…). O código de
saída não é decidido no `main` por uma cadeia de `if`; ele viaja junto com o erro. É
`rules/error-handling.md § 2` ("erros explícitos e tipados") com consequência executável.

**gitleaks** — o código de "achou" é **configurável**:

| Citação | Conteúdo |
|---|---|
| `knowledge-base/references/gitleaks/cmd/detect.go:65` | `exitCode := mustGetIntFlag(cmd, "exit-code")` |
| `knowledge-base/references/gitleaks/cmd/root.go:498` | `os.Exit(exitCode)` — sai com o valor configurado quando há findings |
| `knowledge-base/references/gitleaks/cmd/root.go:494` | `os.Exit(1)` — erro interno, fixo |
| `knowledge-base/references/gitleaks/cmd/root.go:228` | `os.Exit(126)` |

**talisman** — binário, com constantes nomeadas
(`knowledge-base/references/talisman/cmd/talisman.go:103,108,114,124`): `EXIT_SUCCESS` e
`EXIT_FAILURE`. O fallback previsto por EC-4 (ampliar para a raiz) **não foi necessário**
— o contrato estava em `cmd/` na primeira tentativa.

**Convergência:** os três concordam em `0 = limpo` e `1 = achou`. O `2` do ggshield para
erro de uso é o único precedente direto do nosso terceiro código, e ele bate exatamente
com o `docs/PRD.md § FR-18`.

## Cross-cutting Comparison

| Dimensão | ggshield (Python) | gitleaks (Go) | talisman (Go) | Decisão para o M0 |
|---|---|---|---|---|
| Entry point | `pyproject.toml` `[project.scripts]` → `__main__:main` (`:67-68`) | n/a (binário Go) | n/a | Copiar o idioma do ggshield |
| Piso de Python | `>=3.9` (`:33`) | n/a | n/a | `>=3.9` confirmado viável |
| Binário | Lista de extensões, sem sniffing (`utils/files.py:131-134`) | Delega ao git (`sources/git.go:329`) | não investigado | Lista de extensões (ADR D1) |
| Arquivo pulado | Retornado em lista separada (`core/scan/file.py:69-77`) | n/a | n/a | Adotar — mata o falso negativo silencioso |
| Limite de tamanho | Só em contexto de tar (`tar_utils.py:56`) | Flag, desligado por padrão (`detect/files.go:55`) | n/a | 1 MB fixo no M0; flag só se pedirem |
| Exit code | `IntEnum` + exceção que carrega o código (`errors.py:24-59`) | Configurável por flag (`detect.go:65`) | `EXIT_SUCCESS`/`EXIT_FAILURE` | `IntEnum` do ggshield, fixo (não configurável) |
| Parser de config | `yaml.safe_load` + valida tipo do topo (`config/utils.py:51-57`) | TOML (fora do escopo) | n/a | Idêntico ao ggshield (M3) |
| Níveis de teste | `unit/` + `functional/` | teste embutido na definição da regra | n/a | `unit/` + `functional/` no M0 |
| Teste de regra | n/a | `Validate(rule, tps, fps)` na construção | n/a | Herdar no M2; M0 nasce compatível |
| Composição de tarefas | `make test` = unittest + functest; `make lint` = isort + black + flake8 | Makefile | n/a | Mesma forma |

## ADRs

### D1 — Descarte de binário por extensão, nunca por sniffing de conteúdo

**Decisão:** o M0 decide "isto é binário" **exclusivamente pela extensão do arquivo**,
contra um conjunto explícito e ordenado. Nenhuma leitura de conteúdo para classificação.

**Rationale:** os dois peers legíveis convergem em não fazer sniffing —
`ggshield/utils/files.py:131-134` usa conjunto de extensões, `gitleaks/sources/git.go:329`
delega ao git. Sniffing de NUL tem o modo de falha de UTF-16 que o próprio `ROADMAP.md
§ M0` já anotou como risco, e a alternativa custa 213 linhas de dados (o
`_binary_extensions.py` do ggshield) em vez de uma heurística com casos de borda.
Extensão é determinístico, testável com um `parametrize`, e não lê byte nenhum de arquivo
que será descartado.

**Alternativas consideradas:** (a) sniffing de byte NUL nos primeiros N bytes — rejeitada,
é literalmente o risco nº 2 do roadmap e nenhum peer a usa; (b) `charset-normalizer` para
decidir se é texto — rejeitada, ver D2; (c) delegar ao git como o gitleaks — rejeitada
para o M0, que varre disco e não pode depender de repositório git (o `docs/PRD.md § NFR-6`
exige que `git` só seja necessário em `--staged` e `--history`).

**Consequências:** binário com extensão desconhecida será lido e varrido — desperdício
de I/O, não erro; ele simplesmente não casa padrão nenhum. Arquivo de texto com extensão
da lista será pulado — **falso negativo**, e é o custo real desta decisão. Mitigado pelo
D3: o que foi pulado é reportado, não some.

### D2 — Sem detecção de encoding no M0; `utf-8` com `errors="replace"`

**Decisão:** o M0 lê arquivos como `utf-8` com `errors="replace"` e não adota
`charset-normalizer` nem qualquer detector de encoding.

**Rationale:** `knowledge-base/references/ggshield/pyproject.toml:36-39` documenta que um
bump de `charset-normalizer` para 3.2+ passou a **mal decodificar UTF-8 válido, degradando
a detecção de segredos** — falha silenciosa, sem exceção e sem teste vermelho, só menos
achados. O ggshield precisa do detector porque varre repositórios corporativos
arbitrários; o gitsafety do M0 varre o repositório do próprio desenvolvedor, onde UTF-8 é
a norma esmagadora. Adotar a dependência importaria uma classe inteira de falha
silenciosa para cobrir uma cauda que o M0 não tem. `rules/parsimony-ladder.md` rung 2:
`bytes.decode` da stdlib resolve o caso comum.

**Alternativas consideradas:** (a) `charset-normalizer` como o ggshield — rejeitada pelo
precedente documentado de degradação silenciosa e por violar o teto de uma dependência do
`docs/PRD.md § NFR-1`; (b) `errors="strict"` e pular o que não decodificar — rejeitada,
transforma arquivo com um byte estranho em falso negativo total; (c) tentar utf-8 e cair
para latin-1 — rejeitada, latin-1 decodifica qualquer sequência de bytes, então o
fallback nunca falha e mascara o problema em vez de expô-lo.

**Consequências:** arquivo em UTF-16 ou em encoding legado terá caracteres substituídos e
pode não casar um padrão — falso negativo aceito e **declarado**, revisável no M4 se um
caso real aparecer. `errors="replace"` nunca levanta exceção, então nenhum arquivo derruba
a varredura.

### D3 — O que foi pulado é resultado, não efeito colateral

**Decisão:** a função de travessia devolve os arquivos varridos **e** os arquivos pulados,
com o motivo de cada pulo. Nenhum descarte silencioso em nenhum ponto do caminho.

**Rationale:** `knowledge-base/references/ggshield/ggshield/core/scan/file.py:69-77`
retorna `(files, binary_paths)` em vez de filtrar e esquecer. A segunda metade do risco
nº 2 do M0 é exatamente "pular um arquivo por engano é um falso negativo silencioso" — e
a cura não é acertar sempre a heurística (D1 admite que ela erra), é **tornar o erro
visível**. Um usuário que vê "3 arquivos pulados" investiga; um que não vê nada, não.
`rules/error-handling.md § 5` proíbe engolir; pular arquivo em silêncio é a versão
silenciosa do mesmo pecado.

**Alternativas consideradas:** (a) filtrar e seguir, como faria a implementação óbvia —
rejeitada, é o anti-pattern nomeado no roadmap; (b) logar em nível debug — rejeitada, log
que ninguém liga não é evidência.

**Consequências:** a assinatura da travessia fica com valor de retorno composto em vez de
um simples iterável de caminhos, e a saída ganha uma linha de resumo. Custo pequeno,
pago já no M0 para não ser retrofit depois.

### D4 — Exit code viaja com o erro, e não é configurável

**Decisão:** `ExitCode(IntEnum)` com `SUCCESS = 0`, `SECRETS_FOUND = 1`, `USAGE_ERROR = 2`;
cada exceção de domínio carrega seu código. Sem flag `--exit-code`.

**Rationale:** o mecanismo do ggshield (`errors.py:24-59`) mantém o código junto do erro
que o causou, em vez de reconstruí-lo no `main` com uma cadeia de `if` — que é onde esse
tipo de código apodrece. Os três peers convergem em `0`/`1`; o `2` do ggshield para erro
de uso é precedente direto do `docs/PRD.md § FR-18`. Quanto à configurabilidade: o
gitleaks a oferece (`cmd/detect.go:65`), e ela existe para acomodar pipelines de CI
legados — problema que não temos, e um knob que ninguém pediu é YAGNI
(`rules/parsimony-ladder.md` rung 1).

**Alternativas consideradas:** (a) inteiros literais no `main` — rejeitada, `2` sem nome
não diz nada em revisão; (b) flag `--exit-code` como o gitleaks — rejeitada por YAGNI e
por violar o teto de 4 flags do `docs/PRD.md § NFR-3`; (c) copiar os 6 códigos do ggshield
— rejeitada, três deles descrevem falhas de um backend remoto que não existe aqui.

**Consequências:** um sexto código futuro exige adicionar ao enum e à sua exceção — que é
o ponto. O contrato de saída fica congelado em 0/1/2 e testável por asserção direta.

### D5 — `argparse` da stdlib, não `click`

**Decisão:** o M0 usa `argparse` da biblioteca padrão. Nenhuma dependência de CLI.

**Rationale:** o `docs/PRD.md § NFR-1` autoriza **uma** dependência externa, e ela está
reservada ao parser de YAML do M3. O ggshield usa `click` (`pyproject.toml:40`) porque tem
dezenas de subcomandos aninhados (`cmd/{ai,auth,hmsl,honeytoken,machine,plugin,secret}`);
o gitsafety tem dois comandos e quatro flags, teto declarado no `NFR-3`.
`rules/parsimony-ladder.md` rung 2 é explícito: se a stdlib resolve, use a stdlib.

**Alternativas consideradas:** (a) `click` como o ggshield — rejeitada, gasta a única
dependência autorizada em algo que a stdlib faz; (b) `typer` — mesma objeção, mais uma
camada sobre `click`.

**Consequências:** o mecanismo de `_ExitError` do ggshield herda de
`click.ClickException`; sem `click`, o D4 precisa da sua própria classe base de exceção
com atributo de exit code. São ~10 linhas — a tradução está no D4, não é obstáculo.

## Recommendations

Em ordem de impacto sobre o M0, cada uma rastreável a um ADR e a uma citação:

1. **Empacotar com `pyproject.toml` + `[project.scripts]`** apontando para
   `gitsafety.__main__:main`, com `requires-python = ">=3.9"`. Precedente literal em
   `ggshield/pyproject.toml:33,67-68`. Neutraliza o risco nº 1 do M0.
2. **Classificar binário por extensão** (D1), com o conjunto em um módulo de dados
   dedicado e ordenado, como `ggshield/utils/_binary_extensions.py`. Não escrever
   sniffing de NUL.
3. **Devolver os arquivos pulados junto com os varridos** (D3), com motivo. Uma linha de
   resumo na saída.
4. **`ExitCode(IntEnum)` com 0/1/2 e exceções que carregam o código** (D4). Um teste por
   código.
5. **Ler com `utf-8` + `errors="replace"`** (D2). Registrar no README, quando o M0 fechar,
   que encoding legado é limitação conhecida.
6. **Dois níveis de teste — `unit/` e `functional/`** — compostos por um alvo único, como
   `ggshield/Makefile:21`. Integração nasce no M1, com o `git`.
7. **Nascer compatível com o formato de regra do M2**: regra é dado com casos de acerto e
   não-acerto anexos (`gitleaks/cmd/generate/config/rules/adafruit.go`), não regex solto.
   No M0 há uma regra só, mas a forma já deve ser essa.

### Recomendação ao humano, fora do escopo do M0

O glob `Read(**/*secret*)` em `.claude/settings.json` § `permissions.deny` protege
arquivos de credencial, mas casa com nomes de **diretório** e por isso bloqueia três dos
seis peers de referência e o comando de scan do ggshield. Um refinamento — por exemplo
`Read(**/*.secret)` e `Read(**/secrets.*)`, ou uma exceção para
`knowledge-base/references/**` — devolveria `detect-secrets` (o peer mais próximo do
gitsafety) às próximas descobertas. É mudança de política de segurança e fica com o
humano; esta descoberta não a fez.

## Blocked questions

Nenhuma. As 8 questões foram respondidas com citação verificada. Os fallbacks previstos
por EC-4 (ampliar busca no talisman) e a forma alternativa de EC-6 (resposta "delegado a
dependência") estavam disponíveis mas não foram necessários — o talisman respondeu em
`cmd/` na primeira tentativa, e a heurística de binário do ggshield é código próprio, não
delegação.
