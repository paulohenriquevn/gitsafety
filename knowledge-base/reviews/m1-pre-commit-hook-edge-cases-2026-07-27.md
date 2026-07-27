# Discover Edge Case Review — m1-pre-commit-hook

Date: 2026-07-27
Discovery plan analyzed: `knowledge-base/discoveries/plans/m1-pre-commit-hook-plan.md` (v1.0)
Research questions analyzed: 7
Edge cases found: 6 (MUST FIX: 3, SHOULD TEST: 1, DOCUMENT: 2)

> Cada item foi verificado contra os clones antes de ser classificado. Riscos
> especulados que a verificação derrubou estão em § Verificados e descartados.

## MUST FIX

### EC-1: Q3 assume um binário recusar-ou-sobrescrever; existe uma terceira estratégia

- **Questão afetada:** Q3
- **Família:** Interpretation
- **Cenário:** o formato esperado de Q3 lista "recusa / faz backup / anexa". A verificação
  mostrou que `knowledge-base/references/ggshield/ggshield/cmd/install.py:22-31` implementa
  algo diferente: o hook **global** escrito pelo ggshield **encadeia para o hook local**,
  se existir:

  ```sh
  _ggshield_local_hook=$(git rev-parse --git-common-dir)/hooks/{hook_type}
  if [ -f "$_ggshield_local_hook" ]; then
      if ! "$_ggshield_local_hook" "$@"; then
          echo 'Local {hook_type} hook failed, please see output above'
  ```

  Não é recusa, não é backup, não é append: é **delegação em cadeia**, com propagação do
  código de saída do hook delegado.
- **Impacto:** a Fase B classificaria esse comportamento como "outro" e o blueprint
  concluiria que só existem três estratégias, quando a quarta é justamente a mais
  interessante para o nosso `FR-2` — ela permite coexistir com o hook do usuário em vez de
  recusar.
- **Correção sugerida:** acrescentar "delega/encadeia (com propagação de exit code)" ao
  formato esperado de Q3, e pedir explicitamente a comparação entre recusar e encadear.

### EC-2: a Fase A de Q2 aponta para o arquivo errado

- **Questão afetada:** Q2
- **Família:** Reference path
- **Cenário:** Q2 busca a leitura do stage em
  `knowledge-base/references/gitleaks/cmd/protect.go`. A verificação mostra que esse
  arquivo só contém o encanamento da flag — `protect.go:16` declara `--staged`,
  `protect.go:45` lê o booleano e `protect.go:56` delega para
  `sources.NewGitDiffCmdContext(cmd.Context(), source, staged)`. **O comando git literal
  não está lá**, está em `sources/`.
- **Impacto:** Q2 é o núcleo do Risco nº 1 do M1 e o plano exige resposta com o comando
  git **literal**. Parar em `protect.go` produziria "delega para NewGitDiffCmdContext",
  que é paráfrase — exatamente o que o checkpoint de Q2 proíbe.
- **Correção sugerida:** apontar a Fase A de Q2 para o símbolo
  `NewGitDiffCmdContext` em `knowledge-base/references/gitleaks/sources/`, mantendo
  `cmd/protect.go` apenas como ponto de entrada.

### EC-3: Q1 não pergunta em que **linguagem** o hook é escrito

- **Questão afetada:** Q1
- **Família:** Interpretation
- **Cenário:** o formato esperado de Q1 pede "caminho do arquivo + conteúdo do script +
  bit de execução". A verificação mostra que o ggshield escreve um **script shell**
  (`install.py:22-31` é um snippet `sh`), não um arquivo Python — decisão não óbvia para
  um projeto Python, e que tem consequência direta: um hook em shell não paga o startup do
  interpretador quando o `git` decide não executá-lo, e funciona mesmo se o venv não
  estiver ativo.
- **Impacto:** o blueprint poderia recomendar escrever um hook `.py` com shebang, sem
  registrar que o peer escolheu shell e por quê. O M0 mediu que o custo dominante do M1
  seria o startup do interpretador — essa escolha é exatamente sobre isso.
- **Correção sugerida:** acrescentar ao formato esperado de Q1: "em que linguagem o hook é
  escrito e o que isso implica para o custo de invocação".

## SHOULD TEST

### EC-4: Q2 pode achar a leitura do stage do talisman fora de `gitrepo/`

- **Questão afetada:** Q2
- **Checkpoint sugerido no halt-loop:** se a Fase A não encontrar comando git em
  `knowledge-base/references/talisman/gitrepo/`, ampliar uma vez para
  `knowledge-base/references/talisman/cmd/runner.go` antes de marcar BLOCKED. A
  verificação mostrou `gitrepo/git_readers.go`, que é o candidato provável, mas o
  orquestrador pode montar o comando em `runner.go`.

## DOCUMENT

### EC-5: o `install` do ggshield é construído sobre `click`

- **Risco aceito:** `knowledge-base/references/ggshield/ggshield/cmd/install.py:46,53-55`
  usa `click.Choice` para os modos `local`/`global` e para o tipo de hook. O gitsafety usa
  `argparse` (ADR D5 do M0). A **estrutura de decisão** transfere; a expressão dela não.
  Registrar no blueprint em vez de reescrever a questão.

### EC-6: o ggshield instala pre-commit **e** pre-push; o M1 é só pre-commit

- **Risco aceito:** `install.py:53` oferece `["pre-commit", "pre-push"] + AGENTS`. O
  `docs/PRD.md § FR-1` restringe o gitsafety a pre-commit. Ler o fluxo genérico do
  ggshield é útil, mas o blueprint deve resistir a herdar a generalidade: um segundo tipo
  de hook sem caso de uso é YAGNI (`rules/parsimony-ladder.md` rung 1).

## Verificados e descartados

| Risco especulado | Verificação | Resultado |
|---|---|---|
| `ggshield/cmd/install.py` pode ser sobre CI, não sobre pre-commit | `grep pre-commit install.py:53-55` | **Descartado** — `default="pre-commit"`, é o alvo certo |
| `gitleaks/cmd/protect.go` pode não tratar stage | `grep staged protect.go:16,45,56` | **Descartado** — a flag existe; só o comando literal está noutro arquivo (vira EC-2) |
| `talisman/gitrepo/` pode não existir | `ls talisman/gitrepo/` | **Descartado** — existe, com `git_readers.go` |

## Summary

| Questão | Edges | MUST FIX | SHOULD TEST | DOCUMENT |
|---|---|---|---|---|
| Q1 | 1 | 1 (EC-3) | 0 | 0 |
| Q2 | 2 | 1 (EC-2) | 1 (EC-4) | 0 |
| Q3 | 2 | 1 (EC-1) | 0 | 1 (EC-6) |
| Q4 | 0 | 0 | 0 | 0 |
| Q5 | 0 | 0 | 0 | 0 |
| Q6 | 1 | 0 | 0 | 1 (EC-5) |
| Q7 | 0 | 0 | 0 | 0 |

**Veredito:** DISCOVERY PLAN NEEDS ADJUSTMENT — 3 MUST FIX. Nenhum exige questão nova
nem projeto novo: dois são ampliação de formato esperado e um é correção de caminho.
