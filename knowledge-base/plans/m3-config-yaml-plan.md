---
slug: m3-config-yaml
milestone_id: M3
created_at: 2026-07-27
goal: Permitir ajustar o gitsafety por um YAML de três chaves, tratando regex do usuário como entrada não confiável.
---

# Plan: M3 — Configuração `.gitsafety.yml`

## Goal

`.gitsafety.yml` com exatamente três chaves — `ignore`, `allow`, `rules` — todas
opcionais. Config ausente mantém o comportamento atual. Config malformada **para** a
execução com erro apontando arquivo e linha. Regex do usuário é compilada, analisada e
medida antes de ser aceita.

## Context

Quarto milestone. O M2 construiu garantias mecânicas para os **nossos** padrões; o M3
abre a porta para padrões do usuário, que atravessam essas defesas sem passar por
nenhuma — e desde o M1 a regex roda dentro do `git commit`.

O blueprint `knowledge-base/discoveries/blueprints/m3-config-yaml-blueprint.md`
(SHIPPABLE 100.0) travou 4 ADRs, e o achado central é **negativo**: para a defesa contra
regex patológica de usuário não há precedente a copiar. gitleaks usa `MustCompile` (que
entra em pânico) porque RE2 torna o problema inexistente para eles; ggshield não executa
regex de usuário no cliente. A decisão é nossa.

## Baseline Context (deep review of current state)

**Estado:** branch `develop`, tag `v0.3.0`, 512 testes verdes, 53 regras, **zero
dependências de runtime**. O M3 gasta a única autorizada pelo `docs/PRD.md § NFR-1`.

### Files that will be touched

| File | LoC hoje | Último commit | Por que existe hoje | Invariantes a preservar |
|---|---|---|---|---|
| `src/gitsafety/config.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/errors.py` | 128 | `dd69b11` | Hierarquia tipada | Toda exceção nova DEVE carregar `exit_code` |
| `src/gitsafety/patterns.py` | 161 | `74ab7d9` | `Rule` + construtores + `has_free_quantifier` | `has_free_quantifier` será reusado para regex do usuário |
| `src/gitsafety/scanner.py` | 88 | `2d78996` | Compõe walker + rules | `ScanResult(findings, skipped)` é contrato de `cli.render` |
| `src/gitsafety/walker.py` | 116 | `2d78996` | Travessia + pulos | `walk()` devolve `(files, skipped)` |
| `src/gitsafety/cli.py` | 138 | `74ab7d9` | Parser, render, exit | Máximo de 4 flags (`PRD § NFR-3`); `--config` é a 4ª |
| `pyproject.toml` | 62 | `d2bf174` | Empacotamento | `dependencies` deixa de ser vazio |
| `tests/unit/test_config.py` (NOVO) | 0 | — | (a criar) | — |
| `benchmarks/bench_config.py` (NOVO) | 0 | — | (a criar) | — |
| `README.md` | 262 | `74ab7d9` | Contrato público | `--config` migra de ⏳ para ✅ |

### Current callers / dependents

- `cli.main` chama `scan_path(args.path)` e `scan_staged(Path.cwd())`. Ambos passam a
  precisar da config carregada — é a primeira mudança de assinatura desde o M0.
- `scanner._scan_text` aplica cada regra a cada linha; o `allow` e o comentário inline
  agem **depois** do match, filtrando findings.
- `walker.walk` decide o que varrer; o `ignore` age **ali**, antes de abrir o arquivo.

### Domain glossary

- **`ignore`** — lista de globs de caminho que nem são abertos. Age no walker.
- **`allow`** — lista de valores (texto exato ou regex) que não geram finding. Age depois do match.
- **`rules`** — padrões do usuário, acrescentados ao catálogo embutido.
- **Comentário inline** — `# gitsafety: allow` na linha, que suprime o finding daquela linha.
- **Regex não confiável** — padrão vindo do `rules:` ou do `allow:`; escrito pelo usuário, executado pelo nosso motor.
- **Entrada adversarial** — cadeia construída para forçar backtracking; usada para medir a regex do usuário antes de aceitá-la.

### Architecture boundaries affected

```
domínio        errors.py, finding.py, patterns.py, catalog.py, rules.py
aplicação      config.py, walker.py, scanner.py, staged.py     <- config.py é novo
infraestrutura git.py
interface      cli.py, hook.py, __main__.py
```

`config.py` é **aplicação**: lê do sistema de arquivos (fronteira) mas produz objetos de
domínio. Não é infraestrutura porque não encapsula um serviço externo — o `yaml` é
biblioteca, não sistema.

## Prior Art & Related Work

| Fonte | O que aproveitamos | Citação |
|---|---|---|
| Blueprint do M3 | Os 4 ADRs são entrada travada | `knowledge-base/discoveries/blueprints/m3-config-yaml-blueprint.md` |
| ggshield | `safe_load`, config ausente devolve `None`, `or {}` para vazio | `knowledge-base/references/ggshield/ggshield/core/config/utils.py:44-51` |
| ggshield | Duas classes de erro do PyYAML, mensagem com linha | `knowledge-base/references/ggshield/ggshield/core/config/utils.py:52-54` |
| ggshield | Validação do tipo do topo | `knowledge-base/references/ggshield/ggshield/core/config/utils.py:56-57` |
| ggshield | Descoberta a partir da raiz do git, com fallback | `knowledge-base/references/ggshield/ggshield/core/config/utils.py:113-121` |
| ggshield | Pin `pyyaml>=6.0.1,<7` | `knowledge-base/references/ggshield/pyproject.toml:50` |
| gitleaks | O que **não** fazer: `MustCompile` em regex de usuário | `knowledge-base/references/gitleaks/config/config.go:124,127` |
| gitleaks | Validação memoizada, invariante básica primeiro | `knowledge-base/references/gitleaks/config/rule.go:64-70` |
| Blueprint do M2 | `has_free_quantifier` reusado para regex do usuário | `knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md` |
| `rules/error-handling.md § 2` | Validar na fronteira, erro tipado com contexto | `rules/error-handling.md` |
| `rules/parsimony-ladder.md` | Rung 4 sustenta o D1 (uma dependência, não duas) | `rules/parsimony-ladder.md` |

## Objective

Ao fim do M3, um `.gitsafety.yml` com as três chaves altera o comportamento do `scan` e
do hook; um arquivo malformado para a execução com exit 2 e a linha do erro; e um regex
patológico do usuário é **rejeitado na carga**, não executado dentro do commit.

## ADRs

D1-D4 vêm do blueprint, restatados em forma executável; texto integral em
`knowledge-base/discoveries/blueprints/m3-config-yaml-blueprint.md § ADRs`. D5-D6 são
deste plano.

### D1 — Superfície mínima do parser: `safe_load` e nada mais

**Decisão:** uma função do PyYAML — `yaml.safe_load` — e pin `pyyaml>=6.0.1,<7`.

**Rationale:** `utils.py:51` e `pyproject.toml:50`. `yaml.load` executa construtores
arbitrários; num produto de segurança seria contradição. O piso `6.0.1` corrige o problema
de build com Cython 3 da `6.0`. Esta é a **única** dependência que o `docs/PRD.md § NFR-1`
autoriza, e ela se esgota aqui.

**Alternativas consideradas:** (a) `yaml.load(Loader=SafeLoader)` — equivalente, mais
verboso e fácil de alguém "simplificar" removendo o loader; (b) `tomllib` da stdlib, zero
deps — o `FR-20` decidiu YAML por ser o que o público lê; (c) parser próprio — Regra 9.

**Consequências:** o produto passa a ter superfície de CVE. Todo `/deps-audit` seguinte
audita o PyYAML.

### D2 — Erro de config aponta arquivo e linha, com erro tipado

**Decisão:** capturar `yaml.parser.ParserError` **e** `yaml.scanner.ScannerError`,
traduzir para `ConfigError` do gitsafety, preservando o `str(e)` do PyYAML.

**Rationale:** `utils.py:52-54`. Capturar só `ParserError` deixa metade dos malformados
escapar — token inválido levanta `ScannerError`. O `str(e)` do PyYAML já traz arquivo,
linha e coluna via `problem_mark`; o `FR-23` é satisfeito sem reconstruir nada.

**Alternativas consideradas:** (a) capturar `yaml.YAMLError` — pega mais, inclusive o que
talvez devesse propagar; (b) reformatar a mensagem — perderia o `problem_mark`.

**Consequências:** a mensagem carrega o estilo do PyYAML. Precisão vale mais que
uniformidade num erro de config.

### D3 — Regex de usuário: validar na carga **e** medir antes de aceitar

**Decisão:** todo padrão do `rules:` e do `allow:` é (a) compilado em `try/except` com
erro tipado apontando a chave; (b) submetido a `has_free_quantifier`; (c) medido contra
entrada adversarial, e **rejeitado** se exceder o teto.

**Rationale:** aqui não há precedente. gitleaks usa `MustCompile`
(`config.go:124,127,343,347`), que entra em pânico — aceitável para eles porque RE2 torna
a patologia inexistente. Nós temos `re` com backtracking, e desde o M1 a regex roda dentro
do `git commit`: regex patológica na config não é bug do usuário, é o nosso hook
pendurando o commit dele.

**Alternativas consideradas:** (a) deixar propagar como o gitleaks — transforma erro de
digitação em stack trace; (b) validar sem medir — a análise estática já se provou
insuficiente sozinha (ADR D6 do M2); (c) medir a cada execução com timeout — `re` não
suporta timeout sem thread, e thread dentro de hook é desproporcional; (d) aceitar sem
defesa e documentar — é o usuário pagando por decisão nossa.

**Consequências:** a carga fica mais lenta. Acontece uma vez por invocação, sobre entrada
curta — irrelevante. Regex legítima porém lenta é rejeitada: falso negativo de
configuração, preferível ao commit pendurado.

### D4 — Validar a forma antes do conteúdo; chave desconhecida é erro

**Decisão:** validação em camadas — tipo do topo, tipo de cada chave, conteúdo de cada
item. Chave desconhecida **falha**, com sugestão da chave mais próxima.

**Rationale:** `utils.py:56-57` valida o topo; `rule.go:64-70` valida a invariante básica
primeiro. Com três chaves, um `ignroe:` com erro de digitação seria ignorado em silêncio e
o usuário concluiria que a ferramenta não funciona — quando a config dele nunca foi lida.

**Alternativas consideradas:** (a) ignorar chave desconhecida — o silêncio custa uma sessão
de depuração; (b) avisar sem falhar — avisos em CLI rolam para cima e não são lidos; (c)
schema de terceiro (`pydantic`) — gastaria a segunda dependência num produto que autoriza
uma.

**Consequências:** config com chave a mais falha em vez de degradar. Desejado num arquivo
de três chaves.

### D5 — `ignore` age no walker; `allow` age no finding

**Decisão:** `ignore` é aplicado em `walker.walk`, antes de abrir o arquivo. `allow` e o
comentário inline são aplicados em `scanner`, depois do match.

**Rationale:** são otimizações e semânticas diferentes. `ignore` diz "não olhe aqui" — e
o ganho é não ler o arquivo, o que só existe se a decisão for tomada antes da leitura.
`allow` diz "este valor é conhecido" — e só pode ser avaliado depois de ter o valor. Trocar
os lugares faria `ignore` custar a leitura que ele existe para evitar.

**Alternativas consideradas:** (a) tudo no scanner — perde o ganho do `ignore` e faz o
walker devolver arquivos que serão descartados; (b) tudo no walker — impossível, `allow`
depende do valor encontrado; (c) uma terceira camada de filtro — indireção sem ganho
(`parsimony-ladder.md` rung 5).

**Consequências:** `walk()` passa a receber a config, mudando a assinatura pela primeira
vez desde o M0. `ScanResult` não muda.

### D6 — Arquivo ignorado **não** entra em `skipped`

**Decisão:** arquivo excluído por `ignore` não aparece na contagem de pulados da saída.

**Rationale:** o ADR D3 do M0 pôs o pulo no resultado porque o descarte era **decisão
nossa** e o usuário precisava vê-lo — heurística de binário e limite de tamanho podem
errar em silêncio. Um `ignore` é decisão **do usuário**, escrita por ele no arquivo dele;
reportá-la de volta é ruído. Confundir as duas coisas encheria a saída de linhas que o
usuário causou de propósito, e ruído mina a confiança tanto quanto falso positivo.

**Alternativas consideradas:** (a) contar junto com binário e grande — mistura decisão
nossa com decisão do usuário; (b) contar em categoria separada na saída — informação que
ninguém pediu, contra o `PRD § 4`; (c) contar apenas em modo verboso — não temos modo
verboso e criar um estouraria o teto de flags.

**Consequências:** um `ignore` largo demais esconde arquivos sem aviso. Mitigado por ser
decisão explícita do usuário, num arquivo que ele escreveu e pode reler.

## Drawbacks & Risks

| Drawback / Risco | Severidade | Mitigação | Dono |
|---|---|---|---|
| PyYAML vira superfície de CVE do produto | Alta | Pin com teto de major; `/deps-audit` em todo milestone; superfície de uso de **uma** função | dev |
| Regex do usuário pendura o `git commit` | Alta | D3: compila, analisa e **mede** na carga; rejeita antes de executar | dev |
| `allow` largo demais silencia detecção legítima | Alta | Documentar no README que `allow` é a última opção; o valor allowlistado aparece no erro quando a config falha | dev |
| `ignore` largo demais esconde arquivos sem aviso | Média | Aceito no ADR D6 — é decisão explícita do usuário | dev |
| Mudança de assinatura de `walk()` e `scan_path()` quebra chamador | Média | Parâmetro com default `None` = comportamento atual; testes do M0-M2 seguem verdes sem edição | dev |
| Custo de carregar e validar a config a cada invocação | Média | T3.1 mede; o hook invoca uma vez por commit | dev |
| Erro de digitação em chave passa em silêncio | Média | D4: chave desconhecida é erro, com sugestão da mais próxima | dev |

## Unresolved Questions

- Q1 — **Qual o teto de tempo para regex do usuário?** **Resolução adotada:** o mesmo do
  M2 — `0.05` s contra a pior entrada adversarial. Usar o mesmo número mantém a
  comparação direta com o catálogo embutido, e um teto diferente exigiria justificar por
  que a regra do usuário pode ser mais lenta que a nossa.
- Q2 — **`allow` aceita regex ou só texto exato?** O `README.md` já promete "texto exato
  ou regex". **Resolução adotada:** manter a promessa, e submeter o valor às **mesmas**
  verificações do `rules:` (D3) — um `allow` patológico penduraria o commit igual.
- Q3 — **A config deve valer para o `--staged` também?** **Resolução adotada:** sim, e é o
  caso que mais importa: o hook é onde o usuário sente o falso positivo. `scan_staged`
  recebe a config pelo mesmo caminho de `scan_path`.

## Dependency Graph

```
T1.1 (config.py — carregar, validar forma)
  └─> T1.2 (regex do usuário — compilar, analisar, medir)
        ├─> T2.1 (ignore no walker)
        ├─> T2.2 (allow + comentário inline no scanner)
        └─> T2.3 (--config na CLI, wiring)
              └─> T3.1 (benchmark do custo de carga)
```

## Dependencies

| Dependência | Escopo | Versão | Rule 9 |
|---|---|---|---|
| **`pyyaml`** | **runtime** | `>=6.0.1,<7` | **A única dependência de runtime do produto**, autorizada pelo `docs/PRD.md § NFR-1` e gasta aqui. Escrever parser de YAML é o anti-pattern literal da Regra 9. Piso `6.0.1` (não `6.0`) porque a `6.0` tinha problema de build com Cython 3; teto no major porque uma major nova pode mudar `safe_load` sem aviso. Superfície de uso: **uma função**. |
| `pytest` | dev | `>=9.0.3,<10` | Já declarado; piso por `GHSA-6w46-j5rx-g56g`. |
| `ruff` | dev | `>=0.6,<1` | Já declarado. |

**A partir do M3 o orçamento de dependências de runtime está esgotado.** Qualquer
dependência futura exige revisar o `NFR-1`.

---

## Phase 1: Carregar e validar

### T1.1 — `config.py`: carregar o YAML e validar a forma

#### Objective

Ler `.gitsafety.yml` com superfície mínima e falhar cedo, claro e com linha.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `config.py` com `load_config()` e a validação em camadas.
**Raciocínio:** é a fronteira do milestone. Tudo que vem depois assume config já validada,
e validar na fronteira é o que permite ao resto do código tratar os dados como confiáveis
(`rules/architecture.md § 1`).

#### Evidence

- `knowledge-base/references/ggshield/ggshield/core/config/utils.py:44-57` — carga, ausente, vazio, malformado, tipo do topo
- `knowledge-base/references/ggshield/ggshield/core/config/utils.py:113-121` — descoberta
- ADRs D1, D2, D4

#### Files to edit

- `src/gitsafety/config.py` (NOVO)
- `src/gitsafety/errors.py` (editar — `ConfigError`)
- `pyproject.toml` (editar — `dependencies = ["pyyaml>=6.0.1,<7"]`)

#### Deep file dependency analysis

`config.py` importa `yaml`, `pathlib`, `errors` e `patterns`. Consumido por T2.1-T2.3.
`errors.py` ganha `ConfigError`, que a invariante do M0 (`exit_code` obrigatório) cobre
automaticamente pelo `parametrize`.

#### Deep Dives

Três estados distintos que o código óbvio confunde:

1. **Arquivo ausente** → config vazia, sem erro (`FR-22`).
2. **Arquivo vazio** → `safe_load` devolve `None`; sem o `or {}` o código adiante quebra
   com `NoneType`.
3. **Arquivo com conteúdo não-dicionário** (uma lista, uma string) → erro, porque passa
   pelo parser e explode longe da origem.

Chave desconhecida merece sugestão: com três chaves, `difflib.get_close_matches` acha
`ignore` a partir de `ignroe` sem custo nem dependência.

#### Pseudo-code / Signatures

```python
CONFIG_FILENAME = ".gitsafety.yml"
KNOWN_KEYS = frozenset({"ignore", "allow", "rules"})

@dataclass(frozen=True)
class Config:
    ignore: tuple[str, ...] = ()
    allow: tuple[Pattern[str], ...] = ()
    rules: tuple[Rule, ...] = ()

def find_config(start: Path) -> Path | None: ...
def load_config(path: Path | None = None, *, start: Path | None = None) -> Config: ...
```

#### Tasks

1. `ConfigError` em `errors.py`, com `exit_code = USAGE_ERROR`.
2. `pyyaml` no `pyproject.toml`.
3. `find_config()` a partir da raiz do repositório, com fallback.
4. `load_config()` tratando ausente / vazio / malformado / não-dicionário.
5. Validação de chave desconhecida com sugestão.

#### TDD

```python
# tests/unit/test_config.py
def test_missing_config_file_returns_empty_config(tmp_path):
    # FR-22: a ferramenta funciona sem config
    cfg = load_config(start=tmp_path)
    assert cfg.ignore == () and cfg.allow == () and cfg.rules == ()

def test_empty_config_file_returns_empty_config(tmp_path):
    # edge case: safe_load de arquivo vazio devolve None
    (tmp_path / ".gitsafety.yml").write_text("")
    assert load_config(start=tmp_path).ignore == ()

def test_malformed_yaml_raises_with_the_line_number(tmp_path):
    # caso negativo: FR-23
    (tmp_path / ".gitsafety.yml").write_text("ignore:\n  - a\n   - b\n")
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "line" in str(exc.value).lower()

def test_top_level_list_is_rejected(tmp_path):
    # caso negativo: YAML válido, forma errada
    (tmp_path / ".gitsafety.yml").write_text("- a\n- b\n")
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)

def test_unknown_key_is_rejected_with_a_suggestion(tmp_path):
    # caso negativo: o silêncio custaria uma sessão de depuração
    (tmp_path / ".gitsafety.yml").write_text("ignroe:\n  - a\n")
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "ignore" in str(exc.value)

def test_config_error_carries_usage_exit_code(): ...
def test_ignore_must_be_a_list(tmp_path): ...
```

#### Acceptance Criteria

- [ ] Config ausente returns `Config()` vazia, sem levantar (FR-22)
- [ ] Arquivo vazio returns `Config()` vazia — `safe_load` devolve `None`
- [ ] YAML malformado raises `ConfigError` cuja mensagem contains `line`
- [ ] Topo que não é dicionário raises `ConfigError`
- [ ] Chave desconhecida raises `ConfigError` cuja mensagem contains a chave sugerida
- [ ] `ConfigError.exit_code` assert `== ExitCode.USAGE_ERROR`
- [ ] `grep "yaml\." src/gitsafety/config.py` outputs apenas `safe_load` (D1)

#### DoD

- [ ] Todos os testes de T1.1 passam
- [ ] `pyyaml` declarado com o pin exato do D1
- [ ] Commit atômico referenciando T1.1

---

### T1.2 — Regex do usuário: compilar, analisar, medir

#### Objective

Nenhuma regex do usuário chega ao motor sem passar pelas três verificações.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** validar cada padrão de `rules:` e `allow:` na carga.
**Raciocínio:** implementa o ADR D3, que é a decisão **sem precedente** deste milestone.
Vem logo após a carga porque é parte da validação de fronteira: um padrão que não passa
não deve sequer virar objeto.

#### Evidence

- `knowledge-base/references/gitleaks/config/config.go:124,127` — `MustCompile`, o que **não** fazer
- ADR D3
- `has_free_quantifier` do M2 (`src/gitsafety/patterns.py`)

#### Files to edit

- `src/gitsafety/config.py` (editar)

#### Deep file dependency analysis

Reusa `has_free_quantifier` de `patterns.py`, escrito no M2 para os nossos padrões. É a
mesma defesa, aplicada a uma origem diferente.

#### Deep Dives

A entrada adversarial precisa ser **genérica**, porque não sabemos o que o usuário
escreveu. Cadeias longas de um caractere repetido, de caracteres alternados, e de
caracteres que costumam aparecer em delimitadores cobrem os casos clássicos de
backtracking sem depender do padrão.

Medir uma vez por regra na carga é barato; o custo real é a **soma** sobre muitas regras
do usuário. T3.1 mede isso.

A mensagem de erro precisa dizer **qual** regra falhou e **por quê** — "regex inválida"
sem o id manda o usuário procurar em toda a config.

#### Pseudo-code / Signatures

```python
ADVERSARIAL_PROBE = ("a" * 5000, "ab" * 2500, "=" * 2500 + "'" * 2500)
USER_PATTERN_BUDGET_S = 0.05

def compile_user_pattern(raw: str, *, context: str) -> Pattern[str]: ...
```

#### Tasks

1. `compile_user_pattern()` com as três verificações.
2. Entrada adversarial genérica.
3. Mensagens de erro nomeando a regra e o motivo.

#### TDD

```python
def test_invalid_user_regex_raises_naming_the_rule(tmp_path):
    # caso negativo: gitleaks entraria em pânico aqui
    (tmp_path / ".gitsafety.yml").write_text(
        'rules:\n  - id: quebrada\n    pattern: "[unclosed"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "quebrada" in str(exc.value)

def test_user_regex_with_free_quantifier_is_rejected(tmp_path):
    # a defesa do M2, aplicada a origem não confiável
    (tmp_path / ".gitsafety.yml").write_text(
        'rules:\n  - id: larga\n    pattern: ".*"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "larga" in str(exc.value)

def test_pathological_user_regex_is_rejected_before_execution(tmp_path):
    # O NÚCLEO DO RISCO Nº 2 — sem precedente nos peers
    (tmp_path / ".gitsafety.yml").write_text(
        'rules:\n  - id: patologica\n    pattern: "(a{1,50}){1,50}b"\n')
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)

def test_well_formed_user_rule_is_accepted(tmp_path): ...
def test_allow_entries_go_through_the_same_checks(tmp_path): ...
def test_user_rule_without_id_is_rejected(tmp_path): ...
```

#### Acceptance Criteria

- [ ] Regex inválida raises `ConfigError` cuja mensagem contains o id da regra
- [ ] Regex com quantificador livre raises `ConfigError` — nunca chega ao motor
- [ ] Regex patológica raises `ConfigError` **antes** de qualquer varredura
- [ ] Regra bem formada é aceita e aparece em `Config.rules`
- [ ] Entradas de `allow:` passam pelas **mesmas** três verificações
- [ ] Regra sem `id` raises `ConfigError`

#### DoD

- [ ] Todos os testes de T1.2 passam
- [ ] `has_free_quantifier` reusado, não reimplementado
- [ ] Commit atômico referenciando T1.2

---

## Phase 2: Aplicar a config

### T2.1 — `ignore` no walker

#### Objective

Caminho ignorado não é aberto.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** `walk()` passa a receber os globs de `ignore`.
**Raciocínio:** implementa o ADR D5. O ganho do `ignore` é não ler o arquivo, e isso só
existe se a decisão for tomada antes da leitura.

#### Evidence

- ADRs D5 e D6
- `src/gitsafety/walker.py` — `walk()` devolve `(files, skipped)`

#### Files to edit

- `src/gitsafety/walker.py` (editar)

#### Deep file dependency analysis

`walk()` ganha parâmetro com default `None`, então os testes do M0 seguem verdes sem
edição. `scanner.scan_path` repassa.

#### Deep Dives

`Path.match` do stdlib não trata `**` como o glob do shell. `fnmatch` sobre o caminho
relativo em POSIX é o comportamento que o usuário espera de `tests/fixtures/**`.

O ADR D6 diz que o ignorado **não** entra em `skipped` — a lista existe para mostrar
decisão **nossa**, e `ignore` é decisão do usuário.

#### Pseudo-code / Signatures

```python
def walk(root: Path, ignore: Sequence[str] = ()) -> tuple[list[Path], list[SkippedFile]]: ...
```

#### Tasks

1. Parâmetro `ignore` com default vazio.
2. Casamento por `fnmatch` sobre o caminho relativo POSIX.
3. Ignorado fora de `skipped` (D6).

#### TDD

```python
def test_ignored_path_is_not_returned(tmp_path): ...
def test_ignored_path_does_not_appear_in_skipped(tmp_path):
    # ADR D6: skipped mostra decisão NOSSA, não a do usuário
    ...
def test_double_star_glob_matches_nested_paths(tmp_path):
    # edge case: `tests/fixtures/**` precisa alcançar subdiretórios
    ...
def test_empty_ignore_changes_nothing(tmp_path):
    # o default preserva o comportamento do M0
    ...
```

#### Acceptance Criteria

- [ ] Caminho casando um glob de `ignore` **não** aparece em `files`
- [ ] Caminho ignorado **não** aparece em `skipped` (D6)
- [ ] `tests/fixtures/**` alcança arquivo em subdiretório aninhado
- [ ] `walk(root)` sem `ignore` returns exatamente o que retornava no M0

#### DoD

- [ ] Todos os testes de T2.1 passam
- [ ] Testes do M0 sobre `walk` seguem verdes sem edição
- [ ] Commit atômico referenciando T2.1

---

### T2.2 — `allow` e comentário inline no scanner

#### Objective

Valor conhecido e linha marcada não geram finding.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** filtrar findings por `allow` e pelo comentário inline.
**Raciocínio:** ADR D5 — ambos só podem ser avaliados **depois** do match, porque dependem
do valor encontrado e da linha em que ele está.

#### Evidence

- `docs/PRD.md § FR-13, FR-14`
- ADR D5

#### Files to edit

- `src/gitsafety/scanner.py` (editar)
- `src/gitsafety/staged.py` (editar — mesmo filtro no modo staged, Unresolved Q3)

#### Deep file dependency analysis

O filtro precisa existir nos **dois** caminhos de varredura. Escrevê-lo uma vez e chamar
dos dois é DRY sobre conhecimento; duplicá-lo garantiria divergência na primeira mudança.

#### Deep Dives

O comentário inline é `# gitsafety: allow`, mas linguagens usam `//`, `--`, `#`. Procurar
a **substring** `gitsafety: allow` na linha, sem exigir o caractere de comentário, cobre
todas sem precisar saber a linguagem — e o falso positivo dessa abordagem (a string
aparecer fora de um comentário) é irrelevante, porque quem a escreve está pedindo a
supressão de qualquer forma.

O `allow` é uma lista de padrões já compilados em T1.2. Comparar por regex cobre também o
caso de texto exato, porque texto exato é um regex válido.

#### Pseudo-code / Signatures

```python
INLINE_ALLOW_MARKER = "gitsafety: allow"

def is_allowed(finding: Finding, line: str, allow: Sequence[Pattern[str]]) -> bool: ...
```

#### Tasks

1. `is_allowed()` num lugar só.
2. Chamada em `scanner._scan_text` e em `staged.scan_staged`.
3. Marcador inline.

#### TDD

```python
def test_allow_entry_suppresses_the_finding(tmp_path): ...
def test_allow_accepts_a_regex(tmp_path): ...
def test_inline_comment_suppresses_the_finding_on_that_line(tmp_path): ...
def test_inline_comment_does_not_suppress_other_lines(tmp_path):
    # caso negativo: a supressão é da LINHA, não do arquivo
    ...
def test_inline_marker_works_with_any_comment_character(tmp_path): ...
def test_allow_applies_to_the_staged_path_too(tmp_git_repo, stage):
    # Unresolved Q3: o hook é onde o falso positivo dói
    ...
```

#### Acceptance Criteria

- [ ] Valor em `allow:` não gera finding
- [ ] `allow:` aceita regex, não só texto exato
- [ ] `# gitsafety: allow` suprime o finding **daquela** linha
- [ ] A linha seguinte **continua** gerando finding
- [ ] O marcador funciona com `//` e `--`, não só `#`
- [ ] `allow` e marcador valem também em `scan --staged`

#### DoD

- [ ] Todos os testes de T2.2 passam
- [ ] `is_allowed` existe uma vez só, chamada dos dois caminhos
- [ ] Commit atômico referenciando T2.2

---

### T2.3 — `--config` na CLI

#### Objective

O usuário aponta outro arquivo, e a config chega aos dois modos de varredura.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** flag `--config` e wiring da config em `main`.
**Raciocínio:** é o wiring do milestone — sem ele, `config.py` é código morto. É a quarta
e última flag do teto do `docs/PRD.md § NFR-3`.

#### Evidence

- `docs/PRD.md § FR-21` — `--config PATH`
- `docs/PRD.md § NFR-3` — teto de 4 flags

#### Files to edit

- `src/gitsafety/cli.py` (editar)
- `README.md` (editar — `--config` migra para ✅)

#### Deep file dependency analysis

`cli.main` passa a chamar `load_config` antes de qualquer varredura, e a repassar a
`scan_path` / `scan_staged`. `ConfigError` já é `GitsafetyError`, então o `try` existente
o captura sem mudança.

#### Deep Dives

A config precisa ser carregada **antes** da varredura para que um erro de config apareça
imediatamente, e não depois de varrer mil arquivos.

Com `--config`, o arquivo é obrigatório: apontar para caminho inexistente é erro, ao
contrário do `.gitsafety.yml` implícito, cuja ausência é normal. São dois contratos
diferentes para o mesmo carregador.

#### Pseudo-code / Signatures

```python
scan.add_argument("--config", metavar="PATH", help="...")
```

#### Tasks

1. Flag `--config`.
2. Carga antes da varredura, repasse aos dois modos.
3. `--config` inexistente é erro; `.gitsafety.yml` ausente não é.

#### TDD

```python
def test_config_flag_loads_the_given_file(tmp_path): ...
def test_missing_explicit_config_is_an_error(tmp_path):
    # caso negativo: pedir um arquivo que não existe é erro de uso
    assert main(["scan", str(tmp_path), "--config", str(tmp_path / "nao-existe.yml")]) == 2

def test_malformed_config_exits_two_before_scanning(tmp_path):
    # o erro aparece antes de varrer mil arquivos
    ...
def test_help_now_advertises_config(capsys): ...
def test_scan_still_has_at_most_four_flags():
    # PRD § NFR-3
    ...
```

#### Acceptance Criteria

- [ ] `--config caminho.yml` carrega o arquivo indicado
- [ ] `--config` para arquivo inexistente returns exit `2`
- [ ] `.gitsafety.yml` ausente **não** é erro
- [ ] Config malformada returns exit `2` **antes** de varrer
- [ ] `--help` contains `--config`
- [ ] `scan` tem no máximo 4 flags (`PRD § NFR-3`)

#### DoD

- [ ] Todos os testes de T2.3 passam
- [ ] Wiring triad: `cli.main` chama `load_config`; testes funcionais cobrem a fronteira; o erro de config na saída é o sinal observável
- [ ] README com `--config` marcado como disponível
- [ ] Commit atômico referenciando T2.3

---

## Phase 3: Medição

### T3.1 — Benchmark do custo de carregar a config

#### Objective

Medir o que a config custa por invocação, e provar que não estraga o hook.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** medir carga com 0, 10 e 50 regras de usuário.
**Raciocínio:** o M1 mediu ~40 ms de overhead no commit e o M2 mostrou que o catálogo não
escala mal. A config acrescenta um custo **fixo** por invocação — parse do YAML mais a
medição adversarial de cada regra do usuário (D3). Como a medição é justamente o que
protege o commit, é preciso saber se ela própria não o atrasa.

#### Evidence

- `knowledge-base/implementations/m1-hook-pre-commit-implementation.md` — 40 ms de overhead
- ADR D3 — a medição adversarial acontece na carga
- `docs/PRD.md § NFR-2`

#### Files to edit

- `benchmarks/bench_config.py` (NOVO)
- `tests/functional/test_config_performance.py` (NOVO)

#### Deep file dependency analysis

Consome `load_config`. Não é importado por produção.

#### Deep Dives

O custo tem duas parcelas com formas diferentes: o parse do YAML é ~constante, e a
validação adversarial é **linear no número de regras do usuário**. Medir com 0, 10 e 50
separa as duas — e 50 regras de usuário é muito além do plausível, o que dá margem.

O número que importa é o custo somado ao overhead do hook: se a carga custar 10 ms, o
commit vai de 40 para 50 ms, e o `NFR-2` continua com 20× de folga.

#### Pseudo-code / Signatures

```python
def measure_load(n_user_rules: int, rounds: int = 5) -> dict[str, float]: ...
```

#### Tasks

1. Gerador de config com N regras válidas.
2. Medição com 0, 10, 50.
3. Teste de orçamento.

#### TDD

```python
def test_config_load_is_fast_enough_for_the_hook(tmp_path):
    m = measure_load(n_user_rules=10)
    assert m["total_s"] < 0.2, m      # o hook tem 1 s de teto e já gasta 0,04

def test_adversarial_validation_cost_is_linear_and_small(tmp_path):
    dez = measure_load(n_user_rules=10)
    cinquenta = measure_load(n_user_rules=50)
    assert cinquenta["total_s"] < dez["total_s"] * 10
```

#### Acceptance Criteria

- [ ] O benchmark outputs `total_s` para 0, 10 e 50 regras de usuário
- [ ] `assert m["total_s"] < 0.2` com 10 regras
- [ ] O custo com 50 regras é menos que 10× o de 10
- [ ] Os números ficam registrados em `knowledge-base/implementations/m3-config-yaml-implementation.md`
- [ ] O log declara o efeito somado ao overhead do hook medido no M1

#### DoD

- [ ] Os dois testes passam
- [ ] Números registrados com hardware e método
- [ ] Commit atômico referenciando T3.1

---

## Coverage Matrix

| # | Requisito (origem) | Task(s) | Como é resolvido |
|---|---|---|---|
| 1 | `ignore`, `allow`, `rules` implementadas (ROADMAP M3 DoD 1) | T1.1, T2.1, T2.2 | Carga + aplicação nos dois pontos certos (D5) |
| 2 | `# gitsafety: allow` suprime o finding da linha (ROADMAP M3 DoD 2) | T2.2 | Marcador por substring, agnóstico de linguagem |
| 3 | YAML malformado → exit 2 com a linha (ROADMAP M3 DoD 3) | T1.1, T2.3 | Duas classes de erro do PyYAML; `str(e)` preservado |
| 4 | Sem config a ferramenta funciona (ROADMAP M3 DoD 4) | T1.1 | Ausente devolve `Config()` vazia |
| 5 | `--config PATH` (ROADMAP M3 DoD 5) | T2.3 | Quarta e última flag |
| 6 | Regex inválida do usuário não derruba o processo (Risco M3 nº 2) | T1.2 | `try/except` com erro tipado nomeando a regra |
| 7 | Regex patológica do usuário não pendura o commit (Risco M3 nº 2) | T1.2 | Medição adversarial na carga; rejeição |
| 8 | Dependência de YAML pinada e com superfície mínima (Risco M3 nº 1) | T1.1 | `pyyaml>=6.0.1,<7`; só `safe_load` |
| 9 | Chave desconhecida não passa em silêncio (D4) | T1.1 | Erro com sugestão da chave mais próxima |
| 10 | Config vale no modo staged (Unresolved Q3) | T2.2, T2.3 | Mesmo filtro nos dois caminhos |
| 11 | Ignorado não vira ruído na saída (D6) | T2.1 | Fora de `skipped` |
| 12 | Chamadores do M0-M2 não quebram | T2.1, T2.2 | Parâmetros com default; testes anteriores verdes sem edição |
| 13 | Custo da config medido | T3.1 | 0, 10 e 50 regras de usuário |
| 14 | Teto de 4 flags respeitado (PRD NFR-3) | T2.3 | Teste que conta as flags |

**Cobertura: 14/14 requisitos mapeados (100%)**

## Global Definition of Done

- [ ] Os 5 itens de DoD do `ROADMAP.md § M3` verificados por teste automatizado
- [ ] Toda regra de negócio com teste unitário (`rules/testing.md § 3`)
- [ ] Casos negativos cobertos (`§ 4.1`)
- [ ] Nenhum `except Exception` genérico (`rules/error-handling.md § 5`)
- [ ] `yaml.` aparece apenas como `safe_load` no código de produção
- [ ] Wiring triad em T2.3
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] `/code-quality` com veredito ∈ {PASS, PASS_WITH_CAVEATS, FAIL_SOFT com ADR}
- [ ] Benchmark executado, números registrados
- [ ] README com `--config` disponível e `allow` documentado como última opção

## Failure scenarios

O M3 acrescenta uma fronteira: o **arquivo de configuração**, escrito pelo usuário.

| Recurso | Modo de falha | Como o teste reproduz | Comportamento esperado |
|---|---|---|---|
| `.gitsafety.yml` | Ausente | `tmp_path` sem o arquivo | `Config()` vazia; sem erro (FR-22) |
| `.gitsafety.yml` | Vazio | Arquivo em branco | `Config()` vazia — `safe_load` devolve `None` |
| `.gitsafety.yml` | YAML malformado | Indentação inconsistente | `ConfigError` com arquivo e linha; exit 2 |
| `.gitsafety.yml` | Topo não é dicionário | Uma lista no topo | `ConfigError` específico |
| `.gitsafety.yml` | Chave desconhecida | `ignroe:` | `ConfigError` com sugestão `ignore` |
| `.gitsafety.yml` | Tipo errado numa chave | `ignore: "string"` | `ConfigError` nomeando a chave |
| `rules:` do usuário | Regex inválida | `"[unclosed"` | `ConfigError` nomeando a regra; **nunca** stack trace |
| `rules:` do usuário | Quantificador livre | `".*"` | `ConfigError` nomeando a regra |
| `rules:` do usuário | Regex patológica | `"(a{1,50}){1,50}b"` | `ConfigError` **antes** de varrer |
| `--config` | Caminho inexistente | Apontar para arquivo ausente | Erro; ao contrário do implícito, o explícito é obrigatório |

**(sem I/O de rede — o M3 lê um arquivo local; git e sistema de arquivos já cobertos em M0 e M1)**

## Concurrency tests

**(none — single-threaded)** — o M3 lê um arquivo e compila padrões. Nenhuma thread,
async, lock ou estado compartilhado mutável. O ADR D3 rejeitou explicitamente a alternativa
de timeout por thread, por desproporção.

---

## Final Phase: Integration Validation (MANDATORY)

### Execution

```bash
.venv/bin/pytest -q
cd $(mktemp -d)
printf 'k = "AKIAIOSFODNN7EXAMPLE"\n' > app.py
printf 'ok = "AKIAIOSFODNN7EXAMPLE"  # gitsafety: allow\n' > marcado.py
gitsafety scan .; echo "exit=$?"                      # espera: 1 finding (só app.py)
printf 'allow:\n  - "AKIAIOSFODNN7EXAMPLE"\n' > .gitsafety.yml
gitsafety scan .; echo "exit=$?"                      # espera: 0 findings, exit 0
printf 'ignroe:\n  - x\n' > .gitsafety.yml
gitsafety scan .; echo "exit=$?"                      # espera: exit 2, sugere 'ignore'
printf 'rules:\n  - id: ruim\n    pattern: ".*"\n' > .gitsafety.yml
gitsafety scan .; echo "exit=$?"                      # espera: exit 2, nomeia 'ruim'
```

### Acceptance Criteria

- [ ] Suíte inteira verde
- [ ] O comentário inline suprime só a linha marcada
- [ ] `allow` suprime o valor em todos os arquivos
- [ ] Chave com erro de digitação returns exit `2` e sugere a correta
- [ ] Regex com quantificador livre returns exit `2` nomeando a regra
- [ ] Benchmark outputs os números de carga

### If Validation Fails

Voltar ao task pelo Coverage Matrix. Não seguir para `/code-quality` com item falhando.
