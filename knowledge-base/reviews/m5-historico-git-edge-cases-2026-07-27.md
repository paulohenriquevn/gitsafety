# Discover Edge Case Review — m5-historico-git

Date: 2026-07-27
Discovery plan analyzed: `knowledge-base/discoveries/plans/m5-historico-git-plan.md`
Research questions analyzed: 7 efetivas (8 declaradas, Q2 dobrada em Q1)
Edge cases found: 6 (MUST FIX: 2, SHOULD TEST: 3, DOCUMENT: 1)

## MUST FIX

### EC-1: Q5 mede "repositório grande" sem definir qual

- **Affected question:** Q5
- **Family:** Method
- **Scenario:** A Fase B diz "medir tempo no próprio repositório do gitsafety e num repo
  grande". O gitsafety tem ~30 commits — não é medição de escala, é ruído de startup. E
  "repo grande" sem alvo declarado vira o que estiver à mão na hora, o que torna o número
  irreprodutível.
- **Impact:** o Risco M5 nº 1 ("repositório grande tornar o comando lento a ponto de ninguém
  rodar") fica sem resposta verificável, e o roadmap já decidiu que a resposta a esse risco é
  **documentar o custo** — o que exige um número honesto.
- **Suggested fix:** declarar os alvos na Fase B de Q5: o próprio gitsafety (~30 commits),
  um dos peers clonados (`knowledge-base/references/gitleaks`, com `--depth 1` — verificar
  se há histórico suficiente; se não, gerar sinteticamente um repo de 5.000 commits) e
  registrar commits/s além do tempo total.

### EC-2: nenhuma questão pergunta o que reportar quando o segredo foi REMOVIDO

- **Affected question:** nenhuma — é lacuna
- **Family:** Coverage
- **Scenario:** O DoD do `ROADMAP.md § M5` exige "teste de integração num repositório onde o
  segredo foi introduzido e depois removido: ainda é detectado". Mas o plano não pergunta
  **como reportar** esse caso. Um achado que diz `config.py:3` confunde: o arquivo atual não
  tem o segredo naquela linha, e o usuário vai procurar onde não está.
- **Impact:** a decisão de formato de saída seria tomada durante a implementação, sem prior
  art — exatamente o erro que o M4 cometeu ao decidir a localização de notebook sem
  perguntar como o gitleaks a resolve.
- **Suggested fix:** estender Q1 para incluir "o que o gitleaks põe no `Finding` de um
  achado histórico (commit, autor, data, e qual caminho)" — a resposta está no mesmo
  `report/finding.go` que Q4 já lê, então não custa orçamento novo.

## SHOULD TEST

### EC-3: Q2 foi dobrada em Q1 mas o halt-loop pode tratá-la como respondida por omissão

- **Affected question:** Q1/Q2
- **Suggested halt-loop checkpoint:** antes de marcar Q1 como `done`, verificar que a
  resposta contém a tabela flag-a-flag; sem ela, Q1 está parcialmente respondida e a dobra
  virou desculpa para não investigar.

### EC-4: `--depth 1` nos clones pode esvaziar a medição e a leitura de histórico

- **Affected question:** Q5, Q7
- **Suggested halt-loop checkpoint:** antes de usar um peer como alvo de medição ou de
  fixture, rodar `git -C <peer> rev-list --count HEAD` e registrar o número. O
  `skills/roadmap-init/SKILL.md` manda clonar com `--depth 1 --filter=blob:none`, então é
  provável que os peers tenham 1 commit — o que os torna inúteis como repositório de teste
  de histórico e exige gerar um sinteticamente.

### EC-5: o deny-glob pode bloquear a leitura do próprio `git_shell.py` em tempo de execução

- **Affected question:** Q5, Q8
- **Suggested halt-loop checkpoint:** ao abrir qualquer path do ggshield, se o `Read` for
  negado, registrar a negação no blueprint em vez de inferir o conteúdo. O caminho
  `ggshield/ggshield/utils/git_shell.py` não contém "secret" e deve passar, mas quem o
  importa pode estar sob `cmd/secret/` — e afirmar sobre código não lido é fabricação.

## DOCUMENT

### EC-6: profundidade desigual entre peers é aceita, mas precisa aparecer no blueprint

- **Accepted risk:** o ADR D1 aloca 1h para gitleaks e 0h30 para ggshield, e o D1 já declara
  a consequência ("o blueprint terá profundidade desigual e precisa dizer isso"). O risco
  aceito é que um leitor futuro trate a comparação como simétrica quando ela não é. A
  mitigação é a própria declaração — não há razão para equalizar o orçamento quando a
  densidade de evidência é desigual.

## Summary

| Questão | Edges | MUST FIX | SHOULD TEST | DOCUMENT |
|---|---|---|---|---|
| Q1/Q2 | 2 | 1 (EC-2) | 1 (EC-3) | 0 |
| Q3 | 0 | 0 | 0 | 0 |
| Q4 | 0 | 0 | 0 | 0 |
| Q5 | 3 | 1 (EC-1) | 2 (EC-4, EC-5) | 0 |
| Q6 | 0 | 0 | 0 | 0 |
| Q7 | 1 | 0 | 1 (EC-4) | 0 |
| Q8 | 1 | 0 | 1 (EC-5) | 0 |
| — | 1 | 0 | 0 | 1 (EC-6) |

**Verdict:** DISCOVERY PLAN NEEDS ADJUSTMENT — dois MUST FIX, ambos baratos: declarar os
alvos de medição de Q5 e estender Q1 para cobrir o formato do achado histórico.
