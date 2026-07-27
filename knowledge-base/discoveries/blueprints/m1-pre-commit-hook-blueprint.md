# Blueprint: Mecânica do hook de pre-commit (M1)

**Slug:** `m1-pre-commit-hook`
**Plano de origem:** `knowledge-base/discoveries/plans/m1-pre-commit-hook-plan.md` (v1.1)
**Revisão de edge cases:** `knowledge-base/reviews/m1-pre-commit-hook-edge-cases-2026-07-27.md`
**Data:** 2026-07-27
**Questões:** 7 respondidas, 0 BLOCKED

> **Limitação herdada do M0 (D3 daquele blueprint).** `detect-secrets`, `ripsecrets` e
> `secretlint` seguem ilegíveis pelo deny-glob `Read(**/*secret*)`, assim como
> `ggshield/ggshield/cmd/secret/`. As conclusões sobre ggshield vêm de `cmd/install.py`
> e `core/`, que **são** legíveis e contêm o fluxo inteiro de instalação — para este
> milestone a limitação pesa menos que no M0.

## Context

O `ROADMAP.md § M1` é onde o produto passa a interceptar o commit. Os dois riscos
nomeados são o alvo direto desta investigação, e o resultado mais consequente é que
**o Risco nº 1 estava formulado com a técnica errada**: o roadmap supunha
`git show :arquivo`; os dois peers que resolvem esse problema usam outra coisa.

## Objective

Travar quatro decisões antes do `/to-plan` do M1: onde o hook é escrito e em que
linguagem, como o conteúdo em stage é lido, o que acontece com hook preexistente, e qual
forma de teste prova que um commit real é bloqueado.

## Coverage Corner 1 — Integration Tests

### Q4 — Como o talisman prova que um commit real é bloqueado

`knowledge-base/references/talisman/cmd/acceptance_test.go` — o padrão é **um teste por
comportamento, asserindo o exit code**, sobre um repositório git de verdade:

| Linha | Teste | Asserção |
|---|---|---|
| `:64` | `TestNotHavingAnyOutgoingChangesShouldNotFail` | `assert.Equal(t, 0, ...)` |
| `:71` | `TestAddingSimpleFileShouldExitZero` | `assert.Equal(t, 0, ...)` |
| `:78` | `TestAddingSecretKeyShouldExitOne` | `assert.Equal(t, 1, ...)` |
| `:88` | `TestAddingSecretKeyAsFileContentShouldExitOne` | `assert.Equal(t, 1, ...)` |
| `:99` | `TestAddingSecretKeyShouldExitZeroIfPEMFileIsIgnored` | `assert.Equal(t, 0, ...)` |

Três traços importam:

1. **O nome do teste é a especificação.** `TestAddingSecretKeyShouldExitOne` descreve o
   comportamento, não o método — exatamente o que `rules/testing.md § 3` exige.
2. **A asserção é o exit code**, não a saída de texto. O contrato do hook com o git é
   numérico; asserir sobre texto acopla o teste à formatação.
3. **Repositório real**, manipulado por um helper (`git.AddAndcommit("*", "...")`,
   `:82`, `:93`). Não há mock do git.

O último teste (`:99`) é o mais instrutivo: prova que **o caminho de exceção também é
testado** — ignorar um arquivo faz o exit voltar a 0. É a metade que a maioria das suítes
esquece.

### Q5 — Como o ggshield testa o `install`

`knowledge-base/references/ggshield/tests/unit/cmd/test_install.py` — a suíte é organizada
**pelo estado do sistema de arquivos no momento da instalação**:

| Linha | Teste | Cenário coberto |
|---|---|---|
| `:34` | `test_local_exist_is_dir` | o caminho do hook é um **diretório** |
| `:44` | `test_local_exist_not_force` | hook já existe, sem `--force` → deve recusar |
| `:54` | `test_local_exist_force` | hook já existe, com `--force` → deve sobrescrever |
| `:64` | `test_precommit_install` | caminho feliz |
| `:88` | `test_install_exists` | idem para o modo global |
| `:116` | `test_install_exists_force` | idem com `--force` |
| `:141` | `test_install_exists_append` | idem com `--append` |

**Quatro dos sete testes cobrem o caso "já existe alguma coisa lá".** A proporção é a
lição: no comando `install`, o caminho feliz é trivial e o valor do teste está nos
estados degenerados do sistema de arquivos.

O `cli_fs_runner` é um runner de CLI com sistema de arquivos isolado — teste de nível
funcional exercendo o comando inteiro, não a função interna.

## Coverage Corner 2 — Dependencies

### Q6 — O caminho do hook adiciona dependência de runtime?

Imports de `knowledge-base/references/ggshield/ggshield/cmd/install.py:1-15`:

| Import | Origem | O gitsafety precisa? |
|---|---|---|
| `os` (`:1`) | stdlib | **Sim** — `os.chmod` para o bit de execução |
| `subprocess` (`:2`) | stdlib | **Sim** — invocar `git` |
| `pathlib.Path` (`:3`) | stdlib | **Sim** |
| `typing` (`:4`) | stdlib | Sim |
| `click`, `click.UsageError` (`:6-7`) | **terceiro** | **Não** — `argparse` (ADR D5 do M0) |
| `ggshield.core.*`, `ggshield.utils.git_shell`, `ggshield.verticals.*` (`:9-15`) | internos | n/a |

**Veredito: o M1 não adiciona nenhuma dependência de runtime.** Tudo que o fluxo de
instalação precisa — criar diretório, escrever arquivo, setar permissão, invocar `git` —
está em `os`, `pathlib` e `subprocess`. O `docs/PRD.md § NFR-1` continua satisfeito com
`dependencies = []`.

## Coverage Corner 3 — Tools

### Q7 — `core.hooksPath` e bit de execução

`knowledge-base/references/ggshield/ggshield/cmd/install.py`:

| Citação | Mecanismo |
|---|---|
| `:103` | Modo global: `git config --global core.hooksPath <dir>` |
| `:147` | Modo system: `git config --system core.hooksPath <dir>` |
| `:123-131` | `get_global_hook_dir_path()` — lê `core.hooksPath` já configurado antes de escrever |
| `:177` | `get_configured_hook_dir_path()` — resolve qual diretório está de fato em vigor |
| `:319` | `hook_dir_path.mkdir(parents=True, exist_ok=True)` |
| `:320-325` | Diretório do modo system recebe `0o755`, com `except OSError: pass` |
| `:351` | `os.chmod(hook_path, 0o755 if world_readable else 0o700)` |

**A permissão padrão é `0o700` — dono apenas.** `0o755` só no modo system, onde o hook
roda como cada usuário que commita. É o inverso do reflexo comum (`chmod +x` para todos):
um hook que executa código deve ser gravável e executável pelo menor conjunto possível de
usuários.

O `except OSError: pass` do `:324` é uma concessão declarada — em sistemas onde o `chmod`
do diretório falha, a instalação continua. Note a assimetria: o `chmod` **do arquivo**
(`:351`) não tem `try`, porque sem bit de execução o hook simplesmente não roda.

Nada nos arquivos lidos trata Windows explicitamente. **[confiança reduzida]** — o modo
Windows pode estar em `utils/git_shell.py`, fora do escopo declarado desta descoberta.

## Coverage Corner 4 — Techniques

### Q1 — Onde o hook é escrito, e em que linguagem

`create_hook` em `knowledge-base/references/ggshield/ggshield/cmd/install.py:305-358`:

```python
hook_dir_path.mkdir(parents=True, exist_ok=True)      # :319
hook_path = hook_dir_path / hook_type                  # :326
...
with hook_path.open("a" if append else "w") as f:      # :342
    if not append:
        f.write("#!/bin/sh\n")                         # :344
    if local_hook_support:
        f.write(LOCAL_HOOK_SNIPPET.format(hook_type=hook_type))   # :347
    f.write(f'ggshield secret scan {hook_type} "$@"\n')           # :350
    os.chmod(hook_path, 0o755 if world_readable else 0o700)       # :351
```

**O hook é um script `sh`, não Python** (EC-3 respondido). Um projeto Python escrevendo um
hook em shell é escolha deliberada, e o M0 já mediu por quê: a varredura custa 0,0145 ms
por arquivo, então o custo dominante do M1 seria o **startup do interpretador**. Um hook
em shell:

- não paga startup de Python quando o git decide não executá-lo;
- funciona com o venv desativado, porque invoca o comando pelo PATH;
- tem uma linha de corpo — `comando "$@"`, repassando os argumentos que o git fornece.

O `"$@"` no `:350` não é cosmético: o git passa argumentos a alguns hooks, e engoli-los
quebra o contrato silenciosamente.

### Q2 — Como o conteúdo em stage é lido *(o núcleo do Risco nº 1)*

**Os dois peers convergem, e nenhum usa `git show :arquivo`:**

| Peer | Comando literal | Citação |
|---|---|---|
| gitleaks | `git -C <dir> diff -U0 --no-ext-diff --staged .` | `knowledge-base/references/gitleaks/sources/git.go:139-142` |
| talisman | `git diff --staged --src-prefix=a/ --dst-prefix=b/` | `knowledge-base/references/talisman/gitrepo/gitrepo.go:47` |

Cada flag existe por um motivo, e todos são defensivos:

| Flag | Peer | Por quê |
|---|---|---|
| `--staged` | ambos | Diferença entre índice e HEAD — **exatamente o que será commitado**, não o que está em disco |
| `-U0` | gitleaks | Zero linhas de contexto: só o que mudou. Sem isso, linhas inalteradas ao redor entrariam na varredura e gerariam achado em código que ninguém tocou |
| `--no-ext-diff` | gitleaks | Ignora o driver de diff externo do usuário, que poderia produzir saída arbitrária e quebrar o parsing |
| `--src-prefix=a/ --dst-prefix=b/` | talisman | Força os prefixos padrão contra um `diff.noprefix=true` na config do usuário, que quebraria o parsing dos cabeçalhos |

`gitrepo.go:45` declara a intenção: *"GetDiffForStagedFiles gets all the staged files and
collects the diff section in each file"*.

**A consequência de projeto é mais importante que a técnica.** `git diff --staged` devolve
**apenas as linhas adicionadas**, não o arquivo inteiro. Isso significa que o hook reclama
do que você está **introduzindo**, e não de segredo preexistente num arquivo que você por
acaso tocou. Para o `docs/PRD.md § 4` — cuja north-star é retenção — a diferença é
existencial: varrer o arquivo inteiro faria a adoção em repositório legado bloquear todo
commit até que alguém limpe o histórico, e o hook seria desinstalado na primeira semana.

Segredo preexistente é trabalho do `scan` completo e do `--history` (M5), não do hook.

### Q3 — O que acontece quando já existe um `pre-commit`

`knowledge-base/references/ggshield/ggshield/cmd/install.py:328-340`:

```python
if hook_path.is_dir():                                    # :328
    raise UsageError(f"{hook_path} is a directory.")      # :329

if hook_path.is_file() and not (force or append):         # :331
    raise UnexpectedError(
        f"{hook_path} already exists."
        " Use --force to override or --append to add to current script"   # :334
    )

if append and not hook_path.exists():                     # :337
    append = False                                        # :340
```

**Recusa por padrão** (`:331`), e a mensagem **nomeia as duas saídas** (`--force`,
`--append`) em vez de só dizer "já existe". O `:328` trata o caso degenerado de o caminho
ser um diretório, com erro distinto.

O `:337-340` é o detalhe fino: pedir `--append` num arquivo que não existe **desliga o
append**, porque o shebang precisa ser escrito. Sem isso, o arquivo sairia sem `#!/bin/sh`
e o git o executaria com o shell padrão — comportamento diferente do pretendido, em
silêncio.

**A quarta estratégia (EC-1), que é a mais interessante:** o hook global do ggshield
**delega ao hook local**, em vez de competir com ele
(`install.py:22-35`):

```sh
_ggshield_local_hook=$(git rev-parse --git-common-dir)/hooks/{hook_type}   # :28
if [ -f "$_ggshield_local_hook" ]; then                                     # :29
    if ! "$_ggshield_local_hook" "$@"; then                                 # :30
        echo 'Local {hook_type} hook failed, please see output above'       # :31
```

Encadeia, propaga a falha e explica de onde veio. `git rev-parse --git-common-dir` (e não
`--git-dir`) é o detalhe correto: em worktrees, `--git-dir` aponta para o diretório da
worktree, e os hooks vivem no comum.

**Marcador de auto-reconhecimento** (`install.py:37-39`):

```python
# The line `create_hook` writes into every ggshield-managed hook script; its presence
# is how we recognize a hook (or hooks dir) as ggshield's own.
GGSHIELD_HOOK_MARKER = "ggshield secret scan"
```

Com `hook_invokes_ggshield()` (`:207-216`) lendo o arquivo e procurando o marcador. É o
que torna a instalação **idempotente**: rodar `install` duas vezes reconhece o próprio
hook e não trata como conflito de terceiro.

## Cross-cutting Comparison

| Dimensão | ggshield (Python) | talisman (Go) | gitleaks (Go) | Decisão para o M1 |
|---|---|---|---|---|
| Onde escreve | `<hook_dir>/<hook_type>` (`:326`) | `.git/hooks/` via `install.sh` | n/a | `.git/hooks/pre-commit` |
| Linguagem do hook | **`sh`** (`:344`) | shell | n/a | `sh` — evita startup de Python |
| Corpo do hook | `comando "$@"` (`:350`) | idem | n/a | `gitsafety scan --staged "$@"` |
| Permissão | `0o700` padrão (`:351`) | — | n/a | `0o700` |
| Leitura do stage | n/a | `git diff --staged --src-prefix=a/ --dst-prefix=b/` | `git diff -U0 --no-ext-diff --staged .` | `git diff --staged -U0 --no-ext-diff` |
| Hook existente | recusa; msg nomeia `--force`/`--append` (`:331-335`) | — | n/a | **Recusa** (FR-2), msg nomeia a saída |
| Coexistência | delega ao hook local (`:28-31`) | — | n/a | Documentar a linha; não implementar (YAGNI) |
| Idempotência | marcador no conteúdo (`:39`, `:207`) | — | n/a | **Adotar** — marcador reconhecível |
| Forma do teste | 4 de 7 sobre estado preexistente | exit code sobre repo real | n/a | Ambas |

## ADRs

### D1 — Ler o stage com `git diff --staged`, não `git show :arquivo`

**Decisão:** o `--staged` do M1 obtém conteúdo via
`git diff --staged -U0 --no-ext-diff`, e varre **apenas as linhas adicionadas**.

**Rationale:** os dois peers que resolvem este problema convergem nessa técnica
(`gitleaks/sources/git.go:139-142`, `talisman/gitrepo/gitrepo.go:47`). O
`ROADMAP.md § M1` supunha `git show :arquivo`, que resolve o problema declarado — ler o
índice em vez do disco — mas traz um efeito colateral caro: varre o **arquivo inteiro em
stage**, incluindo segredo preexistente que o usuário não introduziu. Num repositório
legado isso bloqueia todo commit até alguém limpar o histórico, e o hook é desinstalado.
Com a north-star do `ROADMAP.md` sendo retenção, esse efeito é fatal.

**Alternativas consideradas:** (a) `git show :arquivo` por arquivo listado em
`git diff --cached --name-only` — rejeitada pelo efeito acima, apesar de dispensar parsing
de diff; (b) ler do disco — rejeitada, é o Risco nº 1 literal: `git add -p` põe parte do
arquivo em stage e o disco tem outra coisa; (c) `git diff --staged` **sem** `-U0` —
rejeitada, linhas de contexto inalteradas entrariam na varredura e gerariam achado em
código não tocado.

**Consequências:** é preciso **parsear diff unificado** para extrair linhas adicionadas e
mapear números de linha — trabalho real que a alternativa (a) não teria. Em troca, o hook
só reclama do que está sendo introduzido. Segredo preexistente fica para o `scan` completo
e para o `--history` do M5; o README precisa dizer isso.

### D2 — O hook é um script `sh` de uma linha

**Decisão:** `.git/hooks/pre-commit` é um script `sh` com shebang `#!/bin/sh` e corpo
`gitsafety scan --staged "$@"`.

**Rationale:** precedente literal em `install.py:344,350`. O M0 mediu 0,0145 ms por
arquivo, de onde se conclui que o custo dominante do M1 é o startup do interpretador — um
hook em shell não o paga quando o git decide não executá-lo, e funciona com o venv
desativado porque resolve o comando pelo PATH. O `"$@"` repassa os argumentos que o git
fornece; engoli-los quebra o contrato em silêncio.

**Alternativas consideradas:** (a) hook em Python com shebang do interpretador do venv —
rejeitada, amarra o hook a um venv específico que pode ser apagado, e paga startup sempre;
(b) hook em shell invocando `python -m gitsafety` — rejeitada, mesma amarração sem ganho
sobre invocar o console script.

**Consequências:** o hook depende de `gitsafety` estar no PATH quando o git o executa. Se
não estiver, o git reporta erro do shell, não do gitsafety — a mensagem será pior. O
`install` deve verificar isso no momento da instalação, não deixar para o commit.

### D3 — Recusar hook preexistente, com mensagem que nomeia a saída

**Decisão:** `install` recusa quando `.git/hooks/pre-commit` já existe, sai com
`USAGE_ERROR` (2) e imprime **a linha exata** a acrescentar no hook do usuário. Sem
`--force`, sem `--append` no M1.

**Rationale:** `docs/PRD.md § FR-2` já decidiu recusar; o precedente acrescenta **como**
recusar — `install.py:331-335` nomeia as duas saídas na própria mensagem, em vez de só
informar o conflito. Traduzido ao nosso escopo, a saída é uma só: a linha a colar. Sobre
não implementar `--force`/`--append`: são dois knobs, o `docs/PRD.md § NFR-3` limita a
superfície, e a linha impressa resolve o caso sem nenhum knob.

**Alternativas consideradas:** (a) `--force` como o ggshield — rejeitada por YAGNI e pelo
teto de flags; destruir o hook de outra ferramenta é dano difícil de desfazer; (b)
`--append` — rejeitada, anexar a um script cuja estrutura não conhecemos pode inserir
código depois de um `exit`; (c) delegação em cadeia (`install.py:28-31`) — rejeitada para
o M1 por escopo, **mas registrada** como a melhor solução para coexistência caso o
problema apareça.

**Consequências:** um usuário com hook preexistente precisa de um passo manual. É o custo
de nunca destruir configuração alheia. O caso do caminho ser um **diretório** (`:328`)
precisa de erro próprio, senão a mensagem confunde.

### D4 — Marcador de auto-reconhecimento para idempotência

**Decisão:** o hook escrito contém a string `gitsafety scan --staged`, e o `install` a
procura no arquivo antes de decidir que há conflito.

**Rationale:** `install.py:37-39` + `hook_invokes_ggshield()` em `:207-216`. Sem marcador,
rodar `install` duas vezes acusa conflito com o **próprio** hook — comportamento
irritante que faz o usuário alcançar o `--force` que o D3 decidiu não oferecer. O marcador
é a linha de comando que já vai lá dentro; não é metadado extra.

**Alternativas consideradas:** (a) comentário dedicado tipo `# gitsafety-managed` —
rejeitada, é metadado que pode ser removido sem quebrar o hook, criando divergência entre
marcador e realidade; (b) arquivo de estado paralelo — rejeitada, dois artefatos para
manter sincronizados.

**Consequências:** um hook de terceiro que por acaso contenha a string seria confundido
com o nosso. Risco aceito: a string é específica o bastante.

### D5 — Testar contra um repositório git real, asserindo exit code

**Decisão:** o teste de integração do M1 cria um repositório git temporário de verdade,
faz `git add`, dispara `git commit` e asserta o **código de saída**. Sem mock do git.

**Rationale:** `talisman/cmd/acceptance_test.go:64-99` — nomes descrevem comportamento, a
asserção é numérica, e o repositório é real. Mock de git no M1 testaria o mock: o
comportamento sob teste É a interação com o git, e o Risco nº 1 (stage divergindo do
disco) só se manifesta num índice de verdade.

**Alternativas consideradas:** (a) mockar `subprocess` — rejeitada, o defeito que mais
importa é justamente na fronteira com o git; (b) asserir sobre a saída de texto —
rejeitada, acopla o teste à formatação; o contrato com o git é o exit code.

**Consequências:** os testes do M1 são mais lentos que os unitários do M0 (criam
repositório, rodam `git`). Ficam em `tests/functional/`, e a divisão de dois níveis
herdada do M0 acomoda isso sem mudança.

### D6 — A suíte cobre os estados degenerados antes do caminho feliz

**Decisão:** o `install` recebe teste para: hook já existe, caminho é um diretório, fora
de repositório git, `.git/hooks/` inexistente, e instalação repetida (idempotência) —
além do caminho feliz.

**Rationale:** em `ggshield/tests/unit/cmd/test_install.py`, **4 dos 7 testes** cobrem
"já existe alguma coisa lá" (`:34,44,54,88,116,141`). A proporção é a lição: no `install`
o caminho feliz é trivial e o valor está nos estados degenerados do sistema de arquivos.
Alinha com `rules/testing.md § 4.1` — o caso negativo é a metade que costuma faltar.

**Consequências:** o M1 terá mais teste de erro que de sucesso no `install`. É o esperado
para um comando que escreve no diretório de outra ferramenta.

## Recommendations

Em ordem de impacto, cada uma rastreável a um ADR e a uma citação:

1. **Ler o stage com `git diff --staged -U0 --no-ext-diff`** (D1) e varrer só as linhas
   adicionadas. Corrige a premissa do roadmap. Documentar no README que o hook checa o que
   você **introduz**, não segredo preexistente.
2. **Escrever o hook em `sh`, uma linha, `"$@"` repassado, `0o700`** (D2) — literal de
   `install.py:344,350,351`.
3. **Recusar hook preexistente com a linha exata a colar** (D3); tratar "é um diretório"
   como erro próprio (`install.py:328`).
4. **Marcador de auto-reconhecimento** para idempotência (D4) — `install.py:37-39`.
5. **Verificar no `install`** que `gitsafety` está no PATH; falhar ali é muito melhor que
   falhar no primeiro commit com erro do shell (consequência declarada em D2).
6. **Testes contra repositório git real, asserindo exit code** (D5), com os estados
   degenerados cobertos primeiro (D6).
7. **Usar `git rev-parse --git-common-dir`**, não `--git-dir`, se algum dia houver suporte
   a worktree — em worktrees os hooks vivem no diretório comum (`install.py:28`).

## Blocked questions

Nenhuma. As 7 questões foram respondidas com citação verificada. Uma resposta parcial está
declarada: Q7 não encontrou tratamento explícito de Windows nos arquivos em escopo — marcada
como **[confiança reduzida]**, com a hipótese de estar em `utils/git_shell.py`, fora do
escopo desta descoberta.
