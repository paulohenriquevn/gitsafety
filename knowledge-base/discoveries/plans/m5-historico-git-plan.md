# Discovery Plan: Histórico do git (M5)

> **Version 1.1** — MUST-FIX de `/discover-edge-cases` absorvidos (EC-1, EC-2).
>
> **Version 1.0** — Investiga como os peers percorrem o histórico do git para achar
> segredos já commitados. **Diferente do M4, aqui há prior art abundante**: os três peers
> legíveis resolvem exatamente este problema, e cada um escolheu um comando de baixo nível
> diferente. A investigação é sobre **qual escolha e por quê**, não sobre inventar.

**Slug:** `m5-historico-git`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 2h30 (quebra em D1)

## Context

O `ROADMAP.md § M5` é a **linha de chegada da V1**: `gitsafety scan --history` percorre o
histórico e reporta commit, autor e data (`docs/PRD.md` FR-17). É o comando que responde à
pergunta que o hook não responde — "a chave que eu commitei mês passado ainda está lá?".

O M1 já estabeleceu a fronteira: `git.py` é o **único** módulo que importa `subprocess`, e
`staged.py` mostrou que `git diff --staged -U0 --no-ext-diff` é o contrato certo para o
index. O M5 precisa do equivalente para o histórico, e a pergunta é qual.

Os dois riscos declarados no roadmap:

- **Risco M5 nº 1** — repositório grande tornar o comando lento a ponto de ninguém rodar.
  O roadmap já decide o que fazer: "se acontecer, é sinal para documentar o custo, não para
  adicionar flags de tuning".
- **Risco M5 nº 2** — o mesmo segredo em vários commits poluir a saída; exige deduplicação
  por (regra, segredo, arquivo).

**Contraste com o M4, e por que ele muda o método.** Naquele milestone nenhum peer parseava
notebook, e a evidência aceita virou execução própria (ADR D2 do plano do M4). Aqui os três
peers legíveis implementam travessia de histórico — `gitleaks/sources/git.go` tem 530
linhas dedicadas a isso. A evidência primária volta a ser **citação `arquivo:linha`**, e
execução própria fica para medir custo.

**Lição do M4 que este plano herda.** Cinco rodadas de review naquele milestone mostraram
que cobertura não pode depender da completude de uma lista escrita por quem implementa. A
pergunta Q5 existe por isso: ela pergunta o que o comando escolhido **não** enxerga, antes
de escolhê-lo.

## Objective

O blueprint deve permitir decidir: qual comando de baixo nível enumera o conteúdo histórico,
como deduplicar sem esconder ocorrência, o que reportar por achado, e qual o custo real.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões respondidas com citação `arquivo:linha` em
      `knowledge-base/references/` ou evidência de execução reproduzível
- [ ] Tabela comparativa dos três peers preenchida
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope

| Fonte | Em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/gitleaks/sources/git.go` (530 ln) | Travessia completa | A implementação mais madura; já sabemos que usa `git log -p -U0 --full-history --all --diff-filter=tuxdb` (linhas 93-94) e `git cat-file blob` (linha 208) — falta saber **por que as duas** |
| `knowledge-base/references/gitleaks/sources/git_test.go` (158 ln) | Como se testa travessia | Corner de testes de integração |
| `knowledge-base/references/gitleaks/report/finding.go` (126 ln) | Campo `Fingerprint` (linha 47) | Corner de dedup — como identificam um achado unicamente |
| `knowledge-base/references/talisman/gitrepo/gitrepo.go` (342 ln) | Travessia alternativa | Segunda opinião independente |
| `knowledge-base/references/talisman/gitrepo/git_readers.go` (146 ln) | Leitura de conteúdo histórico | Como lê blob sem checkout |
| `knowledge-base/references/talisman/gitrepo/gitrepo_test.go` | Fixtures de repositório | Corner de testes |
| `knowledge-base/references/ggshield/ggshield/utils/git_shell.py` (535 ln) | Camada de shell em Python | **O peer da nossa linguagem** — o que Python impõe que Go não impõe |
| `knowledge-base/references/ggshield/tests/repository.py` (85 ln) | Fábrica de repositório de teste | Corner de ferramentas |
| `src/gitsafety/git.py`, `staged.py` | Fronteira já estabelecida | O M5 estende o que o M1 desenhou |

### Out-of-Scope (explícito)

| Item | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | Inacessíveis pelo deny-glob de `.claude/settings.json` — limitação herdada desde o M0 |
| `ggshield/ggshield/cmd/secret/` | Mesmo deny-glob, apesar de ser a parte mais relevante do ggshield |
| Biblioteca `pygit2` / `GitPython` | Seria a **segunda** dependência de runtime; o `docs/PRD.md § NFR-1` autoriza uma, gasta no M3 |
| Reescrita de histórico (`filter-repo`, `BFG`) | Fora do escopo: nós **achamos**, não removemos. O `README.md` manda revogar a chave |
| Varredura de repositório remoto | O `docs/PRD.md § 10` cortou; V1 é local |
| Formatos de relatório (SARIF, JUnit) | Cortados no `docs/PRD.md § 10` |

## ADRs

### D1 — Orçamento e condições de parada

**Decisão:** gitleaks 1h, talisman 0h45, ggshield 0h30, medição própria 0h15. Total 2h30.

**Rationale:** a alocação é proporcional à densidade de evidência. O gitleaks tem 530 linhas
dedicadas ao problema e é a fonte primária; talisman dá a segunda opinião independente que o
`cycle-discover § Anti-patterns` exige ("um blueprint precisa de ≥ 2 referências
independentes"); ggshield tem menos código relevante legível, mas é **o único em Python**, e
a diferença de linguagem é o que revela o que o subprocess impõe a nós.

**Alternativas consideradas:** (a) dividir igual entre os três — desperdiçaria tempo no
ggshield, cuja parte central está bloqueada pelo deny-glob; (b) só gitleaks — violaria o
mínimo de duas referências independentes; (c) sem orçamento — o `cycle-discover § Stop
conditions` exige.

**Stop condition — por questão:** Fase A vazia após 3 variantes de busca → BLOCKED com motivo.

**Stop condition — por projeto:** orçamento esgotado → questões restantes BLOCKED. Todas
nesse estado → `<promise>BLUEPRINT_BLOCKED</promise>`.

**Anti-pattern:** jamais fabricar resposta de Fase B (Regra Inquebrável 3).

**Consequences:** o blueprint terá profundidade desigual entre os peers, e precisa dizer isso
explicitamente em vez de aparentar simetria.

### D2 — Sem segunda dependência: `subprocess` sobre o git instalado

**Decisão:** a travessia usa o binário do `git` via `subprocess`, como já faz `git.py`.
`pygit2` e `GitPython` não entram.

**Rationale:** `rules/parsimony-ladder.md` rung 4 — a dependência já instalada é o próprio
git, que o produto já exige (`is_git_repository` do M1 depende dele). E o `NFR-1` está
esgotado desde o M3. Os três peers fazem o mesmo: gitleaks (`exec.CommandContext`,
`git.go:91`), talisman (`gitrepo.go`) e ggshield (`git_shell.py`) todos chamam o binário.
Quando os três peers independentes convergem, a escolha deixa de ser preferência.

**Alternativas consideradas:** (a) `pygit2` — libgit2 daria enumeração de objetos mais
rápida e sem parsing de texto, mas custa a segunda dependência e uma extensão C que quebra o
`pipx install` simples que o `docs/PRD.md § 4` promete; (b) reimplementar leitura de
`.git/objects` — reinventar a roda (Regra 9) num formato com packfiles e deltas.

**Consequences:** herdamos as limitações do CLI do git, incluindo o custo de parsing de texto
e o comportamento em repositório sem commits. A Q4 existe para caracterizar isso.

### D3 — Reusar o matcher, não criar um segundo motor

**Decisão:** o `--history` reusa `scanner.is_allowed` e as mesmas `BUILTIN_RULES`; a
diferença é **de onde vem o texto**, nunca **como ele é casado**.

**Rationale:** o DoD do `ROADMAP.md § M5` exige literalmente "reusa o **mesmo** matcher — sem
segundo motor de detecção". É o mesmo princípio que o M1 aplicou: `is_allowed` existe uma vez
e é chamada pelos dois caminhos, porque duplicá-la garantiria divergência na primeira
mudança. O M4 provou o custo de ignorar isso — dois caminhos varrendo o mesmo arquivo
produziram cinco defeitos de reconciliação em três rodadas.

**Alternativas consideradas:** (a) matcher próprio otimizado para histórico — divergência
garantida e nenhuma evidência de que o ganho existe; (b) reusar só as regras, com supressão
própria — é a divergência parcial que o M4 mostrou ser pior que as duas alternativas puras.

**Consequences:** a Q1 precisa achar **onde** o texto entra no matcher, para que a nova fonte
se encaixe sem tocar no casamento.

## Research Questions

| # | Questão | Corner | Fonte | Fase A | Fase B | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | Qual comando enumera o conteúdo histórico — por que o gitleaks usa **dois** (`log -p` e `cat-file blob`), o que cada flag de `--full-history --all --diff-filter=tuxdb` compra, e **o que ele põe no achado** (commit, autor, data, caminho)? | techniques | gitleaks | Ler `sources/git.go:85-130`, `:200-220`, `:93-94` e `report/finding.go` | Rastrear quem chama cada comando e com qual propósito; testar cada flag num repositório sintético com merge, branch e rename; listar os campos do achado histórico | Tabela comando → o que devolve → quando é usado (`arquivo:linha`) + tabela flag → o que muda (medição própria) + lista de campos do `Finding` |
| Q2 | Como o talisman percorre, e em que a escolha dele difere? | techniques | talisman | Grep `rev-list\|cat-file\|log` em `gitrepo/gitrepo.go` e `gitrepo/git_readers.go` | Ler os hotspots e comparar com Q1 | Comparação lado a lado das duas estratégias |
| Q3 | Como identificam um achado unicamente, para não repetir o mesmo segredo a cada commit? | tests | gitleaks | Ler `report/finding.go:40-60` (campo `Fingerprint`) e grepar quem o compõe | Rastrear a composição do fingerprint | Fórmula do identificador + veredito sobre a dedup do Risco nº 2 |
| Q4 | O que o comando faz em repositório **sem commits**, e qual o custo em escala? | tools | gitsafety + ggshield | Ler `ggshield/utils/git_shell.py` procurando tratamento de erro do git; criar repo vazio | Medir em **três alvos declarados**: repo vazio (0 commits), o próprio gitsafety (~30), e um repo sintético de 5.000 commits gerado por script | Comportamento no repo vazio (DoD nº 4) + tabela commits × tempo × commits/s |
| Q5 | O que o comando escolhido **não** enxerga? | techniques | gitleaks + talisman | Procurar comentários e testes sobre casos não cobertos | Montar repositório com os casos e medir | Lista de lacunas conhecidas, com medição — **não** com adjetivos |
| Q6 | Como se testa travessia de histórico sem fixtures frágeis? | tests | gitleaks + talisman + ggshield | Ler `gitleaks/sources/git_test.go`, `talisman/gitrepo/gitrepo_test.go`, `ggshield/tests/repository.py` | Comparar as três abordagens de fixture | Padrão recomendado para `tests/conftest.py` |
| Q7 | A travessia acrescenta dependência? | deps | stdlib + peers | SKIP Fase A — `subprocess` é stdlib e `git.py` já o usa | Confirmar que nenhum peer legível usa biblioteca de git em vez do binário | Veredito: `subprocess` basta? |

**Orçamento de questões:** 7 (faixa 5-10 ✓), máximo 3 por corner ✓, mínimo 1 por corner ✓.

> **Nota de revisão.** A v1.0 tinha 8 questões, 4 delas em `techniques` — acima do teto do
> `skills/discover-plan/SKILL.md § Question budget`. Eu havia escrito em prosa que a antiga
> Q2 (flags) estava "dobrada dentro de Q1" e mantido as duas linhas na tabela; o gate contou
> as linhas e capou o veredito, corretamente. Declarar uma dobra sem executá-la é
> racionalização — a dobra agora é real: as flags são propriedade do comando que Q1
> identifica, e viraram uma coluna dela.

## Coverage Matrix

| Corner | Questões mapeadas | Status |
|---|---|---|
| Integration tests | Q3, Q6 | Coberto |
| Dependencies | Q7 | Coberto |
| Tools | Q4 | Coberto |
| Techniques | Q1, Q2, Q5 | Coberto |

**Cobertura: 4/4 corners cobertos (100%)**

## Halt-loop Checkpoints

| Checkpoint | Asserção | Ação em caso de falha |
|---|---|---|
| Antes de responder Qx | Todo path da Fase A existe em disco | BLOCKED com motivo "path não encontrado" |
| Citação de peer | Toda afirmação sobre peer tem `arquivo:linha` que resolve | Reescrever com a citação; afirmação sem citação é fabricação |
| Q4 e Q5 são irrenunciáveis | Ambas respondem com **números** ou com casos medidos | Reiterar; sem medição não há requisito verificável |
| Q1 antes de Q2 | A estratégia do gitleaks precede a comparação com talisman | Reordenar; comparar sem a base produz comparação vazia |
| Q5 antes de fechar | A pergunta "o que não vejo?" é respondida ANTES de recomendar um comando | Recusar a recomendação; foi a lacuna que custou 5 rodadas no M4 |
| Q1 completa (EC-2/EC-3) | A resposta de Q1 contém a tabela flag-a-flag **e** a lista de campos do achado | Q1 fica `in_progress`; a dobra de Q2 não pode virar desculpa para não investigar |
| Alvo de medição (EC-4) | Nenhum peer clonado é usado como repositório de histórico — **verificado: os três têm 1 commit** (`--depth 1`) | Gerar repositório sintético; medir em peer de 1 commit não mede nada |
| Leitura negada (EC-5) | Se um `Read` do ggshield for negado pelo deny-glob, registrar a negação no blueprint | Nunca inferir conteúdo de arquivo não lido — é fabricação (Regra Inquebrável 3) |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação |
| Antes de prometer completo | Os 4 corners com seção preenchida | Recusar a promessa; continuar |

## Acceptance Criteria

- [ ] Todas as 7 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação a peer aponta para `arquivo:linha` que resolve
- [ ] Q4 responde com a tabela de três alvos (0, ~30 e 5.000 commits), com commits/s
- [ ] Q1 responde também quais campos compõem um achado histórico (EC-2)
- [ ] Q5 responde com casos medidos, não com "provavelmente cobre tudo"
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M5
- [ ] Comparação entre ≥ 2 peers independentes (`cycle-discover § Anti-patterns`)
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m5-historico-git-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam princípio de projeto — D2 cita `rules/parsimony-ladder.md` rung 4,
      D3 cita o DoD do `ROADMAP.md § M5` e a lição do M4, D1 cita a Regra Inquebrável 3
