# Blueprint: Histórico do git (M5)

**Slug:** `m5-historico-git`
**Plano:** `knowledge-base/discoveries/plans/m5-historico-git-plan.md` (v1.2, SHIPPABLE 100.0)
**Data:** 2026-07-27
**Veredito `/discover-confidence`:** SHIPPABLE (100.0, zero hard caps)

## Context

O `ROADMAP.md § M5` é a **linha de chegada da V1**: `gitsafety scan --history` percorre o
histórico e reporta commit, autor e data (`docs/PRD.md` FR-17). É a pergunta que o hook não
responde — "a chave que commitei mês passado ainda está lá?".

O M1 fixou a fronteira: `git.py` é o único módulo que importa `subprocess`, e `staged.py`
provou que `git diff --staged -U0 --no-ext-diff` é o contrato certo para o index. Falta o
equivalente para o histórico.

Ao contrário do M4 — onde nenhum peer parseava notebook e a evidência virou execução
própria — aqui os três peers legíveis resolvem exatamente este problema, e escolheram
comandos **diferentes**. A investigação é sobre qual escolha e por quê.

## Objective

Decidir qual comando de baixo nível enumera o conteúdo histórico do git, como deduplicar
sem esconder ocorrência, o que reportar por achado, e qual o custo real em escala.

## Sumário executivo — o achado que muda a decisão

O gitleaks usa `git log -p -U0 --full-history --all --diff-filter=tuxdb`
(`sources/git.go:93-94`). **Medi que esse comando não enxerga um segredo introduzido na
resolução de um conflito de merge.**

```
Segredo existe em algum pai?  lado: 0   main^1: 0   merge(HEAD): 1

git log -p -U0 --full-history --all --diff-filter=tuxdb  ->  0 ocorrências
git log -p -U0 --all -m                                  ->  2 ocorrências (uma por pai)
git log -p -U0 --all --diff-merges=first-parent          ->  1 ocorrência
git rev-list --objects --all | git cat-file --batch      ->  1 ocorrência
```

A causa é comportamento documentado do git: `git log -p` **não emite diff para commits de
merge** por padrão. Todo conteúdo que existe apenas no merge — que é exatamente o caso de
alguém colar uma credencial ao resolver conflito — é invisível.

Isto é prior art que **não deve ser copiado como está**. Foi a pergunta Q5 ("o que o comando
escolhido não enxerga?"), obrigatória antes de recomendar qualquer comando, que o revelou —
o checkpoint existe no plano por causa das cinco rodadas de review do M4.

## Q1 — Comandos, flags e campos do achado (gitleaks)

### Os dois comandos, e por que são dois

| Comando | Onde | O que devolve | Quando é usado |
|---|---|---|---|
| `git log -p -U0 --full-history --all --diff-filter=tuxdb` | `sources/git.go:93-94` | Fluxo de diffs de todo o histórico | Varredura de histórico (`gitleaks git`) |
| `git cat-file blob <commit>:<path>` | `sources/git.go:208` | Conteúdo **íntegro** de um blob | `NewBlobReader` — quando é preciso o arquivo inteiro, não o diff |
| `git diff -U0 --no-ext-diff .` | `sources/git.go:139` | Diff da árvore de trabalho | `gitleaks dir` / pre-commit |

O `cat-file` não é redundante: o `log -p` entrega **linhas adicionadas**, e há regras
multi-linha (chave PEM, por exemplo) que precisam do arquivo íntegro. O comentário em
`sources/git.go:36` diz isso — `blobReader` existe para "fetch" do blob.

### Flags — o que cada uma compra

| Flag | O que compra | Medido |
|---|---|---|
| `-p` | Emite o conteúdo do diff (sem ela, só metadados) | Sem `-p`, zero linhas de conteúdo |
| `-U0` | Zero linhas de contexto — só o que foi **adicionado** | Mesma escolha do `staged.py` no M1 |
| `--full-history` | Não simplifica o histórico em caminhos de merge | — |
| `--all` | Todas as refs, não só `HEAD` | **Crítico**: em repo vazio, `log -p` falha com exit 128 e `fatal: does not have any commits yet`; **com `--all`, exit 0 e saída vazia** |
| `--diff-filter=tuxdb` | Exclui adições/modificações? Não — inclui `t`(type), `u`(unmerged), `x`(unknown), `d`(deleted), `b`(broken) | Ver nota abaixo |

> **Nota honesta sobre `--diff-filter=tuxdb`:** a semântica em minúsculas do git é
> **excludente** — `--diff-filter=d` exclui deletados. Não localizei no gitleaks um
> comentário explicando a escolha, e não vou inferir a intenção de código que não a declara.
> O efeito observável é que tipos de mudança que não trazem conteúdo novo são filtrados.
> **Para o gitsafety a flag é dispensável**: nossas regras só casam conteúdo adicionado, e
> uma flag cuja razão não conseguimos citar não entra por imitação (Regra Inquebrável 3).

### Campos do achado histórico (EC-2)

De `report/finding.go`:

| Campo | Linha |
|---|---|
| `Author`, `Email`, `Date`, `Message` | `finding.go:40-43` |
| `Fingerprint` (identificador único) | `finding.go:47` |
| `Entropy` | `finding.go:38` |

O `ROADMAP.md § M5` pede commit, autor e data — o gitleaks reporta os três mais a mensagem.

## Q2 — Talisman: a segunda estratégia

| Comando | Onde | Estratégia |
|---|---|---|
| `git ls-tree <branch> --name-only -r` | `gitrepo/gitrepo.go:238` | Lista os arquivos de uma árvore |
| `git cat-file -p <expr>` | `gitrepo/gitrepo.go:341` | Lê o conteúdo de um objeto |
| `git cat-file --batch=%(objectsize)` | `gitrepo/git_readers.go:42` | Consulta tamanho em lote |

**O talisman não usa `git log -p`.** Ele enumera **árvores e objetos**, não diffs. A
diferença é material: enumerar objetos não tem a lacuna do merge, porque não depende do git
decidir se emite diff para um commit.

`--batch` em `git_readers.go:42` é a mesma técnica que medi como alternativa: um único
processo do git respondendo a muitas consultas, em vez de um processo por objeto.

## Q3 — Deduplicação (Risco M5 nº 2)

`detect/detect.go:714`:

```go
finding.Fingerprint = fmt.Sprintf("%s:%s:%s:%d", finding.Commit, finding.File, finding.RuleID, finding.StartLine)
```

A chave é **commit + arquivo + regra + linha**. Confirmado pelos testes:
`detect/detect_test.go:884` — `"1b6da43b...:main.go:aws-access-key:20"`.

**Consequência para nós, e ela contraria o roadmap.** O `ROADMAP.md § M5` sugere dedup por
`(regra, segredo, arquivo)` — sem o commit. Isso colapsaria o mesmo segredo em commits
diferentes num achado só. O gitleaks **inclui o commit**, ou seja, não deduplica entre
commits: cada introdução é um achado.

As duas leituras são defensáveis e servem a perguntas diferentes:

- Com commit (gitleaks): "onde este segredo foi introduzido?" — útil para auditoria.
- Sem commit (roadmap): "quais segredos existem no histórico?" — útil para revogação.

A lição do M4 aponta o caminho: **colapsar ocorrências esconde lugares de onde remover**.
Mas aqui a ação corretiva é *revogar a chave no provedor*, que é única por segredo, e não
*editar cada commit*. Proposta de decisão no ADR D2 abaixo.

## Q4 — Custo e repositório vazio

### Repositório sem commits (DoD nº 4)

| Comando | exit | saída |
|---|---|---|
| `git log -p` | **128** | `fatal: your current branch 'master' does not have any commits yet` |
| `git log -p --all` | **0** | vazia |

`--all` transforma o erro em resultado vazio. É a diferença entre precisar tratar exceção e
não precisar — e resolve o DoD nº 4 sem código de caso especial.

### Custo em escala

Repositório sintético: 5.000 commits, 50 arquivos, `.git` de 9,7 MB. Melhor de 3 rodadas,
saída consumida (medir com a saída descartada dava 0,00 s — erro de método corrigido).

| Comando | Tempo | Linhas |
|---|---|---|
| `log -p --full-history --all --diff-filter=tuxdb` | 0,115 s | 79.949 |
| `log -p --all -m` | 0,120 s | 79.949 |
| `log -p --all --diff-merges=first-parent` | **0,113 s** | 79.949 |
| `rev-list --objects --all \| cat-file --batch` | 0,228 s | 203.359 |

**`--diff-merges=first-parent` custa o mesmo que o padrão e fecha a lacuna do merge.**
Ressalva honesta: este repositório sintético **não tem merges**, então os três variantes de
`log` percorrem o mesmo material; o número diz que a flag não tem custo próprio, não que
seja gratuita num repositório com muitos merges.

A enumeração de blobs custa **2×** e devolve 2,5× mais conteúdo — porque entrega arquivos
íntegros, não linhas adicionadas, e portanto revarre conteúdo que não mudou.

**Risco M5 nº 1 não se materializa nesta escala:** 5.000 commits em 0,115 s. O roadmap manda
documentar o custo em vez de adicionar flags de tuning, e o custo é este.

## Q5 — O que o comando não enxerga (medido)

| Caso | `log -p --all` | Alternativa que acha |
|---|---|---|
| Segredo introduzido e depois **removido** | ✅ acha | — (o DoD nº 3 está coberto) |
| Segredo num **ramo** não mergeado | ✅ acha (via `--all`) | — |
| Segredo só na **resolução de conflito de merge** | ❌ **não acha** | `--diff-merges=first-parent` (1×) ou `-m` (2×) |
| Segredo em commit **reescrito** (`reset --soft` + novo commit) | ❌ não acha | `git log -g --all` (reflog) acha 2× |

O caso do reflog merece nuance: o commit foi reescrito, então o segredo **não está mais no
histórico** — mas continua recuperável localmente por até 90 dias. Achá-lo seria útil, e
`--all` não cobre reflog. Fica como lacuna declarada, não como requisito do M5.

## Q6 — Fixtures de teste

| Peer | Abordagem | Onde |
|---|---|---|
| ggshield | Classe `Repository` com `create`, `clone`, `add`, `create_commit`; erro do git é impresso com stdout **e** stderr antes de relançar | `tests/repository.py:1-50` |
| gitleaks | Fixtures em Go | `sources/git_test.go` |
| talisman | Pacote `git_testing` dedicado | `gitrepo/gitrepo_test.go` |

**Padrão recomendado**, vindo do ggshield por ser o único em Python: uma fábrica que cria o
repositório e faz commits com credenciais de autor fixas. O `tests/conftest.py` já tem
`tmp_git_repo` e `git_commit` do M1 — o M5 precisa estendê-los para criar **histórico**, não
só um commit.

Detalhe que vale copiar: `repository.py:22-27` imprime stdout e stderr do git antes de
relançar a exceção. Um teste de histórico que falha sem mostrar a saída do git é um teste
que custa uma hora para diagnosticar.

## Q7 — Dependências

`subprocess` é stdlib, e `git.py` já o usa desde o M1. **Nenhum dos três peers legíveis usa
biblioteca de git**: gitleaks chama `exec.CommandContext` (`sources/git.go:91`), talisman
chama `exec.Command` (`gitrepo/gitrepo.go:332`), ggshield chama `subprocess` através de
`utils/git_shell.py`. Três implementações independentes convergindo no binário.

**Veredito: nenhuma dependência nova.** `docs/PRD.md § NFR-1` preservado.

## Coverage Corner 1 — Integration tests

Q3 (fingerprint como identidade do achado) e Q6 (fixtures). O padrão do ggshield —
`Repository` como fábrica, erro do git impresso antes de relançar — é diretamente
transportável para `tests/conftest.py`, que já tem a base do M1.

## Coverage Corner 2 — Dependencies

Q7. Zero dependências novas; `subprocess` sobre o binário do git, convergência dos 3 peers.

## Coverage Corner 3 — Tools

Q4. Repositório vazio resolvido por `--all` (exit 0 em vez de 128). Custo medido: 5.000
commits em 0,115 s; enumeração de blobs custa 2×.

## Coverage Corner 4 — Techniques

Q1 (dois comandos, flags, campos do achado), Q2 (talisman enumera objetos, não diffs),
Q5 (a lacuna do merge, medida).

## Cross-cutting Comparison

| Dimensão | gitleaks | talisman | ggshield | Decisão para o gitsafety |
|---|---|---|---|---|
| Estratégia | Diffs (`log -p`) | Objetos (`ls-tree` + `cat-file`) | `subprocess` genérico | Diffs — o texto já vem como "linhas adicionadas", que é o que o matcher do M1 consome |
| Comando principal | `log -p -U0 --full-history --all --diff-filter=tuxdb` (`git.go:93-94`) | `ls-tree -r` + `cat-file -p` (`gitrepo.go:238,341`) | camada em `git_shell.py` | `log -p -U0 --all --diff-merges=first-parent` (ADR B1) |
| Leitura de conteúdo íntegro | `cat-file blob` (`git.go:208`) | `cat-file --batch` (`git_readers.go:42`) | — | Não necessário no M5: nossas 53 regras são de linha única |
| Identidade do achado | `commit:file:rule:line` (`detect.go:714`) | — | — | `(regra, segredo, arquivo)` + commit mais antigo (ADR B2) |
| Lacuna do merge | **presente** (medida: 0 de 1) | ausente — enumerar objetos não depende do git emitir diff | não avaliado (deny-glob) | fechada por `--diff-merges=first-parent` |
| Repo vazio | `--all` evita o exit 128 | — | — | `--all` (resolve o DoD nº 4 sem caso especial) |
| Dependência de git | binário (`exec.CommandContext`) | binário (`exec.Command`) | binário (`subprocess`) | binário — convergência dos três |

A comparação é **assimétrica por desenho** (ADR D1 do plano): 1h para gitleaks, 0h45 para
talisman, 0h30 para ggshield, proporcional à densidade de evidência. O ggshield contribuiu
sobretudo com o padrão de fixture, porque sua parte central está sob o deny-glob.

## Recommendations

Em ordem de importância para a implementação do M5:

1. **Não copiar a flag do gitleaks.** Usar `git log -p -U0 --all --diff-merges=first-parent`.
   Fecha a lacuna do merge (medida: 0 → 1) sem custo (0,113 s contra 0,115 s).
2. **Manter `--all`**, que resolve o repositório vazio sem código de caso especial: exit 0 e
   saída vazia, contra exit 128 e `fatal` sem ela.
3. **Não usar `--diff-filter=tuxdb`.** Não consegui citar a razão dela no gitleaks, e flag
   sem razão citável não entra por imitação.
4. **Reusar `parse_added_lines` do `staged.py`.** O formato de saída é o mesmo diff
   unificado; se ele não servir, a decisão de reuso precisa ser revista, não contornada.
5. **Deduplicar por `(regra, segredo, arquivo)` reportando o commit mais antigo**, e dizer
   na saída **em quantos commits** a ocorrência aparece — para que o colapso seja visível.
6. **Estender `tests/conftest.py`** com uma fábrica de histórico no padrão do
   `ggshield/tests/repository.py`, imprimindo stdout e stderr do git antes de relançar.
7. **Documentar o custo** em vez de adicionar flags de tuning, como o roadmap manda:
   5.000 commits em 0,115 s.
8. **Registrar a lacuna do reflog** no README ou no backlog: um segredo em commit reescrito
   segue recuperável localmente por ~90 dias e `--all` não o vê.

## ADRs

### D1 — `--diff-merges=first-parent` em vez de copiar a flag do gitleaks

**Decisão:** usar `git log -p -U0 --all --diff-merges=first-parent`.

**Rationale:** fecha a lacuna medida do merge (0 → 1 ocorrência) ao custo de 0,113 s contra
0,115 s do padrão — ou seja, sem custo. `-m` também fecha, mas emite o diff uma vez **por
pai**, duplicando cada achado de merge e empurrando o problema para a deduplicação.

**Alternativas consideradas:** (a) copiar `--full-history --diff-filter=tuxdb` do gitleaks —
herda uma lacuna medida e uma flag cuja razão não consegui citar; (b) `-m` — dobra achados
de merge; (c) enumerar blobs via `rev-list --objects` — não tem a lacuna e é a estratégia do
talisman, mas custa 2× e devolve arquivos íntegros, o que muda o significado de "linha" no
achado e obrigaria a revarrer conteúdo não modificado a cada commit.

**Consequences:** achados vindos de merge terão a linha do diff de primeiro pai. Um segredo
que existe em **ambos** os pais e é resolvido no merge aparecerá uma vez pelo pai, não pelo
merge — comportamento correto, já que o pai é onde ele foi introduzido.

### D2 — Dedup por `(regra, segredo, arquivo)` e reporte do **primeiro** commit

**Decisão:** deduplicar como o roadmap manda, e reportar o commit **mais antigo** em que a
ocorrência aparece, com autor e data.

**Rationale:** a ação que o produto pede é revogar a chave no provedor (`README.md`), e essa
ação é única por segredo — não por commit. Reportar N achados do mesmo segredo em N commits
seria o "poluir a saída" que o Risco M5 nº 2 nomeia. O commit mais antigo é o mais útil dos
N: responde "desde quando esta chave está exposta?", que é o que decide a urgência.

**Alternativas consideradas:** (a) fingerprint do gitleaks incluindo commit — não deduplica
entre commits; útil para auditoria contínua, ruído para varredura pontual; (b) reportar o
commit mais recente — responde a pergunta menos útil; (c) reportar todos — o ruído que o
risco nomeia.

**Tensão registrada:** a lição do M4 é que colapsar ocorrências esconde lugares de onde
remover. Aqui a diferença é que a remoção não é por lugar — a chave é revogada uma vez. Mas
a saída deve dizer **quantos commits** contêm a ocorrência, para que o colapso seja visível
em vez de silencioso.

### D3 — Reusar `scanner.is_allowed` e `BUILTIN_RULES` sem exceção

**Decisão:** o `--history` alimenta o mesmo matcher; muda a fonte do texto, nunca o
casamento.

**Rationale:** o DoD do `ROADMAP.md § M5` exige literalmente. E o M4 mediu o custo de dois
caminhos de varredura sobre a mesma coisa: cinco defeitos de reconciliação em três rodadas.

**Consequences:** `--history` e `--staged` compartilham o parser de diff unificado que
`staged.py` já tem — a diferença é o comando que gera o diff. Reusar `parse_added_lines` é o
teste dessa decisão: se ele não servir, a decisão precisa ser revista, não contornada.

## Lacunas declaradas

| Lacuna | Situação |
|---|---|
| `ggshield/ggshield/cmd/secret/` | Inacessível pelo deny-glob; nenhuma afirmação feita sobre ele |
| `detect-secrets`, `ripsecrets`, `secretlint` | Inacessíveis desde o M0 |
| Razão do `--diff-filter=tuxdb` no gitleaks | Não localizei comentário explicando; não inferi |
| Reflog | `--all` não cobre; segredo em commit reescrito segue local por ~90 dias |
| Custo com muitos merges | O repo sintético não tem merges; o número de `--diff-merges` não foi medido sob carga de merge |

## Referências

- `knowledge-base/references/gitleaks/sources/git.go` — travessia, `:91`, `:93-94`, `:139`, `:208`
- `knowledge-base/references/gitleaks/report/finding.go` — campos do achado, `:38-47`
- `knowledge-base/references/gitleaks/detect/detect.go:714` — composição do fingerprint
- `knowledge-base/references/gitleaks/detect/detect_test.go:884` — fingerprint em teste
- `knowledge-base/references/talisman/gitrepo/gitrepo.go` — `:238`, `:332`, `:341`
- `knowledge-base/references/talisman/gitrepo/git_readers.go:42` — `cat-file --batch`
- `knowledge-base/references/ggshield/tests/repository.py` — `:1-50`, fábrica de repositório
- `knowledge-base/references/ggshield/ggshield/utils/git_shell.py` — camada de subprocess
