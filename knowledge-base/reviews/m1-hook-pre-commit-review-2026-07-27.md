# Review — M1: hook de pre-commit

**Data:** 2026-07-27 · **Slug:** `m1-hook-pre-commit` · **Milestone:** M1
**Base do diff:** `v0.1.0..HEAD` — 5 commits
**Domínio:** CLI + integração com git

> **Método declarado.** Verificadores determinísticos, hard gates do `cycle-review` e
> cross-validation manual entre plano, código, testes e execução real. Os 5-7 agentes
> especialistas do `cycle-review` **não** foram gerados. A limitação é a mesma do M0 e a
> consequência é a mesma: esta revisão não tem olhos independentes. Antes de um release
> público (M6), revisão humana é recomendada.

## Hard gates

| # | Gate | Resultado |
|---|---|---|
| 1 | Testes verdes | ✅ 144/144 |
| 2 | Nenhum segredo commitado | ✅ 0 arquivos casando `.env`/`credentials*`/`*.pem`/`*.key` |
| 3 | Sem commit direto em `main` | ✅ branch `develop` |
| 4 | Nenhum trailer `Co-Authored-By` | ✅ 0 em 5 commits |
| 5 | `CHANGELOG.md` atualizado | ✅ |

**Nenhum BLOCKER.**

## Cross-validation: plano ↔ implementação ↔ teste ↔ execução

| # | Requisito | Verificação | Status |
|---|---|---|---|
| 1 | `install` escreve hook executável chamando `scan --staged` | Execução real: `#!/bin/sh` + `gitsafety scan --staged "$@"`, `-rwx------` | ✅ |
| 2 | Hook preexistente → recusa, exit 2, imprime a linha | Execução real: exit 2, hook alheio **byte a byte intacto** | ✅ |
| 3 | `--staged` lê o índice, não o disco | Unitário + e2e: segredo só no disco não bloqueia | ✅ |
| 4 | Commit bloqueado; `--no-verify` passa | 7 testes e2e; `rev-list --count == 0` após bloqueio | ✅ |
| 5 | Fora de repo git → exit 2 específico | `NotAGitRepositoryError` ≠ `GitUnavailableError` | ✅ |
| 6 | `git` ausente ≠ "não é repositório" | Dois testes negativos distintos | ✅ |
| 7 | `core.hooksPath` respeitado | `git rev-parse --git-path hooks`; teste dedicado | ✅ |
| 8 | Instalação idempotente | Marcador (D4); execução real: exit 0 duas vezes | ✅ |
| 9 | PATH validado na instalação | `CommandNotOnPathError`; teste com PATH só do git | ✅ |
| 10 | Segredo mascarado no modo staged | Saída real do commit bloqueado: `AKIA••••••••••••MPLE` | ✅ |
| 11 | Sem dependência de runtime nova | `dependencies = []` inalterado | ✅ |
| 12 | Latência `< 1 s` | Medido ~0,04 s (25× de folga) | ✅ |
| 13 | Linha correta no diff | Testes de hunk múltiplo, arquivo novo, `noprefix` | ✅ |
| 14 | Remover segredo não gera finding | `test_removed_lines_are_not_reported` | ✅ |
| 15 | `--help` não anuncia `--history` | Teste dedicado, mantido do M0 | ✅ |

**15/15.**

## Fronteiras de arquitetura

- `subprocess` aparece **apenas** em `git.py` — verificado por `grep -rn` em `src/`. ✅
- Domínio (`errors`, `rules`, `finding`) não importa de aplicação nem de interface. ✅
- `hook.py` é o único módulo que escreve no sistema de arquivos do usuário. ✅
- Nenhuma abstração especulativa: `git.py` não tem protocolo com implementador único (D7). ✅

## Wiring triad

| Símbolo novo | Chamador em produção | Teste |
|---|---|---|
| `run_git`, `is_git_repository`, `repo_root`, `hooks_dir` | `staged.py`, `hook.py` | 11 |
| `staged_diff`, `parse_added_lines`, `scan_staged` | `cli.main` | 15 |
| `install_hook`, `hook_path_for`, `is_our_hook` | `cli.main` | 15 |

**Sinal observável em runtime:** o caminho do hook impresso na instalação, e a saída do
commit bloqueado chegando ao terminal do usuário.

## Achados

### MEDIUM-1 — 19 parâmetros de fixture não usados *(corrigido nesta revisão)*

**Encontrado pelo `/code-quality`:** 19 achados HARD de `dead_code_unallowlisted_python`,
todos parâmetros `gitsafety_on_path` declarados e nunca referenciados no corpo do teste —
a fixture age por efeito colateral (`monkeypatch` do PATH).

**Corrigido**, não isentado: convertido para `@pytest.mark.usefixtures("gitsafety_on_path")`,
que é o idioma do pytest para exatamente este caso. Além de eliminar o achado, deixa a
intenção explícita — "este teste precisa do efeito colateral desta fixture".

Veredito do gate: `FAIL_HARD` → `FAIL_SOFT` com **HARD = 0**.

### LOW-1 — 6 soft caps no ferramental, sob ADR 0001

Os mesmos do M0: parâmetros exigidos por contrato de interface em `.claude/`. Nenhum no
produto. Sunset 2026-10-25.

### INFO-1 — o hook depende de o `gitsafety` continuar no PATH

Se o usuário apagar o venv depois de instalar, o hook quebra e o erro vem do shell. O ADR
D8 mitiga movendo a falha para a instalação, mas o resíduo permanece e está declarado no
log de implementação. Não é corrigível sem amarrar o hook a um caminho absoluto, o que o
ADR D2 rejeitou por motivo mais forte.

### INFO-2 — Windows não exercido

`docs/PRD.md § NFR-6` promete Windows; o M1 foi implementado e testado só em POSIX.
Registrado como Unresolved Question Q1 do plano. Elevar para suporte verificado exige
runner Windows no CI.

## Verdicto

**`READY_TO_MERGE`**

Zero BLOCKER, zero HIGH. Um MEDIUM encontrado e corrigido dentro da revisão; um LOW sob
ADR com sunset; dois INFO rastreados.

O milestone entrega o que prometeu: **a partir daqui o produto protege de verdade**, com
prova ponta a ponta contra `git commit` real e com o custo medido em ~0,04 s.
