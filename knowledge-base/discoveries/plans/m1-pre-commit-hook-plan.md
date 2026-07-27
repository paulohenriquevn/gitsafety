# Discovery Plan: Mecânica do hook de pre-commit (M1)

> **Version 1.1** (2026-07-27) — absorve os 3 MUST FIX de
> `knowledge-base/reviews/m1-pre-commit-hook-edge-cases-2026-07-27.md`: EC-1 (existe uma
> quarta estratégia de coexistência — delegação em cadeia), EC-2 (o comando git literal
> está em `sources/`, não em `cmd/protect.go`) e EC-3 (Q1 precisa perguntar em que
> linguagem o hook é escrito). O SHOULD TEST virou checkpoint.
>
> **Version 1.0** — Investiga como peers maduros instalam e executam um hook de
> pre-commit: onde o hook é escrito, como se comportam diante de um hook já existente,
> como leem o **conteúdo em stage** (e não o disco), e como testam isso ponta a ponta.
> Projetos em escopo: `talisman` (peer direto — seu propósito É o hook), `ggshield`
> (comando `install` em Python) e `gitleaks` (comando `protect`, que varre o stage). A
> saída trava as decisões do M1 antes do `/to-plan`.

**Slug:** `m1-pre-commit-hook`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 3h (quebra por projeto em D1)

## Context

O `ROADMAP.md § M1` é o milestone em que o produto passa a proteger de verdade: até o M0
o gitsafety varre quando alguém pede; a partir do M1 ele intercepta o commit. Os dois
riscos nomeados no roadmap são específicos e caros:

- **Risco M1 nº 1** — "ler do disco em vez de `git show :arquivo` deixa passar segredo
  quando o `git add -p` colocou só parte do arquivo em stage — falso negativo difícil de
  perceber". É o risco central: o hook validaria conteúdo diferente do que será commitado.
- **Risco M1 nº 2** — "bit de execução do hook em Windows / repositórios com
  `core.hooksPath` customizado".

Some-se o `docs/PRD.md § FR-2`: o `install` **recusa** quando já existe um `pre-commit`,
em vez de sobrescrever. Destruir o hook de outra ferramenta é o tipo de dano que faz o
usuário desinstalar e nunca mais voltar.

O blueprint do M0
(`knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md`)
já travou o contrato de exit code e a forma da saída; esta descoberta acrescenta a camada
de integração com o git.

## Objective

O blueprint deve permitir decidir, antes de escrever o M1, **onde** escrever o hook,
**como** detectar e recusar um hook existente, **como** ler o conteúdo em stage sem tocar
o disco, e **qual forma de teste** prova que um commit real é bloqueado — cada decisão com
precedente citado em `arquivo:linha`.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões respondidas com citação a `knowledge-base/references/`
- [ ] Tabela comparativa preenchida para cada projeto em escopo
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope (por projeto de referência)

| Projeto | Subdiretórios em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/talisman/` | `cmd/pre_commit_hook.go`, `cmd/talisman.go`, `cmd/runner.go`, `cmd/acceptance_test.go`, `install.sh`, `global_install_scripts/`, `gitrepo/`, `git_testing/` | **Peer direto.** O propósito do talisman É o hook; ele trata instalação, hook preexistente e leitura do stage em profundidade. |
| `knowledge-base/references/ggshield/` | `ggshield/cmd/install.py`, `ggshield/core/git_hooks/`, `tests/` | Comando `install` em Python — mesma stack, mesmo problema de escrever arquivo executável. |
| `knowledge-base/references/gitleaks/` | `cmd/protect.go`, `sources/` | `protect` varre o stage; contrato de leitura de conteúdo staged. |

### Out-of-Scope (explícito)

| Projeto / Subdir | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | Inacessíveis pelo deny-glob `Read(**/*secret*)` — mesma limitação declarada no blueprint do M0. |
| `ggshield/ggshield/cmd/secret/` | Mesmo bloqueio. Q2 e Q3 ficam restritas a `core/` e `cmd/install.py`. |
| `ggshield/ggshield/core/git_hooks/prepush.py`, `prereceive.py` | Hooks de push e de servidor — o M1 é pre-commit apenas. |
| `talisman/global_install_scripts/` além do fluxo de instalação | Instalação global via `core.hooksPath` é contexto do Risco nº 2, não o alvo principal. |
| `gitleaks/detect/`, `gitleaks/config/` | Motor de detecção e config TOML — cobertos no M0 ou cortados no `docs/PRD.md § 10`. |
| Qualquer projeto não clonado em `knowledge-base/references/` | Nunca afirmar comportamento sem ler a fonte. |

## ADRs

### D1 — Orçamento de tempo e condições de parada

**Decisão:** talisman 1.5h, ggshield 1h, gitleaks 0.5h. Total 3h.

**Rationale:** o talisman recebe o dobro porque é o único peer cujo produto inteiro é o
hook — as decisões dele são as mais transplantáveis para o M1, invertendo a alocação do
M0 (onde ele recebeu o mínimo). ggshield entra pela implementação em Python do `install`.
gitleaks entra só pelo contrato de leitura do stage.

**Alternativas consideradas:** (a) manter a proporção do M0 — rejeitada, o valor relativo
dos peers mudou com o milestone; (b) só talisman — rejeitada, perde a implementação
Python do `install`, que é o que de fato vamos escrever; (c) sem orçamento — rejeitada,
`cycle-discover § Stop conditions` exige condição de parada.

**Stop condition — por questão (obrigatória):** Fase A vazia após 3 variantes de consulta
→ questão marcada BLOCKED com motivo "Fase A exaurida"; seguir para a próxima.

**Stop condition — por projeto (obrigatória):** orçamento esgotado → questões restantes
daquele projeto BLOCKED com motivo "orçamento esgotado". Todos os projetos nesse estado →
`<promise>BLUEPRINT_BLOCKED</promise>`, nunca `BLUEPRINT_COMPLETE`.

**Anti-pattern:** jamais fabricar resposta de Fase B para fechar questão exaurida
(Regra Inquebrável 3).

**Consequences:** questões BLOCKED aparecem explicitamente no blueprint e viram semente da
próxima descoberta.

### D2 — Profundidade da investigação

**Decisão:** leitura integral dos arquivos de fluxo de instalação e de hook
(`cmd/pre_commit_hook.go`, `cmd/install.py`, `install.sh`); Grep dirigido seguido de
leitura por hotspot nos diretórios de teste e de acesso ao git.

**Rationale:** o fluxo de instalação é curto e o valor está no conjunto — ler metade
produz conclusão errada sobre o que acontece quando já existe um hook. Diretórios de teste
são grandes e o valor está em pontos específicos. Aplica `rules/parsimony-ladder.md` rung 1
à própria pesquisa.

**Alternativas consideradas:** (a) ler tudo — estoura o D1; (b) só Grep — produz citação
sem entendimento de intenção, o "deep-research theatre" do
`discover-blueprint-golden-rule.md § 4`.

**Consequences:** respostas de fluxo com alta confiança; respostas de teste citam hotspots
e declaram o que não foi lido.

### D3 — Peers em Go entram como contrato, nunca como código

**Decisão:** de `talisman` e `gitleaks` extrair **comportamento observável** — qual comando
git é invocado, o que acontece com hook preexistente, qual a forma do teste — nunca idioma
de implementação Go.

**Rationale:** transplantar idioma entre linguagens produz código não-idiomático, que
`rules/architecture.md § 6` classifica como abstração vazada. O que viaja é o contrato.
Neste milestone a distinção é mais fina que no M0: o "contrato" inclui **qual invocação de
git** é feita, que é linguagem-agnóstica e é exatamente o núcleo do Risco nº 1.

**Consequences:** citações a talisman/gitleaks descrevem comandos git e comportamento;
recomendações derivadas precisam de tradução explícita para Python.

## Research Questions

| # | Questão | Corner | Projeto(s) | Fase A (mapa amplo) | Fase B (leitura profunda) | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | Onde o hook é escrito e o que é escrito dentro dele? | techniques | ggshield, talisman | Ler `knowledge-base/references/ggshield/ggshield/cmd/install.py` integralmente; Grep por `hooks`, `pre-commit`, `chmod`, `0o` em `knowledge-base/references/talisman/install.sh` | Leitura integral do `install.py` (D2); hotspots no `install.sh` | Caminho do arquivo + conteúdo do script + bit de execução, com `arquivo:linha`. **Incluir (EC-3): em que linguagem o hook é escrito e o que isso implica para o custo de invocação** — o M0 mediu que o startup do interpretador dominaria o custo do M1 |
| Q2 | Como o conteúdo **em stage** é lido, sem tocar o disco? | techniques | gitleaks, talisman | **Alvo primário (EC-2):** Grep pelo símbolo `NewGitDiffCmdContext` e por `git show`, `diff-index`, `ls-files`, `cached` em `knowledge-base/references/gitleaks/sources/` — o comando literal está lá, não em `cmd/protect.go`, que só tem o encanamento da flag. Complementar: `knowledge-base/references/talisman/gitrepo/`; **fallback (EC-4)** `knowledge-base/references/talisman/cmd/runner.go` | Ler cada hotspot; capturar o comando git exato e o porquê | Comando git literal + o que ele devolve + citação. **Núcleo do Risco nº 1** |
| Q3 | O que acontece quando já existe um `pre-commit`? | techniques | ggshield, talisman | Grep por `exists`, `backup`, `overwrite`, `force`, `append` em `knowledge-base/references/ggshield/ggshield/cmd/install.py` e `knowledge-base/references/talisman/install.sh` | Ler o ramo de decisão inteiro em cada um | Comportamento + mensagem ao usuário + citação. Estratégias possíveis (EC-1): recusa / backup / anexa / **delega em cadeia com propagação de exit code** — esta última existe em `install.py:22-31` e é a mais relevante para o nosso FR-2, porque permite coexistir com o hook do usuário em vez de recusar. Comparar recusar × encadear explicitamente |
| Q4 | Como o talisman testa que um commit real é bloqueado? | tests | talisman | `ls knowledge-base/references/talisman/git_testing/` + Grep por `func Test` em `knowledge-base/references/talisman/cmd/acceptance_test.go` | Ler um teste de aceitação ponta a ponta com seu helper de repositório | Forma do teste: como o repo temporário é criado, como o commit é disparado, o que é asserido |
| Q5 | Como o ggshield testa o comando `install`? | tests | ggshield | Grep por `install` em `knowledge-base/references/ggshield/tests/` | Ler 2-3 testes representativos | Nível do teste (unit/functional) + o que é mockado vs real |
| Q6 | O caminho do hook adiciona dependência de runtime? | deps | ggshield | SKIP Fase A — forma textual. Ler os imports de `knowledge-base/references/ggshield/ggshield/cmd/install.py` | Classificar cada import em stdlib / terceiro | Lista de imports + veredito: dá para fazer só com stdlib? |
| Q7 | Como lidam com `core.hooksPath` e com o bit de execução em plataformas diferentes? | tools | talisman, ggshield | Grep por `hooksPath`, `core.hooks`, `chmod`, `stat`, `windows`, `platform` em `knowledge-base/references/talisman/global_install_scripts/` e `knowledge-base/references/ggshield/ggshield/cmd/install.py` | Ler cada hotspot | Tabela: plataforma/config → tratamento → citação. **Núcleo do Risco nº 2** |

**Orçamento de questões:** 7 (faixa 5-10 ✓), máximo 3 por corner ✓, mínimo 1 por corner ✓.

## Coverage Matrix

| Corner | Questões mapeadas | Status |
|---|---|---|
| Integration tests | Q4, Q5 | Coberto |
| Dependencies | Q6 | Coberto |
| Tools | Q7 | Coberto |
| Techniques | Q1, Q2, Q3 | Coberto |

**Cobertura: 4/4 corners cobertos (100%)**

## Halt-loop Checkpoints

| Checkpoint | Asserção | Ação em caso de falha |
|---|---|---|
| Antes de responder Qx | Todo path da Fase A existe em disco | BLOCKED com motivo "path não encontrado"; seguir |
| Orçamento de Fase A | ≥ 1 hotspot OU 3 variantes tentadas | BLOCKED com motivo "Fase A exaurida" |
| Depois de responder Qx | Seção de Qx tem ≥ 1 citação `arquivo:linha` | Reiterar Qx (1 tentativa) |
| Q2 é irrenunciável | Q2 respondida com o **comando git literal**, não com paráfrase | Reiterar; é o núcleo do Risco nº 1 e paráfrase não permite implementar |
| Fallback do talisman (EC-4) | Q2 tentou `gitrepo/` E, se vazio, `cmd/runner.go` | Só marcar BLOCKED após as duas tentativas |
| Estratégia de coexistência (EC-1) | Q3 avaliou explicitamente a delegação em cadeia, não só recusar/sobrescrever | Reiterar Q3 |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação |
| Confiança sobre ggshield | Conclusões que dependeriam de `cmd/secret/` marcadas como confiança reduzida | Reescrever a frase |
| Orçamento por projeto | Orçamento do D1 não esgotado | Marcar restantes BLOCKED; avançar |
| Antes de prometer completo | Os 4 corners com seção preenchida | Recusar a promessa; continuar |

## Acceptance Criteria

- [ ] Todas as 7 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação aponta para path real em `knowledge-base/references/`
- [ ] Q2 responde com o comando git **literal**, transcrito da fonte
- [ ] Nenhuma afirmação sobre os três peers inacessíveis
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M1
- [ ] Orçamento de tempo do D1 respeitado
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m1-pre-commit-hook-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam princípio de projeto — D2 cita `rules/parsimony-ladder.md`, D3 cita
      `rules/architecture.md § 6`, D1 cita a Regra Inquebrável 3
