# Discovery Plan: Catálogo de padrões de credencial (M2)

> **Version 1.0** — Investiga como um catálogo de detecção com dezenas de padrões é
> construído, validado e mantido sem virar fonte de falso positivo nem de regex
> patológica. Projeto em escopo principal: `gitleaks`, que mantém **131 regras** em
> `cmd/generate/config/rules/` com um gerador de regex e um validador próprios.
> Complementares: `ggshield` (organização de teste em Python) e `talisman` (detectores).

**Slug:** `m2-catalogo-de-padroes`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 3h (quebra por projeto em D1)

## Context

O `ROADMAP.md § M2` pede **≥ 40 padrões**, cada um com teste de acerto e de não-acerto, e
nomeia dois riscos que são justamente os que escalam com o tamanho do catálogo:

- **Risco M2 nº 1** — "um padrão largo demais gera falso positivo e derruba a confiança —
  o dano é maior que o benefício de um padrão a mais". Com 40 padrões, a chance de pelo
  menos um ser largo demais é alta, e o `docs/PRD.md § 4` já declarou que falso positivo
  é o que faz desinstalar a ferramenta.
- **Risco M2 nº 2** — "regex com backtracking catastrófico trava o commit; exige teste com
  limite de tempo". Desde o M1 o motor roda dentro do `git commit`: uma regex patológica
  não é lentidão, é o commit do usuário pendurado.

O M0 plantou a forma (`Rule` congelada com casos anexos, precedente
`gitleaks/cmd/generate/config/rules/adafruit.go`) justamente para este milestone. Agora a
forma vai de 1 para 40+ e as decisões de escala aparecem.

## Objective

O blueprint deve permitir decidir, antes do `/to-plan` do M2: como construir padrões que
não sejam largos demais, como provar que nenhum é patológico, como organizar 40+ regras
sem virar código espalhado, e como medir falso positivo de forma reprodutível.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões respondidas com citação a `knowledge-base/references/`
- [ ] Tabela comparativa preenchida para cada projeto em escopo
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope (por projeto de referência)

| Projeto | Subdiretórios em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/gitleaks/` | `cmd/generate/config/rules/`, `cmd/generate/config/utils/`, `cmd/generate/config/main.go`, `config/gitleaks.toml` | **Peer primário.** 131 regras mantidas com gerador e validador próprios — é o único peer legível que já enfrentou o problema de escala do catálogo. |
| `knowledge-base/references/ggshield/` | `tests/unit/` | Organização de suíte em Python para muitos casos parametrizados. |
| `knowledge-base/references/talisman/` | `detector/` | Segunda opinião sobre estrutura de detector; escopo mínimo. |

### Out-of-Scope (explícito)

| Projeto / Subdir | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | Inacessíveis pelo deny-glob — limitação herdada e declarada desde o M0. |
| `ggshield/ggshield/cmd/secret/` | Mesmo bloqueio. |
| `gitleaks/detect/`, `gitleaks/sources/` | Motor de varredura — coberto nos M0 e M1. |
| `gitleaks/report*`, `gitleaks/cmd/generate/config/main.go` além do fluxo de geração | Formatos de relatório são não-objetivo (`docs/PRD.md § 5 NG5`). |
| Padrões de provedores que o `README.md` não lista | O M2 cobre as 6 categorias declaradas; ampliar o escopo do catálogo é decisão de produto, não de descoberta. |
| Qualquer projeto não clonado em `knowledge-base/references/` | Nunca afirmar comportamento sem ler a fonte. |

## ADRs

### D1 — Orçamento de tempo e condições de parada

**Decisão:** gitleaks 2h, ggshield 0.5h, talisman 0.5h. Total 3h.

**Rationale:** o gitleaks concentra 5 das 7 questões porque é o único peer que mantém um
catálogo grande — os outros dois têm poucas regras e não enfrentaram o problema de escala.
A alocação inverte a do M1 (onde talisman dominou) porque o objeto de estudo mudou.

**Alternativas consideradas:** (a) divisão igual — rejeitada, trataria peers sem catálogo
grande como equivalentes ao que tem 131 regras; (b) só gitleaks — rejeitada, perde a
organização de suíte em Python, que é o que de fato vamos escrever; (c) sem orçamento —
rejeitada, `cycle-discover § Stop conditions` exige condição de parada.

**Stop condition — por questão (obrigatória):** Fase A vazia após 3 variantes → questão
BLOCKED com motivo "Fase A exaurida"; seguir.

**Stop condition — por projeto (obrigatória):** orçamento esgotado → questões restantes
BLOCKED com motivo "orçamento esgotado". Todos os projetos nesse estado →
`<promise>BLUEPRINT_BLOCKED</promise>`, nunca `BLUEPRINT_COMPLETE`.

**Anti-pattern:** jamais fabricar resposta de Fase B para fechar questão exaurida
(Regra Inquebrável 3).

**Consequences:** questões BLOCKED aparecem no blueprint e viram semente da próxima
descoberta.

### D2 — Amostragem em vez de leitura exaustiva do catálogo

**Decisão:** ler integralmente `utils/{generate,patterns,validate}.go` e `main.go`; das 131
regras, ler uma **amostra dirigida** — as dos provedores que o nosso `README.md` lista, mais
duas de formato notoriamente difícil (chave privada PEM e string de conexão).

**Rationale:** ler 131 arquivos estoura o orçamento do D1 sem ganho: as regras seguem um
molde comum, e o molde está nos `utils`. O valor marginal da 40ª regra lida é quase zero;
o valor de `generate.go` é alto porque é onde o molde vive. A amostra dirigida cobre
justamente os casos em que o molde pode não servir.

**Alternativas consideradas:** (a) ler todas as 131 — estoura o orçamento; (b) ler só os
`utils` — perde os casos em que a regra foge do molde, que são os interessantes; (c)
amostra aleatória — rejeitada, amostra aleatória de um conjunto homogêneo repete o molde e
não cobre os difíceis.

**Consequences:** o blueprint descreverá o molde com alta confiança e os casos fora do
molde com a ressalva de que a amostra foi dirigida, não exaustiva.

### D3 — Peers em Go entram como contrato, nunca como código

**Decisão:** extrair de `gitleaks` e `talisman` o **formato dos padrões e a disciplina de
validação**, nunca idioma de implementação Go.

**Rationale:** o que viaja entre linguagens é a expressão regular em si (que é padrão
POSIX/PCRE, não Go) e a disciplina de validar cada regra contra seus próprios exemplos. A
implementação do gerador é Go idiomático e não deve ser transplantada
(`rules/architecture.md § 6`).

**Consequência importante deste milestone:** o Go usa **RE2**, que não tem backtracking
por construção; o `re` do Python usa backtracking. Uma regex segura no gitleaks pode ser
patológica em Python. Isso torna o Risco nº 2 **específico nosso** — copiar padrão sem
verificar é exatamente o erro a evitar.

**Consequences:** toda regex adotada precisa de verificação de tempo no nosso motor, não
basta o precedente.

## Research Questions

| # | Questão | Corner | Projeto(s) | Fase A (mapa amplo) | Fase B (leitura profunda) | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | Qual o molde de construção de regex e quais parâmetros ele expõe? | techniques | gitleaks | Ler `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go` integralmente | Leitura integral (D2) | Assinatura dos geradores + o que cada parâmetro controla, com `arquivo:linha` |
| Q2 | Como o catálogo evita regex patológica e padrão largo demais? | techniques | gitleaks | Grep por `Validate`, `fps`, `tps`, `false`, `boundary`, `\\b`, `(?i)` em `knowledge-base/references/gitleaks/cmd/generate/config/utils/validate.go` e `patterns.go` | Ler `validate.go` integralmente | Mecanismo de validação + como a delimitação é feita. **Núcleo dos dois riscos do M2** |
| Q3 | Como 131 regras são organizadas sem virar código espalhado? | techniques | gitleaks | `ls knowledge-base/references/gitleaks/cmd/generate/config/rules/` + ler `knowledge-base/references/gitleaks/cmd/generate/config/main.go` | Ler `main.go` integralmente + amostra dirigida de regras (D2) | Estrutura do catálogo + como uma regra nova entra + citação |
| Q4 | Como cada regra é validada contra seus próprios exemplos? | tests | gitleaks | Ler `knowledge-base/references/gitleaks/cmd/generate/config/utils/validate.go` | Leitura integral | Momento da validação (construção vs teste separado) + o que acontece quando falha |
| Q5 | Como o ggshield organiza suíte com muitos casos parametrizados? | tests | ggshield | `ls knowledge-base/references/ggshield/tests/unit/` + Grep por `parametrize` | Ler 2-3 arquivos com mais parametrize | Padrão de organização + como os casos ficam legíveis em volume |
| Q6 | O catálogo adiciona dependência de runtime? | deps | gitleaks, talisman | SKIP Fase A — forma textual. Ler os imports de `knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go` e de `knowledge-base/references/talisman/detector/` | Classificar cada import | Lista + veredito: dá para fazer só com `re` da stdlib? |
| Q7 | Como o catálogo é gerado, versionado e revisado? | tools | gitleaks | Ler `knowledge-base/references/gitleaks/cmd/generate/config/main.go`; comparar com `knowledge-base/references/gitleaks/config/gitleaks.toml` | Leitura integral do `main.go` | Fluxo: fonte da verdade → artefato gerado → como o diff de uma regra nova aparece na revisão |

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
| Antes de responder Qx | Todo path da Fase A existe em disco | BLOCKED com motivo "path não encontrado" |
| Orçamento de Fase A | ≥ 1 hotspot OU 3 variantes tentadas | BLOCKED com motivo "Fase A exaurida" |
| Depois de responder Qx | Seção de Qx tem ≥ 1 citação `arquivo:linha` | Reiterar Qx (1 tentativa) |
| Q2 é irrenunciável | Q2 responde **como a delimitação é construída**, com o operador literal | Reiterar; é o núcleo do Risco nº 1 |
| Ressalva de motor de regex (D3) | Toda recomendação de padrão declara que RE2 ≠ `re` do Python quanto a backtracking | Reescrever a frase |
| Amostragem declarada (D2) | Conclusões sobre "as regras" dizem que a amostra foi dirigida, não exaustiva | Reescrever a frase |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação |
| Antes de prometer completo | Os 4 corners com seção preenchida | Recusar a promessa; continuar |

## Acceptance Criteria

- [ ] Todas as 7 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação aponta para path real em `knowledge-base/references/`
- [ ] Q2 responde com o mecanismo **literal** de delimitação, transcrito da fonte
- [ ] Toda recomendação de padrão declara a diferença RE2 × `re` (D3)
- [ ] Conclusões sobre o conjunto de regras declaram que a amostra foi dirigida (D2)
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M2
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m2-catalogo-de-padroes-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam princípio de projeto — D2 cita `rules/parsimony-ladder.md`, D3 cita
      `rules/architecture.md § 6`, D1 cita a Regra Inquebrável 3
