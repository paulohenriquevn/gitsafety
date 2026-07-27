---
slug: m1-hook-pre-commit
milestone_id: M1
date: 2026-07-27
plan: knowledge-base/plans/m1-hook-pre-commit-plan.md
blueprint: knowledge-base/discoveries/blueprints/m1-pre-commit-hook-blueprint.md
status: IMPLEMENTATION_COMPLETE
---

# M1 — Log de implementação

## Resumo

Seis tasks entregues em ordem de dependência, cada uma com RED antes de GREEN. 144 testes
(52 novos), todos verdes. Zero dependências de runtime acrescentadas.

## Tasks e evidência

| Task | Testes | Evidência de que fechou |
|---|---|---|
| T1.1 — `git.py` | 11 | `subprocess` confinado a um arquivo (verificado por `grep`); `git` ausente e "não é repo" são erros distintos |
| T1.2 — `staged.py` | 15 | Comando dos peers com 4 flags defensivas; parser com hunk múltiplo, arquivo novo, binário e `noprefix` |
| T2.1 — `scan --staged` | 5 | Exit 0/1/2; mutuamente exclusivo com o posicional; `--help` atualizado |
| T2.2 — `install` | 15 | Recusa hook alheio sem tocá-lo; idempotente; `0700`; respeita `core.hooksPath` |
| T3.1 — e2e | 7 | `git commit` real bloqueado; `--no-verify` passa; commit **não existe** depois |
| T3.2 — benchmark | 3 | Números abaixo |

## Benchmark — a hipótese do M0, medida

**Ambiente:** i7-1355U, 16 GB, Python 3.10.12, git 2.34.1, Linux 6.8.0.
**Método:** medição **pareada** — `git commit` com o hook menos `git commit` sem ele, no
mesmo conteúdo, alternando as duas condições a cada rodada (3 rodadas) para que uma
variação de carga da máquina contamine as duas por igual em vez de enviesar uma.

| Arquivos no commit | Sem hook | Com hook | **Overhead** |
|---|---|---|---|
| 1 | 0,0033 s | 0,0459 s | **0,0426 s** |
| 20 | 0,0040 s | 0,0377 s | **0,0337 s** |
| 200 | 0,0053 s | 0,0501 s | **0,0448 s** |

**A hipótese do M0 está confirmada.** O M0 mediu 0,0145 ms por arquivo e **concluiu por
inferência** que o custo dominante do M1 seria o startup do interpretador, não a
varredura. A medição confirma: o overhead é **plano** — 200× mais arquivos custam o
mesmo. A variação entre as três medições (0,0337 a 0,0448 s) é maior que qualquer
tendência com o número de arquivos, que é exatamente a assinatura de um custo constante.

**Contra o orçamento:** `docs/PRD.md § NFR-2` promete `< 1 s`. Medido: **~0,04 s**, cerca
de **25× abaixo**.

**Onde a otimização deveria olhar, se um dia precisar:** no startup do processo Python, não
no scanner. Reduzir imports no caminho de `scan --staged` teria efeito; otimizar a regex
não teria nenhum.

**O que este benchmark NÃO mede:** disco frio, repositório com histórico grande (o
`git diff --staged` compara com HEAD, e um HEAD distante pode custar mais), Windows, e
commit com hook **disparando** (mede-se o fluxo normal, que é o que se paga todo dia).

## Verificação dos DoD do `ROADMAP.md § M1`

| # | DoD | Status | Evidência |
|---|---|---|---|
| 1 | `install` escreve `.git/hooks/pre-commit` executável chamando `scan --staged` | ✅ | Conteúdo real: `#!/bin/sh` + `gitsafety scan --staged "$@"`, permissão `-rwx------` |
| 2 | Hook preexistente → recusa, exit 2, imprime a linha | ✅ | Execução real: exit 2, hook alheio **intacto** depois |
| 3 | `scan --staged` lê o conteúdo em stage, não o disco | ✅ | `test_secret_only_on_disk_does_not_block_the_commit`, unitário e e2e |
| 4 | Teste de integração: commit bloqueado, `--no-verify` passa | ✅ | 7 testes contra `git` real; `rev-list --count` = 0 após bloqueio |
| 5 | Fora de repositório git → mensagem específica, exit 2 | ✅ | `NotAGitRepositoryError`, distinto de `GitUnavailableError` |

## Desvios em relação ao plano

| Desvio | Motivo |
|---|---|
| `HookPathIsDirectoryError` virou classe própria (o plano previa dentro de `HookExistsError`) | A remediação é outra: apagar um diretório é decisão do usuário, não algo a sugerir junto com "acrescente esta linha". |
| Fixture `gitsafety_on_path` acrescentada | O ADR D8 faz `install_hook` recusar quando o comando não está no PATH; os testes precisam montar essa pré-condição, senão testariam o próprio D8. |
| `test_install_fails_when_gitsafety_is_not_on_path` usa PATH só com o diretório do git | Zerar o PATH inteiro removeria também o `git`, e a instalação falharia antes, em `is_git_repository` — o D8 nem seria alcançado. |
| `parse_added_lines` tolera cabeçalho sem prefixo `a/`/`b/` | Passamos `--src-prefix`/`--dst-prefix` para evitar o caso, mas o parser não deve quebrar se o diff vier de outra origem. |
| `benchmarks/bench_hook.py` ganhou `ensure_gitsafety_on_path()` | Mesmo motivo da fixture: `install_hook` checa o PATH do processo atual, de propósito. |

## Limitações conhecidas, declaradas

1. **Segredo preexistente não é reportado pelo hook** (ADR D1) — se o arquivo já tinha o
   segredo commitado e o usuário edita outra linha, o hook não reclama. Deliberado, e
   agora documentado no README com o encaminhamento (`gitsafety scan` na pasta).
2. **Windows não exercido** — o `docs/PRD.md § NFR-6` promete, mas o M1 foi implementado e
   testado só em POSIX. Registrado como Unresolved Question Q1 do plano.
3. **O hook depende do PATH** — se o usuário apagar o venv depois de instalar, o hook
   quebra. Mitigado por falhar cedo na instalação (D8); o resíduo é aceito.
4. **Uma única regra de detecção** — segue sendo só a chave AWS. Catálogo é o M2.

<promise>IMPLEMENTATION_COMPLETE</promise>
