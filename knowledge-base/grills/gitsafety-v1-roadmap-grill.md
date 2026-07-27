---
slug: gitsafety-v1
date: 2026-07-27
generated_by: roadmap-init
questions_answered: 7
unresolved_dims: []
status: completed
---

# Roadmap grill: gitsafety-v1

> **Desvio declarado do protocolo da skill.** A skill manda 7 perguntas, uma por
> turno. A própria skill instrui a NÃO ser invocada quando *"o escopo já está travado
> em um spec ou RFC"* — e está: `docs/PRD.md` v2.0, escrito e aprovado nesta mesma
> sessão (2026-07-27), responde as 7 dimensões. As dimensões 1-5 e 7 foram
> **pré-preenchidas do PRD**; apenas o que o PRD não travava foi perguntado
> (3 perguntas efetivas). Nenhuma dimensão ficou como TBD.

### Q1/7: Problema raiz

**Fonte:** `docs/PRD.md` § 2 (pré-preenchido, não perguntado).

**Resposta:** Chave de API commitada é incidente caro, comum e **irreversível** — uma
vez no histórico, está exposta para sempre, e bots varrem GitHub público em minutos.
Agravantes: a detecção chega tarde (code review, scan trimestral, ou a fatura) e as
ferramentas existentes são pesadas demais para quem não é de segurança. Vetor
específico mal coberto: **notebooks Jupyter**, onde a chave sobrevive na saída salva
de uma execução antiga.

### Q2/7: Usuários primários

**Fonte:** `docs/PRD.md` § 3 (pré-preenchido).

**Resposta:** Desenvolvedor individual e **cientista de dados** — externos, qualquer
time. Já têm Python; não têm Docker nem Go. Secundário: time de engenharia usando o
mesmo hook mais verificação no CI. **Não é público-alvo:** AppSec fazendo auditoria
forense com baseline e SARIF.

### Q3/7: Escopo da V1

**Fonte:** `docs/PRD.md` § 6 (pré-preenchido) + confirmação da sequência (perguntado).

**Resposta:** `gitsafety install` + `gitsafety scan` com 4 flags (`--staged`,
`--history`, `--config`, `--show-secrets`); catálogo embutido de ≥40 padrões;
`.gitsafety.yml` com `ignore`/`allow`/`rules`; notebooks `.ipynb` incluindo saídas
salvas; segredo mascarado por padrão; exit codes 0/1/2.

### Q4/7: Fora de escopo

**Fonte:** `docs/PRD.md` § 5 (NG1-NG6) e § 10 (pré-preenchido).

**Resposta:** Não reescreve histórico; não é cofre; sem archives; sem decoding
base64/hex; **sem entropia de Shannon**; sem herança de config, regra composta ou
`condition AND/OR`; sem CSV/JUnit/SARIF/template; **sem Docker**.

### Q5/7: Restrições

**Fonte:** `docs/PRD.md` § 7 + decisões da sessão (pré-preenchido).

**Resposta:** Python 3.9+; instalação via `pipx`/`pip`; dependência externa apenas o
parser de YAML; sem Docker; Linux/macOS/Windows; `git` só necessário para `--staged`
e `--history`; no máximo 4 flags no `scan` (NFR-3); latência imperceptível no commit.

### Q6/7: Critério de ship da V1 (mensurável)

**Perguntado nesta sessão.**

**Recomendado:** publicado no PyPI, para que `pipx install gitsafety` funcione para um
terceiro.

**User answer:** **Override — "funciona local, sem publicar".** V1 = `pip install -e .`
no clone + `gitsafety install` + `git commit` com segredo bloqueado. Publicação no
PyPI vira milestone **pós-V1** (M6).

### Q7/7: North-star metric

**Fonte:** `docs/PRD.md` § 8 (pré-preenchido).

**Resposta:** **Retenção do hook** — percentual de repositórios em que o hook continua
instalado 30 dias após a instalação. É a métrica que revela se a ferramenta é
tolerável no dia a dia; ferramenta desinstalada tem taxa de detecção zero.

---

## Perguntas adicionais desta sessão (fora das 7 dimensões)

### Referências SOTA

**Perguntado.** Resposta: **clonar os peers completos** (6 aprovados após curadoria de
10 candidatos). Ver `knowledge-base/references/_catalog.md`.

### Sequência dos milestones

**Perguntado.** Resposta: **hook primeiro** — após M1 o produto já protege de verdade,
mesmo com poucos padrões; cada milestone seguinte aumenta cobertura sobre base que já
funciona.
