---
slug: m0-esqueleto-cli
milestone_id: M0
created_at: 2026-07-27
goal: Entregar uma CLI Python instalável que varre arquivos, aplica uma regra real de detecção e sai com o exit code correto, com suíte de testes verde e benchmark de latência.
---

# Plan: M0 — Esqueleto ponta a ponta da CLI

## Goal

Entregar `gitsafety scan <caminho>` como CLI Python instalável via `pip install -e .`,
que percorre arquivos de texto, aplica uma regra real de detecção (chave de acesso AWS),
imprime `arquivo:linha  regra  segredo-mascarado`, sai com exit code 0 / 1 / 2 conforme o
resultado, pula binários e arquivos acima de 1 MB **reportando o que pulou**, e tem suíte
de testes verde executável por um comando.

## Context

Primeiro milestone do `ROADMAP.md`. O repositório tem documentação e ecossistema de
ciclos, mas **nenhuma linha de código de produto**. Este plano cria a fundação sobre a
qual M1 (hook), M2 (catálogo de padrões), M3 (config YAML), M4 (notebooks) e M5
(histórico) empilham.

As decisões de forma já estão travadas pelo blueprint
`knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md`
(veredito SHIPPABLE 100.0), cujos 5 ADRs este plano consome como entrada, não como
sugestão.

## Baseline Context (deep review of current state)

**Estado do repositório:** branch `develop`, HEAD `48ddb90`, working tree limpo, zero
código de produto. Não existe `src/`, `tests/`, `pyproject.toml` nem `.github/`.

**Consequência para este plano:** não há invariante de código a preservar, nem chamador
existente a não quebrar. O risco de regressão é nulo; o risco real é de **forma errada**
— escolher um layout que M1-M5 tenham de desfazer. É por isso que o milestone foi
precedido de descoberta.

### Files that will be touched

| File | LoC hoje | Último commit | Por que existe hoje | Invariantes a preservar |
|---|---|---|---|---|
| `pyproject.toml` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/__init__.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/__main__.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/errors.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/rules.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/finding.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/_binary_extensions.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/walker.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/scanner.py` (NOVO) | 0 | — | (a criar) | — |
| `src/gitsafety/cli.py` (NOVO) | 0 | — | (a criar) | — |
| `tests/unit/*.py` (NOVOS) | 0 | — | (a criar) | — |
| `tests/functional/*.py` (NOVOS) | 0 | — | (a criar) | — |
| `benchmarks/bench_scan.py` (NOVO) | 0 | — | (a criar) | — |
| `.github/workflows/ci.yml` (NOVO) | 0 | — | (a criar) | — |
| `README.md` | 232 | `48ddb90` (2026-07-27) | Contrato público do produto | As 4 flags e os exit codes documentados NÃO podem divergir do implementado |
| `CHANGELOG.md` | 31 | `48ddb90` (2026-07-27) | Contrato de comunicação | Seção `[Unreleased]` recebe entrada por mudança visível |

### Current callers / dependents

Nenhum. Este é o primeiro código do produto. O único consumidor externo do M0 é o
próprio `README.md`, que já promete a interface — divergir dele é o único jeito de
quebrar alguém neste milestone.

### Domain glossary

- **Rule** — padrão de detecção nomeado: `id` + regex compilada. No M0 existe exatamente uma, `aws-access-key-id`.
- **Finding** — ocorrência de uma Rule em um arquivo: `rule_id`, `path`, `line` (1-based), `secret`.
- **Segredo mascarado** — representação de exibição de um Finding que preserva prefixo e sufixo e oculta o miolo; é a forma **padrão** de saída (`docs/PRD.md § NFR-4`).
- **Skipped** — arquivo deliberadamente não varrido, com motivo (`binary` ou `too_large`); faz parte do resultado, não é descarte silencioso (ADR D3).
- **ScanResult** — par `(findings, skipped)` devolvido por `scan_path()`.
- **ExitCode** — enum de código de saída: `0` limpo, `1` achou, `2` erro de uso.
- **Wiring triad** — caller real, teste de integração e sinal observável em runtime; exigido por `rules/cycle-implement.md` para cada task fechar.

### Architecture boundaries affected

Camadas conforme `rules/architecture.md § 1`, do interno para o externo:

```
domínio        errors.py, rules.py, finding.py, _binary_extensions.py
aplicação      walker.py, scanner.py
interface      cli.py, __main__.py
```

- Domínio não importa de aplicação nem de interface.
- `cli.py` é a única camada que conhece `argparse`, `sys.exit` e `print`.
- Nenhuma fronteira de infraestrutura no M0: sem rede, sem banco, sem fila. O sistema de
  arquivos é acessado por `walker.py` via `pathlib` da stdlib — DIP não se aplica
  (`rules/architecture.md § 2` proíbe abstração especulativa).

## Prior Art & Related Work

| Fonte | O que aproveitamos | Citação |
|---|---|---|
| Blueprint do M0 | Os 5 ADRs (D1-D5) são entrada travada deste plano | `knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md` |
| ggshield | Idioma de entry point `[project.scripts]` → `__main__:main` (o piso `>=3.9` deles foi **rejeitado** — ver ADR D8) | `knowledge-base/references/ggshield/pyproject.toml:33,67-68` |
| ggshield | Classificação de binário por extensão, sem sniffing | `knowledge-base/references/ggshield/ggshield/utils/files.py:131-134` |
| ggshield | Arquivo pulado devolvido em lista separada | `knowledge-base/references/ggshield/ggshield/core/scan/file.py:69-77` |
| ggshield | `ExitCode(IntEnum)` + exceção que carrega o código | `knowledge-base/references/ggshield/ggshield/core/errors.py:24-59` |
| ggshield | Dois níveis de teste compostos por um alvo | `knowledge-base/references/ggshield/Makefile:21-26` |
| gitleaks | Regra como dado com casos de acerto e não-acerto anexos | `knowledge-base/references/gitleaks/cmd/generate/config/rules/adafruit.go` |
| `rules/testing.md § 4.1` | Distinção edge case × negative case aplicada ao plano de teste | `rules/testing.md` |
| `rules/error-handling.md § 2` | Erros tipados que carregam contexto | `rules/error-handling.md` |
| `rules/parsimony-ladder.md` | Degraus 1-2 sustentam D5 (argparse) e D2 (sem detector de encoding) | `rules/parsimony-ladder.md` |

## Objective

Ao fim do M0, um desenvolvedor clona o repositório, roda `pip install -e .` e obtém um
comando `gitsafety` funcional que detecta uma chave AWS real em um arquivo, com todos os
cinco itens de DoD do `ROADMAP.md § M0` verificados por teste automatizado e um benchmark
de latência registrado.

## ADRs

D1-D5 vêm do blueprint e não são re-decididos aqui, mas são **restatados abaixo em forma
executável** — quem implementa não deve precisar abrir outro documento para saber o que
foi decidido. O texto integral (rationale longo, alternativas descartadas em detalhe,
consequências) está em
`knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md § ADRs`.
D6-D8 são deste plano.

### D1 — Binário é classificado por extensão, nunca por leitura de conteúdo

**Decisão:** `is_binary_path()` compara o sufixo do arquivo com um conjunto explícito.
Nenhum byte do arquivo é lido para classificá-lo.

**Rationale:** os dois peers legíveis convergem — ggshield usa conjunto de extensões
(`knowledge-base/references/ggshield/ggshield/utils/files.py:131-134`), gitleaks delega ao
git (`knowledge-base/references/gitleaks/sources/git.go:329`). Sniffing de byte NUL é o
risco nº 2 nomeado no `ROADMAP.md § M0` e ninguém na área o usa.

**Alternativas consideradas:** (a) sniffing de NUL nos primeiros N bytes — rejeitada, erra
em UTF-16 e é o risco declarado; (b) `charset-normalizer` para decidir se é texto —
rejeitada, ver D2; (c) delegar ao git como gitleaks — rejeitada, o M0 varre disco e
`docs/PRD.md § NFR-6` exige que `git` só seja necessário em `--staged` e `--history`.

**Consequências:** binário sem extensão conhecida é lido inutilmente (desperdício, não
erro); arquivo de texto com extensão da lista é pulado (falso negativo real, mitigado
pelo D3).

### D2 — Leitura com `utf-8` e `errors="replace"`, sem detector de encoding

**Decisão:** arquivos são lidos com `open(path, encoding="utf-8", errors="replace")`.
Nenhuma dependência de detecção de encoding.

**Rationale:** `knowledge-base/references/ggshield/pyproject.toml:36-39` documenta que um
bump de `charset-normalizer` para 3.2+ passou a mal decodificar UTF-8 válido e **degradou
a detecção de segredos em silêncio**. Importar essa classe de falha para cobrir uma cauda
que o M0 não tem contraria `rules/parsimony-ladder.md` rung 2.

**Alternativas consideradas:** (a) `charset-normalizer` como o ggshield — rejeitada pelo
precedente de degradação silenciosa e por gastar a única dependência autorizada pelo
`docs/PRD.md § NFR-1`; (b) `errors="strict"` pulando o que falhar — rejeitada, um byte
estranho viraria falso negativo do arquivo inteiro; (c) tentar utf-8 e cair para latin-1 —
rejeitada, latin-1 decodifica qualquer byte, então o fallback nunca falha e mascara o
problema.

**Consequências:** arquivo em UTF-16 tem caracteres substituídos e pode não casar padrão —
falso negativo aceito e declarado. `errors="replace"` nunca levanta exceção.

### D3 — Arquivo pulado é valor de retorno, não efeito colateral

**Decisão:** `walk()` devolve `(files, skipped)` e `scan_path()` devolve
`ScanResult(findings, skipped)`. Nenhum descarte silencioso.

**Rationale:** `knowledge-base/references/ggshield/ggshield/core/scan/file.py:69-77`
retorna `(files, binary_paths)` em vez de filtrar e esquecer. O `ROADMAP.md § M0` nomeia
"pular um arquivo por engano é um falso negativo silencioso"; como o D1 admite que a
heurística erra, a cura é tornar o erro visível, não perseguir uma heurística perfeita.

**Alternativas consideradas:** (a) filtrar e seguir — rejeitada, é o anti-pattern nomeado
no roadmap; (b) logar em nível debug — rejeitada, `rules/error-handling.md § 5`: log que
ninguém lê não é evidência.

**Consequências:** valor de retorno composto e uma linha de resumo na saída.

### D4 — `ExitCode(IntEnum)` fixo, carregado pela exceção

**Decisão:** `SUCCESS = 0`, `SECRETS_FOUND = 1`, `USAGE_ERROR = 2`. Cada exceção de
domínio carrega seu `exit_code`. Sem flag para configurar códigos.

**Rationale:** `knowledge-base/references/ggshield/ggshield/core/errors.py:24-59` mantém o
código junto do erro em vez de reconstruí-lo no `main` com cadeia de `if` — que é onde
esse tipo de código apodrece. Os três peers convergem em `0`/`1`; o `2` do ggshield é
precedente direto do `docs/PRD.md § FR-18`.

**Alternativas consideradas:** (a) inteiros literais no `main` — rejeitada, `2` sem nome
não diz nada em revisão; (b) flag `--exit-code` como o gitleaks
(`knowledge-base/references/gitleaks/cmd/detect.go:65`) — rejeitada, existe para acomodar
CI legado que não temos, e estoura o teto de 4 flags do `docs/PRD.md § NFR-3`; (c) copiar
os 6 códigos do ggshield — rejeitada, três descrevem falhas de backend remoto inexistente
aqui.

**Consequências:** um código novo exige entrada no enum e na exceção correspondente — que
é exatamente o ponto.

### D5 — `argparse` da stdlib, sem framework de CLI

**Decisão:** o M0 usa `argparse`. Nenhuma dependência de CLI.

**Rationale:** `docs/PRD.md § NFR-1` autoriza uma dependência externa, reservada ao parser
de YAML do M3. O ggshield usa `click` porque tem dezenas de subcomandos aninhados; o
gitsafety tem dois comandos e quatro flags (`docs/PRD.md § NFR-3`).
`rules/parsimony-ladder.md` rung 2: se a stdlib resolve, use a stdlib.

**Alternativas consideradas:** (a) `click` como o ggshield — rejeitada, gasta a única
dependência autorizada em algo que a stdlib faz; (b) `typer` — mesma objeção, com uma
camada a mais sobre `click`.

**Consequências:** sem `click.ClickException`, o D4 precisa de classe base própria com
atributo `exit_code` — cerca de 10 linhas, previstas em T1.2.

### D6 — Layout `src/` com pacote único, dividido por camada

**Decisão:** código em `src/gitsafety/`, com módulos nomeados por responsabilidade
(`errors`, `rules`, `finding`, `walker`, `scanner`, `cli`), não por tipo.

**Rationale:** o layout `src/` impede que testes importem o pacote do diretório de
trabalho em vez do instalado — o modo clássico de "passa local, quebra depois de
instalado", que atacaria diretamente o DoD nº 1 do M0 (`pip install -e .` funciona). A
divisão por camada segue `rules/architecture.md § 5` (package by layer) e é adequada
enquanto o produto tem uma feature; migrar para package-by-feature seria abstração
prematura com uma feature só (`rules/parsimony-ladder.md` rung 1).

**Alternativas consideradas:** (a) pacote na raiz sem `src/` — rejeitada, é justamente o
layout que mascara erro de empacotamento; (b) módulo único `gitsafety.py` — rejeitada,
M1-M5 empilham cinco áreas de responsabilidade e o arquivo viraria god module antes do
M2; (c) package-by-feature já no M0 — rejeitada, YAGNI com uma feature.

**Consequências:** `pyproject.toml` precisa declarar `package-dir`. Nove arquivos de
código no M0, todos pequenos — a contagem alta é consequência de SRP, não de
complexidade.

### D7 — `ScanResult` é um par nomeado (findings, skipped), não um iterável de findings

**Decisão:** `scan_path()` devolve um objeto com dois campos — `findings` e `skipped` —
em vez de retornar apenas findings.

**Rationale:** implementa o ADR D3 do blueprint. A assinatura óbvia
(`Iterator[Finding]`) torna o pulo de arquivo invisível por construção, e o
`ROADMAP.md § M0` nomeia "pular um arquivo por engano é um falso negativo silencioso"
como risco. Decidir isso agora evita quebrar a assinatura no M4, quando `.ipynb` grande
começar a ser pulado.

**Alternativas consideradas:** (a) retornar só findings e logar os pulos — rejeitada, log
que ninguém lê não é evidência (`rules/error-handling.md § 5`); (b) callback de
notificação de pulo — rejeitada, indireção sem ganho sobre um valor de retorno
(`rules/parsimony-ladder.md` rung 5).

**Consequências:** o chamador desempacota dois campos. A saída da CLI ganha uma linha de
resumo quando há pulos.

### D8 — Piso de Python sobe para 3.10; `pytest>=9.0.3`

**Decisão:** `requires-python = ">=3.10"` (não `>=3.9`, como o blueprint indicava a partir
do ggshield) e `pytest>=9.0.3,<10` como dependência de desenvolvimento.

**Rationale:** o `/deps-audit` deste plano encontrou `GHSA-6w46-j5rx-g56g` /
`PYSEC-2026-1845` — *"pytest through 9.0.2 on UNIX relies on directories with the
`/tmp/pytest-of-{user}` name pattern, which allows local users to cause a denial of
service or possibly gain privileges"*, vetor `CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:L`,
corrigido apenas em **9.0.3**. E `pytest 9.x` exige **Python >=3.10**. Em 3.9 é,
portanto, impossível instalar um pytest não vulnerável.

O dado que resolve o impasse: **Python 3.9 chegou a EOL em 2025-10-31** (verificado em
`endoflife.date/api/python.json` em 2026-07-27) — nove meses sem correção de segurança.
Um produto cuja única razão de existir é segurança não pode declarar suporte a um
interpretador que não recebe mais patch. O piso 3.9 herdado do ggshield descrevia a
realidade *deles*, não uma recomendação.

3.10 é o **menor** piso que resolve o CVE, e cobre o Python de sistema do Ubuntu 22.04 —
o que importa porque a north-star do `ROADMAP.md` é retenção, e retenção depende de
instalar sem atrito.

**Alternativas consideradas:** (a) manter 3.9 e allowlistar o CVE com sunset — rejeitada:
allowlist para conviver com vulnerabilidade evitável é workaround, e o problema de fundo
(interpretador EOL) continuaria; (b) piso 3.11 — rejeitada: mais seguro na margem, mas
exclui o Ubuntu 22.04 sem resolver nada que 3.10 já não resolva; (c) piso 3.9 no runtime
e 3.10 só no desenvolvimento — rejeitada: se a suíte nunca roda em 3.9, afirmar suporte a
3.9 é afirmação sem evidência (Regra Inquebrável 3).

**Consequences:** `docs/PRD.md § NFR-1` e o `README.md` mudam de "3.9 ou superior" para
"3.10 ou superior" — o M0 é o momento certo, antes de existir usuário. A matriz de CI
passa a ser 3.10 (piso) e 3.13 (moderno). O achado Q1 do blueprint (ggshield em `>=3.9`)
continua verdadeiro; divergimos dele conscientemente. **Python 3.10 chega a EOL em
2026-10-31** — revisar o piso no `cycle-analysis` pós-release.

## Drawbacks & Risks

| Drawback / Risco | Severidade | Mitigação | Dono |
|---|---|---|---|
| Classificação por extensão gera **falso negativo** em arquivo de texto com extensão de binário | Média | Aceito e declarado no ADR D1; mitigado pelo D3 (o arquivo pulado aparece na saída, então o usuário vê e pode agir) | dev |
| `errors="replace"` faz arquivo em UTF-16 não casar padrão | Média | Aceito e declarado no ADR D2; registrar no README ao fechar o M0 como limitação conhecida; revisável no M4 | dev |
| Regex de detecção com backtracking catastrófico trava o commit no M1 | Alta | A regra do M0 (`AKIA[0-9A-Z]{16}`) é linear e sem alternância aninhada; T3.3 mede o tempo e o teste de benchmark falha se exceder o orçamento | dev |
| Nove módulos para um produto que ainda faz uma coisa parecem over-engineering em revisão | Baixa | Cada módulo tem uma razão de mudar declarada no D6; o teste é a pergunta "M2 forçaria a dividir isto?" — para todos, sim | dev |
| Contagem de linha off-by-one entre arquivos com e sem newline final | Média | Teste de borda explícito em T2.4 com arquivo sem `\n` final | dev |
| Benchmark rodando em CI compartilhado produz número não comparável entre execuções | Média | O benchmark do M0 valida **orçamento absoluto** (limite superior generoso), não regressão relativa; comparação entre execuções fica para o `cycle-analysis` pós-release | dev |

## Unresolved Questions

- Q1 — Qual o orçamento de latência aceitável para o M0?** O `docs/PRD.md § NFR-2` fixa
  `< 1 s` para um commit típico, mas isso é do M1 (arquivos em stage). Para o M0
  (varredura de diretório) não há número declarado. **Resolução adotada:** T3.3 mede e
  registra o número real; o teste de orçamento assert `total_s < 5.0` para 1.000
  arquivos — folgado de propósito, para falhar só em regressão de ordem de grandeza e não
  em ruído de máquina. Revisável no `cycle-analysis` quando houver série histórica.
- Q2 — O `README.md` promete `--history` e `--staged`, que só existem em M5 e M1.**
  **Resolução adotada:** o M0 implementa `scan` sem essas flags e o teste
  `test_help_does_not_advertise_flags_that_do_not_exist_yet` assert que a saída de
  `gitsafety scan --help` não contains `--history` nem `--staged`. Nenhuma flag
  documentada-mas-inexistente.
- Q3 — Python 3.10 chega a EOL em 2026-10-31, três meses após este plano.** O ADR D8
  escolheu 3.10 como piso por ser o menor que permite `pytest>=9.0.3`. **Resolução
  adotada:** manter 3.10 no M0 e reavaliar o piso no `cycle-analysis` pós-release, com o
  dado de qual versão os usuários reais têm. Elevar o piso é mudança de uma linha em
  `pyproject.toml`; escolher errado agora, sem dado, seria adivinhação.

## Dependency Graph

```
T1.1 (pyproject + esqueleto do pacote)
  └─> T1.2 (errors.py — ExitCode + hierarquia)
        ├─> T2.1 (rules.py — Rule + regra AWS)
        ├─> T2.2 (finding.py — Finding + mascaramento)
        │     └─> T2.3 (walker.py — travessia + pulos)   [precisa de T2.1? não]
        │           └─> T2.4 (scanner.py — orquestra walker + rules)
        │                 └─> T3.1 (cli.py — argparse + render + exit)
        │                       ├─> T3.2 (CI)
        │                       └─> T3.3 (benchmark)
```

Ordem de execução: T1.1 → T1.2 → T2.1 → T2.2 → T2.3 → T2.4 → T3.1 → T3.2 → T3.3.

## Dependencies

Dependências declaradas para `/deps-audit`. O `docs/PRD.md § NFR-1` autoriza **uma**
dependência externa de runtime, reservada ao parser de YAML do M3.

| Dependência | Escopo | Versão | Rule 9 (por que não reinventar / por que não usar) |
|---|---|---|---|
| *(nenhuma)* | runtime | — | **O M0 não adiciona nenhuma dependência de runtime.** `argparse`, `pathlib`, `re`, `enum`, `dataclasses` da stdlib cobrem tudo (ADR D5 + `parsimony-ladder.md` rung 2). |
| `pytest` | dev | `>=9.0.3,<10` | Framework de teste padrão do ecossistema Python; escrever runner próprio é o anti-pattern nomeado na Regra 9. **Piso em 9.0.3 obrigatório:** versões até 9.0.2 carregam `GHSA-6w46-j5rx-g56g` / `PYSEC-2026-1845` (manipulação vulnerável de tmpdir em UNIX). Ver ADR D8. |

Nenhuma dependência de runtime significa: nenhuma superfície de CVE de terceiro
introduzida pelo M0, e nada a auditar além do `pytest` de desenvolvimento.

### Resultado do `/deps-audit` (2026-07-27)

| Verificação | Resultado |
|---|---|
| Dependências de runtime | 0 — nada a auditar |
| `pytest` consultado em OSV (`api.osv.dev`) | 2 avisos na faixa originalmente planejada (`>=8.0,<9`): `GHSA-6w46-j5rx-g56g` e `PYSEC-2026-1845` (o mesmo defeito, duas bases) |
| Faixa vulnerável | tudo até **9.0.2**, inclusive toda a série 8.x |
| Versão corrigida | **9.0.3** (disponível no PyPI; última é 9.1.1) |
| Ação tomada | Piso elevado para `>=9.0.3`. **Sem entrada de allowlist** — o CVE foi eliminado, não tolerado |
| Efeito colateral | `pytest 9.x` exige Python >=3.10 → motivou o ADR D8 |

**Veredito: PASS** — nenhuma dependência declarada permanece com CVE conhecido.

---

## Phase 1: Fundação — pacote instalável e contrato de erro

### T1.1 — Empacotamento e esqueleto do pacote

#### Objective

`pip install -e .` expõe o comando `gitsafety` no PATH e `gitsafety --version` responde.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `pyproject.toml` com `[project.scripts]` e o pacote vazio em `src/`.
**Raciocínio:** é o DoD nº 1 do M0 e o risco nº 1 do roadmap ("empacotamento consumir
mais tempo que a detecção"). O blueprint reduziu esse risco a duas linhas copiáveis de
`ggshield/pyproject.toml:67-68`. Fazer primeiro converte o maior risco declarado do
milestone no primeiro item resolvido — se o empacotamento falhar, falha barato, com zero
lógica escrita em cima.

#### Evidence

- `knowledge-base/references/ggshield/pyproject.toml:33` — `requires-python = ">=3.9"`
- `knowledge-base/references/ggshield/pyproject.toml:67-68` — `[project.scripts]` →
  `ggshield = "ggshield.__main__:main"`

#### Files to edit

- `pyproject.toml` (NOVO)
- `src/gitsafety/__init__.py` (NOVO) — expõe `__version__`
- `src/gitsafety/__main__.py` (NOVO) — `main()` mínimo que imprime a versão

#### Deep file dependency analysis

Nenhum arquivo existente é tocado. `pyproject.toml` na raiz é lido por `pip`; o
`package-dir = {"" = "src"}` é o que faz o layout `src/` funcionar (ADR D6).

#### Deep Dives

O modo de falha silenciosa aqui é o pacote resolver do diretório de trabalho em vez do
instalado. O teste de T1.1 roda `gitsafety --version` como **subprocesso**, a partir de
um diretório de trabalho diferente da raiz do repositório — se o layout `src/` estiver
mal declarado, o subprocesso falha, e é exatamente o que se quer detectar.

#### Pseudo-code / Signatures

```toml
[project]
name = "gitsafety"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
gitsafety = "gitsafety.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]
```

```python
# src/gitsafety/__main__.py
def main() -> int: ...
```

#### Tasks

1. Escrever `pyproject.toml` com metadados, `requires-python`, `[project.scripts]` e
   `packages.find` apontando para `src`.
2. Criar `src/gitsafety/__init__.py` com `__version__ = "0.1.0"`.
3. Criar `src/gitsafety/__main__.py` com `main()` que imprime a versão e devolve 0.

#### TDD

```python
# tests/functional/test_installed_entry_point.py
def test_installed_command_reports_version_from_outside_the_repo(tmp_path):
    # Arrange — cwd fora da raiz do repositório, para que só o pacote instalado resolva
    # Act
    result = subprocess.run(["gitsafety", "--version"], cwd=tmp_path,
                            capture_output=True, text=True)
    # Assert
    assert result.returncode == 0
    assert __version__ in result.stdout

def test_package_is_importable_after_install():
    # Arrange / Act
    import gitsafety
    # Assert
    assert gitsafety.__version__
```

RED: ambos falham (comando inexistente). GREEN: criar os três arquivos e instalar.

#### Acceptance Criteria

- [ ] `pip install -e .` termina com código 0 em Python 3.10
- [ ] `gitsafety --version` executado a partir de `/tmp` imprime a versão e sai com 0
- [ ] `python -c "import gitsafety; print(gitsafety.__version__)"` funciona

#### DoD

- [ ] Os dois testes acima passam
- [ ] `CHANGELOG.md` `[Unreleased] § Added` registra a CLI instalável
- [ ] Commit atômico referenciando T1.1

---

### T1.2 — Contrato de erro: `ExitCode` e hierarquia de exceções

#### Objective

Todo erro do gitsafety é uma exceção tipada que carrega seu próprio exit code.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `errors.py` com `ExitCode(IntEnum)` e a classe base que carrega o código.
**Raciocínio:** o ADR D4 do blueprint decidiu o mecanismo, e ele precisa existir **antes**
de qualquer código que possa falhar — caso contrário cada módulo inventa sua forma de
sinalizar erro e a unificação vira refactor. Vem logo após T1.1 porque é o segundo item
sem dependência de lógica de negócio.

#### Evidence

- `knowledge-base/references/ggshield/ggshield/core/errors.py:24-44` — `ExitCode(IntEnum)`
  com `SUCCESS = 0`, `SCAN_FOUND_PROBLEMS = 1`, `USAGE_ERROR = 2`
- `knowledge-base/references/ggshield/ggshield/core/errors.py:47-59` — `_ExitError` base
  que recebe `exit_code` no `__init__`
- `rules/error-handling.md § 2` — erros explícitos e tipados, com contexto

#### Files to edit

- `src/gitsafety/errors.py` (NOVO)

#### Deep file dependency analysis

Módulo de domínio puro: importa só de `enum`. Nada importa dele ainda; T2.3, T2.4 e T3.1
passam a importar.

#### Deep Dives

O ggshield herda de `click.ClickException` porque usa `click`. Sem `click` (ADR D5), a
classe base é `Exception` com um atributo `exit_code` — a tradução custa ~10 linhas e
está declarada como consequência no ADR D5 do blueprint.

Nenhuma exceção do gitsafety deve mapear para `UNEXPECTED_ERROR = 128` no M0: o M0 tem
duas condições de erro (caminho inexistente e uso inválido), ambas `USAGE_ERROR`.
Adicionar códigos sem caso de uso é YAGNI.

#### Pseudo-code / Signatures

```python
class ExitCode(IntEnum):
    SUCCESS = 0
    SECRETS_FOUND = 1
    USAGE_ERROR = 2

class GitsafetyError(Exception):
    exit_code: ExitCode
    def __init__(self, message: str) -> None: ...

class UsageError(GitsafetyError):      # exit_code = USAGE_ERROR
class PathNotFoundError(UsageError):   # mensagem com o caminho
```

#### Tasks

1. `ExitCode(IntEnum)` com os três códigos.
2. `GitsafetyError` base com atributo `exit_code`.
3. `UsageError` e `PathNotFoundError`, com mensagem contendo o caminho ofensor.

#### TDD

```python
# tests/unit/test_errors.py
def test_exit_codes_match_the_documented_contract():
    assert (ExitCode.SUCCESS, ExitCode.SECRETS_FOUND, ExitCode.USAGE_ERROR) == (0, 1, 2)

def test_path_not_found_error_carries_usage_exit_code():
    err = PathNotFoundError("/nao/existe")
    assert err.exit_code == ExitCode.USAGE_ERROR

def test_path_not_found_error_message_names_the_offending_path():
    # negative case (rules/testing.md § 4.1): mensagem específica, não genérica
    err = PathNotFoundError("/nao/existe")
    assert "/nao/existe" in str(err)
```

RED: `ImportError`. GREEN: criar o módulo.

#### Acceptance Criteria

- [ ] `ExitCode.SUCCESS == 0`, `SECRETS_FOUND == 1`, `USAGE_ERROR == 2`
- [ ] Toda subclasse de `GitsafetyError` tem `exit_code` não nulo
- [ ] A mensagem de `PathNotFoundError` contém o caminho recebido

#### DoD

- [ ] Os três testes passam
- [ ] Nenhum `except Exception` genérico introduzido (`rules/error-handling.md § 5`)
- [ ] Commit atômico referenciando T1.2

---

## Phase 2: Motor de detecção

### T2.1 — `Rule` e a regra de chave de acesso AWS

#### Objective

Uma regra é um dado nomeado com regex compilada e casos de acerto e não-acerto anexos.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `rules.py` com a dataclass `Rule`, a constante `BUILTIN_RULES` e a regra
`aws-access-key-id`. **Raciocínio:** a recomendação nº 7 do blueprint exige que o M0
nasça no formato que o M2 vai escalar para ≥ 40 regras. Escolher agora a forma "regra é
dado com casos anexos" (precedente `gitleaks/.../adafruit.go`) custa o mesmo que
escolher "regex solto" e evita reescrever 40 regras depois.

#### Evidence

- `knowledge-base/references/gitleaks/cmd/generate/config/rules/adafruit.go` — `RuleID`,
  `Description`, `Regex`, `Keywords` e `utils.Validate(r, tps, fps)` com positivos e
  negativos na própria definição
- `rules/testing.md § 4.1` — edge case × negative case

#### Files to edit

- `src/gitsafety/rules.py` (NOVO)

#### Deep file dependency analysis

Domínio puro: importa `re` e `dataclasses`. Consumido por T2.4.

#### Deep Dives

O padrão `AKIA[0-9A-Z]{16}` é literal seguido de classe de caracteres com quantificador
fixo — sem alternância, sem grupo aninhado, sem quantificador aninhado. Não tem
backtracking catastrófico por construção, o que é o mitigante declarado do risco de
performance nos Drawbacks.

`re.compile` na definição do módulo (não a cada chamada) é o que mantém o custo por
arquivo em O(tamanho do arquivo) em vez de recompilar por invocação.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: Pattern[str]

AWS_ACCESS_KEY_ID = Rule(
    id="aws-access-key-id",
    description="Identificador de chave de acesso da AWS",
    pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
)
BUILTIN_RULES: tuple[Rule, ...] = (AWS_ACCESS_KEY_ID,)
```

#### Tasks

1. Dataclass `Rule` congelada.
2. Regra `aws-access-key-id` com regex compilada.
3. `BUILTIN_RULES` como tupla imutável.

#### TDD

```python
# tests/unit/test_rules.py
# Acerto (true positives)
@pytest.mark.parametrize("texto", [
    "AKIAIOSFODNN7EXAMPLE",
    'aws_key = "AKIAIOSFODNN7EXAMPLE"',
    "export AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF",
])
def test_aws_rule_matches_a_real_access_key_id(texto):
    assert AWS_ACCESS_KEY_ID.pattern.search(texto)

# Não-acerto (false positives) — a metade que a maioria das suítes esquece
@pytest.mark.parametrize("texto", [
    "AKIA",                      # prefixo sozinho
    "AKIAIOSFODNN7EXAMPL",       # 15 caracteres — um a menos (edge case)
    "AKIAiosfodnn7example",      # minúsculas
    "NOTAKIAIOSFODNN7EXAMPLE1",  # prefixo não delimitado à esquerda
])
def test_aws_rule_does_not_match_near_misses(texto):
    assert AWS_ACCESS_KEY_ID.pattern.fullmatch(texto) is None

def test_builtin_rules_have_unique_ids():
    ids = [r.id for r in BUILTIN_RULES]
    assert len(ids) == len(set(ids))
```

RED: `ImportError`. GREEN: criar o módulo.

#### Acceptance Criteria

- [ ] `test_aws_rule_matches_a_real_access_key_id` passa nas 3 formas listadas
- [ ] `test_aws_rule_does_not_match_near_misses` assert `pattern.fullmatch(t) is None` nos 4 quase-acertos
- [ ] `BUILTIN_RULES` não tem `id` duplicado
- [ ] `isinstance(AWS_ACCESS_KEY_ID.pattern, re.Pattern)` — compilada no import, não por chamada

#### DoD

- [ ] Todos os testes de T2.1 passam, incluindo os negativos
- [ ] Commit atômico referenciando T2.1

---

### T2.2 — `Finding` e mascaramento do segredo

#### Objective

Um Finding sabe se exibir sem vazar o segredo que encontrou.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `finding.py` com a dataclass e a função de mascaramento.
**Raciocínio:** o `docs/PRD.md § NFR-4` exige que o segredo apareça mascarado **por
padrão** em toda saída — o relatório não pode virar o próximo vazamento. Implementar o
mascaramento no objeto que carrega o segredo, e não no renderizador, torna impossível
esquecer de mascarar em um caminho de saída futuro (M1 hook, M5 histórico).

#### Evidence

- `docs/PRD.md § NFR-4` — "a saída não vaza; segredo mascarado por padrão"
- `docs/PRD.md § FR-15, FR-16` — forma da saída e `--show-secrets`

#### Files to edit

- `src/gitsafety/finding.py` (NOVO)

#### Deep file dependency analysis

Domínio puro: `dataclasses` e `pathlib`. Consumido por T2.4 e renderizado por T3.1.

#### Deep Dives

Mascarar preservando prefixo e sufixo é útil para o usuário reconhecer **qual** chave é,
sem expor o valor. Mas segredo curto não tem miolo para ocultar: mascarar
`"AKIA"` preservando 4 na frente e 4 atrás não oculta nada. A regra precisa de um piso —
abaixo de N caracteres, mascarar tudo. Esse é o edge case central deste task.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: Path
    line: int          # 1-based
    secret: str
    @property
    def masked_secret(self) -> str: ...

def mask(secret: str, *, keep: int = 4) -> str: ...
```

#### Tasks

1. Dataclass `Finding` congelada com linha 1-based.
2. `mask()` preservando `keep` no início e no fim, com piso de segurança.
3. Propriedade `masked_secret` no `Finding`.

#### TDD

```python
# tests/unit/test_finding.py
def test_mask_preserves_head_and_tail_and_hides_the_middle():
    assert mask("AKIAIOSFODNN7EXAMPLE") == "AKIA" + "•" * 12 + "MPLE"

@pytest.mark.parametrize("curto", ["", "a", "AKIA", "AKIAIOSF"])
def test_mask_hides_everything_when_secret_is_too_short_to_keep_edges(curto):
    # edge case: sem miolo suficiente, preservar bordas exporia o segredo inteiro
    assert set(mask(curto)) <= {"•"}

def test_masked_length_never_reveals_more_than_the_original():
    assert len(mask("AKIAIOSFODNN7EXAMPLE")) == len("AKIAIOSFODNN7EXAMPLE")

def test_finding_exposes_masked_secret_by_default():
    f = Finding("aws-access-key-id", Path("a.py"), 3, "AKIAIOSFODNN7EXAMPLE")
    assert "IOSFODNN7EXA" not in f.masked_secret
```

RED: `ImportError`. GREEN: criar o módulo.

#### Acceptance Criteria

- [ ] `mask` preserva 4 no início e 4 no fim para segredo de 20 caracteres
- [ ] `mask` oculta **integralmente** segredo com ≤ 2×`keep` caracteres
- [ ] `len(mask(s)) == len(s)` para todo `s` do parametrize
- [ ] `Finding.masked_secret` nunca contém o miolo do segredo

#### DoD

- [ ] Todos os testes de T2.2 passam
- [ ] Nenhum caminho de código expõe `Finding.secret` sem passar por `--show-secrets`
- [ ] Commit atômico referenciando T2.2

---

### T2.3 — `walker`: travessia com pulos reportados

#### Objective

A travessia devolve os arquivos a varrer **e** os arquivos pulados, com o motivo de cada
pulo.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `walker.py` e `_binary_extensions.py`.
**Raciocínio:** implementa os ADRs D1 (extensão, não sniffing) e D3 (pulo é resultado) do
blueprint, que juntos endereçam o risco nº 2 do `ROADMAP.md § M0`. Vem antes do scanner
porque o scanner consome sua saída.

#### Evidence

- `knowledge-base/references/ggshield/ggshield/utils/files.py:131-134` — `is_path_binary`
  por extensão
- `knowledge-base/references/ggshield/ggshield/utils/_binary_extensions.py` — conjunto em
  módulo de dados dedicado, 213 linhas, ordenado
- `knowledge-base/references/ggshield/ggshield/core/scan/file.py:69-77` — retorno de
  `(files, binary_paths)`
- `knowledge-base/references/gitleaks/detect/files.go:55-60` — limite por tamanho

#### Files to edit

- `src/gitsafety/_binary_extensions.py` (NOVO) — conjunto ordenado de extensões
- `src/gitsafety/walker.py` (NOVO)

#### Deep file dependency analysis

`walker.py` importa `errors.py` (T1.2) para `PathNotFoundError` e `_binary_extensions`.
Consumido por T2.4.

#### Deep Dives

Ordem das decisões de pulo importa para o custo: **extensão primeiro, tamanho depois**.
Checar extensão é uma consulta em conjunto sem tocar o disco; checar tamanho é um
`stat()`. Inverter a ordem faz um `stat()` desnecessário em todo binário — desperdício
proporcional ao número de arquivos.

O limite de 1 MB vem do `README.md`; é fixo no M0 (sem flag), conforme o teto de 4 flags
do `docs/PRD.md § NFR-3` e o ADR D4 (nada configurável sem caso de uso).

Caminho inexistente é **erro de uso**, não lista vazia: retornar vazio silenciosamente
faz `gitsafety scan /caminho/digitado/errado` sair com 0 e o usuário concluir que está
limpo. É o falso negativo mais caro possível e o `rules/error-handling.md § 2` manda
validar na fronteira.

#### Pseudo-code / Signatures

```python
class SkipReason(str, Enum):
    BINARY = "binary"
    TOO_LARGE = "too_large"

@dataclass(frozen=True)
class SkippedFile:
    path: Path
    reason: SkipReason

MAX_FILE_BYTES = 1_000_000

def is_binary_path(path: Path) -> bool: ...
def walk(root: Path) -> tuple[list[Path], list[SkippedFile]]: ...
```

#### Tasks

1. `_binary_extensions.py` com conjunto ordenado (imagens, vídeo, áudio, comprimidos,
   executáveis, fontes, artefatos compilados).
2. `SkipReason` e `SkippedFile`.
3. `is_binary_path()` por sufixo.
4. `walk()` devolvendo `(files, skipped)`, com extensão checada antes de tamanho.
5. `PathNotFoundError` quando a raiz não existe.

#### TDD

```python
# tests/unit/test_walker.py
def test_walk_returns_text_files_to_scan(tmp_path): ...

def test_walk_reports_binary_file_as_skipped_instead_of_dropping_it(tmp_path):
    # o risco nº 2 do roadmap: o pulo precisa ser visível
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    files, skipped = walk(tmp_path)
    assert files == []
    assert [s.reason for s in skipped] == [SkipReason.BINARY]

def test_walk_reports_oversized_file_as_skipped(tmp_path):
    (tmp_path / "big.txt").write_text("x" * (MAX_FILE_BYTES + 1))
    files, skipped = walk(tmp_path)
    assert [s.reason for s in skipped] == [SkipReason.TOO_LARGE]

def test_file_at_exactly_the_limit_is_scanned_not_skipped(tmp_path):
    # edge case: fronteira inclusiva
    (tmp_path / "edge.txt").write_text("x" * MAX_FILE_BYTES)
    files, skipped = walk(tmp_path)
    assert len(files) == 1 and skipped == []

def test_walk_raises_typed_error_when_root_does_not_exist(tmp_path):
    # negative case: nunca retornar vazio em silêncio
    with pytest.raises(PathNotFoundError) as exc:
        walk(tmp_path / "inexistente")
    assert "inexistente" in str(exc.value)

def test_binary_extension_is_checked_before_file_size(tmp_path):
    # binário grande é pulado por BINARY, não por TOO_LARGE — prova a ordem
    (tmp_path / "big.png").write_bytes(b"\x00" * (MAX_FILE_BYTES + 1))
    _, skipped = walk(tmp_path)
    assert skipped[0].reason == SkipReason.BINARY
```

RED: `ImportError`. GREEN: criar os módulos.

#### Acceptance Criteria

- [ ] `walk()` devolve tupla `(files, skipped)`, nunca só arquivos
- [ ] Arquivo com extensão binária aparece em `skipped` com motivo `BINARY`
- [ ] Arquivo acima de 1 MB aparece em `skipped` com motivo `TOO_LARGE`
- [ ] `test_file_at_exactly_the_limit_is_scanned_not_skipped`: arquivo de `1_000_000` bytes returns em `files` e `skipped == []`
- [ ] Raiz inexistente levanta `PathNotFoundError` com o caminho na mensagem
- [ ] Binário grande é classificado como `BINARY` (prova que extensão precede tamanho)

#### DoD

- [ ] Todos os testes de T2.3 passam, incluindo os dois edge cases de fronteira
- [ ] Nenhum arquivo é descartado sem entrar em `skipped`
- [ ] Commit atômico referenciando T2.3

---

### T2.4 — `scanner`: orquestra travessia e regras

#### Objective

`scan_path()` devolve `ScanResult(findings, skipped)` para um diretório ou arquivo.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `scanner.py` com `ScanResult` e `scan_path()`.
**Raciocínio:** é a camada de aplicação que compõe T2.1 (regras), T2.2 (findings) e T2.3
(travessia). Implementa o ADR D7. Precisa vir antes da CLI porque a CLI só traduz seu
resultado em texto e código de saída — mantendo `rules/architecture.md § 1` (interface
não contém regra de negócio).

#### Evidence

- ADR D2 do blueprint — leitura `utf-8` com `errors="replace"`, sem detector de encoding
- `knowledge-base/references/ggshield/ggshield/core/scan/scannable.py:106-134` — o
  `_decode_bytes` que **não** vamos copiar, e o porquê
- ADR D7 deste plano — forma do retorno

#### Files to edit

- `src/gitsafety/scanner.py` (NOVO)

#### Deep file dependency analysis

Importa `walker` (T2.3), `rules` (T2.1), `finding` (T2.2). Consumido por T3.1.

#### Deep Dives

Numeração de linha é 1-based (convenção universal de editor). O modo de falha clássico é
off-by-one em arquivo **sem newline final** — `splitlines()` e iteração sobre o file
object divergem em arquivos que terminam sem `\n`. Há teste de borda dedicado.

Múltiplos segredos na mesma linha devem produzir múltiplos findings: usar `finditer`, não
`search`. Um `search` por linha esconde o segundo segredo — falso negativo silencioso.

Leitura com `errors="replace"` (ADR D2) nunca levanta `UnicodeDecodeError`, então nenhum
arquivo derruba a varredura inteira.

#### Pseudo-code / Signatures

```python
@dataclass(frozen=True)
class ScanResult:
    findings: list[Finding]
    skipped: list[SkippedFile]
    @property
    def has_findings(self) -> bool: ...

def scan_path(root: Path, rules: Sequence[Rule] = BUILTIN_RULES) -> ScanResult: ...
```

#### Tasks

1. `ScanResult` congelada com `has_findings`.
2. `scan_path()` que caminha, lê cada arquivo com `utf-8`/`errors="replace"` e aplica
   cada regra por linha com `finditer`.
3. Propagar `skipped` do walker sem alterar.

#### TDD

```python
# tests/unit/test_scanner.py
def test_scan_finds_aws_key_and_reports_1_based_line_number(tmp_path):
    (tmp_path / "cfg.py").write_text('x = 1\nkey = "AKIAIOSFODNN7EXAMPLE"\n')
    result = scan_path(tmp_path)
    assert result.findings[0].line == 2

def test_line_number_is_correct_when_file_has_no_trailing_newline(tmp_path):
    # edge case: off-by-one clássico
    (tmp_path / "a.txt").write_text('a\nAKIAIOSFODNN7EXAMPLE')  # sem \n final
    assert scan_path(tmp_path).findings[0].line == 2

def test_two_secrets_on_the_same_line_produce_two_findings(tmp_path):
    # negative case para 'search': search acharia só o primeiro
    (tmp_path / "a.txt").write_text("AKIAIOSFODNN7EXAMPLE AKIA1234567890ABCDEF")
    assert len(scan_path(tmp_path).findings) == 2

def test_scan_result_carries_skipped_files_through(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    assert len(scan_path(tmp_path).skipped) == 1

def test_undecodable_bytes_do_not_abort_the_scan(tmp_path):
    # negative case: ADR D2 — errors="replace" nunca levanta
    (tmp_path / "weird.txt").write_bytes(b"\xff\xfe caf\xe9\nAKIAIOSFODNN7EXAMPLE\n")
    result = scan_path(tmp_path)
    assert result.has_findings

def test_clean_directory_has_no_findings(tmp_path):
    (tmp_path / "ok.py").write_text("print('hello')\n")
    assert scan_path(tmp_path).has_findings is False
```

RED: `ImportError`. GREEN: criar o módulo.

#### Acceptance Criteria

- [ ] `test_line_number_is_correct_when_file_has_no_trailing_newline` assert `findings[0].line == 2`
- [ ] `assert len(scan_path(tmp_path).findings) == 2` com dois segredos na mesma linha
- [ ] `skipped` do walker chega intacto no `ScanResult`
- [ ] `test_undecodable_bytes_do_not_abort_the_scan` assert `result.has_findings` após gravar `b"\xff\xfe"`
- [ ] Diretório limpo devolve `has_findings is False`

#### DoD

- [ ] Todos os testes de T2.4 passam
- [ ] `scan_path` não contém `print` nem `sys.exit` (fronteira de camada)
- [ ] Commit atômico referenciando T2.4

---

## Phase 3: Interface, CI e benchmark

### T3.1 — `cli`: argparse, renderização e exit code

#### Objective

`gitsafety scan <caminho>` imprime os findings mascarados e sai com 0, 1 ou 2.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `cli.py` e ligar `__main__.main()` a ele.
**Raciocínio:** é o **wiring** que transforma os módulos em produto. Sem este task os
módulos anteriores são código morto — exatamente o que `cycle-implement § Wiring triad`
proíbe. Vem por último na cadeia funcional porque consome todo o resto.

#### Evidence

- ADR D4 do blueprint — exceção carrega o exit code
- ADR D5 do blueprint — `argparse`, não `click`
- `docs/PRD.md § FR-15, FR-16, FR-18` — forma da saída, `--show-secrets`, exit codes

#### Files to edit

- `src/gitsafety/cli.py` (NOVO)
- `src/gitsafety/__main__.py` (editar — passa a delegar para `cli.main`)

#### Deep file dependency analysis

`cli.py` importa `scanner`, `errors` e `finding`. `__main__.py` deixa de imprimir versão
diretamente e passa a chamar `cli.main()`. É o único ponto do sistema que chama
`sys.exit`.

#### Deep Dives

O tratamento de erro é o inverso do anti-pattern: em vez de `try/except Exception`, o
`main` captura **apenas** `GitsafetyError` e usa o `exit_code` que a exceção carrega. Erro
não previsto propaga com traceback — `rules/error-handling.md § 2`, falhar alto é
preferível a mascarar.

O `--help` deve listar apenas as flags que existem no M0. `--history` e `--staged` são
M5 e M1; documentá-las agora seria a divergência README×binário que o DoD do M6 verifica.

#### Pseudo-code / Signatures

```python
def build_parser() -> argparse.ArgumentParser: ...
def render(result: ScanResult, *, show_secrets: bool) -> str: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

#### Tasks

1. `build_parser()` com subcomando `scan`, argumento posicional de caminho,
   `--show-secrets` e `--version`.
2. `render()` produzindo `caminho:linha  regra  segredo` + linha de resumo de pulos.
3. `main()` capturando só `GitsafetyError` e devolvendo `exit_code`.
4. `__main__.main` delegando para `cli.main` com `sys.exit`.

#### TDD

```python
# tests/functional/test_cli.py
def test_exit_code_is_zero_when_nothing_is_found(tmp_path): ...

def test_exit_code_is_one_when_a_secret_is_found(tmp_path): ...

def test_exit_code_is_two_when_path_does_not_exist(tmp_path):
    # negative case
    assert main(["scan", str(tmp_path / "nope")]) == ExitCode.USAGE_ERROR

def test_output_masks_the_secret_by_default(tmp_path, capsys):
    # NFR-4: o relatório não pode virar o próximo vazamento
    ...
    assert "AKIAIOSFODNN7EXAMPLE" not in capsys.readouterr().out

def test_show_secrets_flag_reveals_the_full_value(tmp_path, capsys): ...

def test_output_reports_how_many_files_were_skipped(tmp_path, capsys): ...

def test_help_does_not_advertise_flags_that_do_not_exist_yet(capsys):
    # --history e --staged são M5 e M1
    out = ...
    assert "--history" not in out and "--staged" not in out
```

RED: `ImportError`. GREEN: criar o módulo.

#### Acceptance Criteria

- [ ] `main(["scan", limpo]) == 0`, `main(["scan", com_segredo]) == 1`, `main(["scan", inexistente]) == 2`
- [ ] `"AKIAIOSFODNN7EXAMPLE" not in capsys.readouterr().out` — a saída não contains o segredo íntegro
- [ ] com `--show-secrets` a saída contains `AKIAIOSFODNN7EXAMPLE` na íntegra
- [ ] a saída contains a contagem de pulos (assert por substring `pulado`)
- [ ] `"--history" not in help_out and "--staged" not in help_out`

#### DoD

- [ ] Todos os testes de T3.1 passam
- [ ] Wiring triad: `cli.main` é chamador real de `scan_path`; teste funcional cobre a
      fronteira CLI; a linha de resumo de pulos é o sinal observável em runtime
- [ ] Commit atômico referenciando T3.1

---

### T3.2 — Integração contínua

#### Objective

A suíte roda com um comando e está verde em CI, em Python 3.10 e 3.13.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `.github/workflows/ci.yml` e o alvo de teste único.
**Raciocínio:** é o DoD nº 4 do M0. Rodar em 3.10 e 3.13 verifica na prática o
`requires-python = ">=3.10"` declarado em T1.1 — declarar um piso sem testá-lo é
afirmação sem evidência.

#### Evidence

- `knowledge-base/references/ggshield/Makefile:21-26` — `test` compondo `unittest` e
  `functest`
- `ROADMAP.md § M0` DoD nº 4

#### Files to edit

- `.github/workflows/ci.yml` (NOVO)
- `pyproject.toml` (editar — dependência de desenvolvimento `pytest`)

#### Deep file dependency analysis

O workflow instala o pacote em modo editável e roda `pytest`. Depende de T1.1 (o pacote
precisa instalar) e de todos os tasks anteriores (a suíte precisa existir).

#### Deep Dives

O job precisa instalar o pacote (`pip install -e ".[dev]"`) **antes** de rodar os testes
funcionais, porque `tests/functional/test_installed_entry_point.py` invoca o binário
`gitsafety` como subprocesso. Rodar `pytest` sem instalar faz esse teste falhar por
motivo errado.

#### Pseudo-code / Signatures

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.13"]
steps:
  - pip install -e ".[dev]"
  - pytest
```

#### Tasks

1. `[project.optional-dependencies] dev = ["pytest>=9.0.3,<10"]` no `pyproject.toml` (piso obrigatório — ADR D8).
2. Workflow com matriz 3.10 / 3.13.
3. Configuração do pytest (`testpaths`) no `pyproject.toml`.

#### TDD

Task de infraestrutura — a verificação é a execução do próprio workflow, não um teste
unitário (testar o YAML do GitHub Actions seria testar framework de terceiro, vedado por
`rules/testing.md § 4`). O teste de regressão é: **a suíte completa passa nas duas
versões**.

```bash
# verificação local equivalente, antes do push
python3.10 -m pytest   # esperado: verde
python3.11 -m pytest   # esperado: verde
```

#### Acceptance Criteria

- [ ] `pytest` na raiz returns exit code `0` cobrindo `tests/unit` e `tests/functional`
- [ ] `pytest` returns exit `0` nos dois jobs da matriz (`3.10` e `3.13`)
- [ ] o passo `pip install -e ".[dev]"` precede `pytest` no `ci.yml`

#### DoD

- [ ] CI verde nas duas versões, com link da execução registrado no log de implementação
- [ ] Commit atômico referenciando T3.2

---

### T3.3 — Benchmark de varredura

#### Objective

Medir e registrar a latência da varredura, com orçamento verificado por teste.

#### Why this step (action + reasoning — ReAct discipline)

**Ação:** criar `benchmarks/bench_scan.py` e um teste de orçamento.
**Raciocínio:** o M1 amarra a varredura ao `git commit`, e a partir daí latência vira
experiência do usuário — `docs/PRD.md § NFR-2` exige que o commit não fique
perceptivelmente mais lento. Medir no M0, antes de existir a pressão do hook, cria a
linha de base contra a qual o M1 será comparado. Sem número no M0, "ficou mais lento" no
M1 é opinião.

#### Evidence

- `docs/PRD.md § NFR-2` — latência imperceptível no commit
- Unresolved Question nº 1 deste plano — a origem do orçamento de 5 s

#### Files to edit

- `benchmarks/bench_scan.py` (NOVO)
- `tests/functional/test_performance_budget.py` (NOVO)

#### Deep file dependency analysis

Consome `scan_path` (T2.4). Não é importado por código de produção — é ferramenta, e
`/code-quality` pode sinalizá-lo como export órfão; a mitigação é o teste de orçamento,
que o exercita.

#### Deep Dives

O benchmark gera a árvore em `tmp_path` para ser reprodutível em qualquer máquina, e mede
com `time.perf_counter`. Registra três números: total, por arquivo, e arquivos por
segundo — o segundo é o que se compara entre milestones, porque não depende do tamanho da
árvore gerada.

O orçamento do teste é **absoluto e folgado** (5 s para 1.000 arquivos): o objetivo é
pegar regressão de ordem de grandeza, não variação de ruído de CI. Comparação relativa
entre execuções é trabalho do `cycle-analysis`, não deste teste.

#### Pseudo-code / Signatures

```python
def build_corpus(root: Path, n_files: int, secrets_every: int) -> None: ...
def measure(root: Path) -> dict[str, float]: ...  # total_s, per_file_ms, files_per_s
```

#### Tasks

1. Gerador de corpus determinístico (N arquivos, 1 segredo a cada K).
2. Medição com `perf_counter` e impressão das três métricas.
3. Teste de orçamento com limite absoluto.

#### TDD

```python
# tests/functional/test_performance_budget.py
def test_scanning_1000_files_stays_within_the_absolute_budget(tmp_path):
    build_corpus(tmp_path, n_files=1000, secrets_every=100)
    metrics = measure(tmp_path)
    assert metrics["total_s"] < 5.0, f"orçamento estourado: {metrics}"

def test_benchmark_corpus_contains_the_expected_number_of_secrets(tmp_path):
    # o benchmark não vale nada se o corpus não tiver o que achar
    build_corpus(tmp_path, n_files=1000, secrets_every=100)
    assert len(scan_path(tmp_path).findings) == 10
```

RED: `ImportError`. GREEN: criar os módulos.

#### Acceptance Criteria

- [ ] `python benchmarks/bench_scan.py` outputs as três chaves `total_s`, `per_file_ms` e `files_per_s`
- [ ] `assert metrics["total_s"] < 5.0` para 1.000 arquivos
- [ ] `assert len(scan_path(tmp_path).findings) == 10` — o corpus contains segredos reais a detectar
- [ ] os três números aparecem em `knowledge-base/implementations/m0-esqueleto-cli-implementation.md`

#### DoD

- [ ] Os dois testes passam
- [ ] Números reais registrados em `knowledge-base/implementations/`
- [ ] Commit atômico referenciando T3.3

---

## Coverage Matrix

| # | Requisito (origem) | Task(s) | Como é resolvido |
|---|---|---|---|
| 1 | `pip install -e .` expõe `gitsafety` (ROADMAP M0 DoD 1) | T1.1 | `[project.scripts]`; teste invoca o binário como subprocesso de fora do repo |
| 2 | `scan` aplica `AKIA[0-9A-Z]{16}` (ROADMAP M0 DoD 2) | T2.1, T2.4, T3.1 | Regra + scanner + CLI; testes de acerto e não-acerto |
| 3 | Imprime `arquivo:linha regra` (ROADMAP M0 DoD 2) | T3.1 | `render()`; teste funcional de saída |
| 4 | Exit 0/1/2, cada um testado (ROADMAP M0 DoD 3) | T1.2, T3.1 | `ExitCode` + 3 testes funcionais |
| 5 | Suíte com um comando, verde em CI (ROADMAP M0 DoD 4) | T3.2 | `pytest>=9.0.3` + workflow em matriz 3.10/3.13 |
| 15 | Nenhuma dependência com CVE conhecido (deps-audit-golden-rule § 3) | T1.1, T3.2 | Runtime sem deps; `pytest` pinado acima da versão corrigida (ADR D8) |
| 6 | Binários pulados (ROADMAP M0 DoD 5) | T2.3 | `is_binary_path` por extensão; teste de pulo reportado |
| 7 | Arquivos > 1 MB pulados (ROADMAP M0 DoD 5) | T2.3 | `MAX_FILE_BYTES`; teste de fronteira inclusiva |
| 8 | Segredo mascarado por padrão (PRD NFR-4) | T2.2, T3.1 | `mask()` + teste que o segredo íntegro não aparece na saída |
| 9 | `--show-secrets` revela (PRD FR-16) | T3.1 | Flag + teste funcional |
| 10 | Falha explícita, sem erro genérico (PRD NFR-5) | T1.2, T2.3, T3.1 | `PathNotFoundError` tipado; `main` captura só `GitsafetyError` |
| 11 | Pulo é resultado, não efeito colateral (Blueprint D3, ADR D7) | T2.3, T2.4, T3.1 | `(files, skipped)` → `ScanResult` → linha de resumo |
| 12 | Sem dependência de runtime (PRD NFR-1, Blueprint D5) | T1.1 | `dependencies = []`; verificado por `/deps-audit` |
| 13 | Dados de benchmark (objetivo do ciclo) | T3.3 | Benchmark + teste de orçamento + números registrados |
| 14 | Formato de regra compatível com o M2 (Blueprint rec. 7) | T2.1 | `Rule` como dado com casos anexos |

**Cobertura: 15/15 requisitos mapeados (100%)**

## Global Definition of Done

- [ ] Os 5 itens de DoD do `ROADMAP.md § M0` verificados por teste automatizado
- [ ] Cobertura: toda regra de negócio com teste unitário (`rules/testing.md § 3`)
- [ ] Cada task com teste de acerto **e** de não-acerto onde aplicável (`§ 4.1`)
- [ ] Nenhum `except Exception` genérico (`rules/error-handling.md § 5`)
- [ ] Wiring triad em T3.1: chamador real, teste de integração, sinal observável
- [ ] `CHANGELOG.md` `[Unreleased]` atualizado
- [ ] `/code-quality` com veredito ∈ {PASS, PASS_WITH_CAVEATS}
- [ ] Benchmark executado com números registrados
- [ ] Nenhuma flag no `--help` que não exista

## Failure scenarios

O M0 não faz I/O externo — sem rede, banco, fila ou RPC. O único recurso externo é o
**sistema de arquivos**, e seus modos de falha são tratados como casos negativos:

| Recurso | Modo de falha | Como o teste reproduz | Comportamento esperado |
|---|---|---|---|
| Sistema de arquivos | Caminho não existe | `walk(tmp_path / "inexistente")` | `PathNotFoundError` com o caminho na mensagem; exit 2. Nunca lista vazia com exit 0 |
| Sistema de arquivos | Arquivo com bytes indecodificáveis | Escrever `b"\xff\xfe..."` em `tmp_path` | `errors="replace"` decodifica com substituição; varredura continua; demais arquivos ainda são varridos |
| Sistema de arquivos | Arquivo maior que o limite | Escrever 1 MB + 1 byte | Entra em `skipped` com motivo `TOO_LARGE`; aparece no resumo da saída |
| Sistema de arquivos | Arquivo binário | Escrever `b"\x89PNG"` com sufixo `.png` | Entra em `skipped` com motivo `BINARY`; nunca é lido |

**(sem I/O externo além do sistema de arquivos — nada de rede, banco ou fila no M0)**

## Concurrency tests

**(none — single-threaded)** — o M0 varre arquivos sequencialmente. Não há thread, async,
processo, lock nem estado compartilhado mutável. Paralelizar a varredura é otimização
sem dado que a justifique (o benchmark de T3.3 é justamente o que produzirá esse dado) e
seria YAGNI no M0.

---

## Final Phase: Integration Validation (MANDATORY)

### Execution

Em um clone limpo, em ambiente virtual novo:

```bash
python3 -m venv /tmp/gs && /tmp/gs/bin/pip install -e ".[dev]"
/tmp/gs/bin/pytest -q                                   # toda a suíte
cd /tmp && /tmp/gs/bin/gitsafety --version               # entry point fora do repo
mkdir -p /tmp/demo && printf 'k = "AKIAIOSFODNN7EXAMPLE"\n' > /tmp/demo/app.py
/tmp/gs/bin/gitsafety scan /tmp/demo; echo "exit=$?"      # esperado: exit=1, mascarado
/tmp/gs/bin/gitsafety scan /tmp/vazio; echo "exit=$?"     # esperado: exit=0
/tmp/gs/bin/gitsafety scan /tmp/nao-existe; echo "exit=$?" # esperado: exit=2
/tmp/gs/bin/python benchmarks/bench_scan.py               # números registrados
```

### Acceptance Criteria

- [ ] `pip install -e ".[dev]"` em venv novo returns exit code `0`
- [ ] `pytest -q` returns exit code `0`
- [ ] `cd /tmp && gitsafety --version` returns exit `0` e outputs a versão
- [ ] `echo $?` outputs `0`, `1` e `2` nos três comandos da § Execution
- [ ] a saída contains `AKIA••••••••••••MPLE` e não contains `AKIAIOSFODNN7EXAMPLE`
- [ ] `bench_scan.py` outputs `total_s`, `per_file_ms` e `files_per_s`

### If Validation Fails

Voltar ao task correspondente pelo Coverage Matrix. Não seguir para `/code-quality` com
qualquer item acima falhando — `cycle-implement § Stop conditions` proíbe emitir a
promessa de conclusão em estado parcial.
