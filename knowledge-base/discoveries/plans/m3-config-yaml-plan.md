# Discovery Plan: Configuração em YAML e regex vinda do usuário (M3)

> **Version 1.0** — Investiga como peers carregam configuração de usuário, como reportam
> arquivo malformado, e — a questão central — **como tratam expressão regular fornecida
> pelo usuário**, que é entrada não confiável executada pelo nosso motor. Projetos em
> escopo: `ggshield` (config em YAML, mesma stack) e `gitleaks` (regex de usuário em
> config).

**Slug:** `m3-config-yaml`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 2.5h (quebra por projeto em D1)

## Context

O `ROADMAP.md § M3` acrescenta `.gitsafety.yml` com três chaves e nomeia dois riscos:

- **Risco M3 nº 1** — "o parser de YAML é a **única** dependência externa; versão fixada
  e superfície de uso mínima, para não virar porta de entrada de CVE".
- **Risco M3 nº 2** — "regex vinda da config do usuário é **entrada não confiável na
  fronteira do sistema**: precisa ser validada na carga e ter limite de tempo na execução".

O segundo risco é o que distingue este milestone. O M2 construiu garantias mecânicas —
nenhum quantificador livre, teto de tempo por regra — para **os nossos** padrões. Um
padrão vindo do `rules:` do usuário atravessa essas defesas sem passar por nenhuma. E
desde o M1 a regex roda dentro do `git commit`.

## Objective

O blueprint deve permitir decidir, antes do `/to-plan` do M3: como carregar o YAML com
superfície mínima, como reportar erro com arquivo e linha, e **o que fazer com um regex
de usuário** — rejeitar, aceitar com limite, ou aceitar sem defesa.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões respondidas com citação a `knowledge-base/references/`
- [ ] Tabela comparativa preenchida para cada projeto em escopo
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope (por projeto de referência)

| Projeto | Subdiretórios em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/ggshield/` | `ggshield/core/config/utils.py`, `ggshield/core/config/user_config.py`, `ggshield/core/config/config.py` | **Peer primário.** Config em YAML, em Python, com tratamento de arquivo malformado. |
| `knowledge-base/references/gitleaks/` | `config/config.go`, `config/rule.go`, `config/utils.go` | Único peer que aceita **regex de usuário** em config. |

### Out-of-Scope (explícito)

| Projeto / Subdir | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | Inacessíveis pelo deny-glob — limitação herdada e declarada desde o M0. |
| `ggshield/ggshield/core/config/auth_config.py`, `token_store.py` | Autenticação em serviço remoto — não-objetivo (`docs/PRD.md § 5 NG2`). |
| `gitleaks/config/gitleaks.toml` | TOML como formato — cortado no `docs/PRD.md § 10`. |
| Herança de config, `[extend]`, perfis global/local | Cortados no `docs/PRD.md § 10`; o M3 tem três chaves e um arquivo. |
| Qualquer projeto não clonado em `knowledge-base/references/` | Nunca afirmar comportamento sem ler a fonte. |

## ADRs

### D1 — Orçamento de tempo e condições de parada

**Decisão:** ggshield 1.5h, gitleaks 1h. Total 2.5h.

**Rationale:** ggshield concentra o carregamento em Python, que é o que vamos escrever.
gitleaks entra por um motivo só, mas decisivo: é o único peer que aceita regex de usuário.

**Alternativas consideradas:** (a) só ggshield — perderia a única fonte sobre regex de
usuário; (b) divisão igual — daria a gitleaks tempo que ele não precisa, já que só uma
questão o alcança; (c) sem orçamento — `cycle-discover § Stop conditions` exige.

**Stop condition — por questão (obrigatória):** Fase A vazia após 3 variantes → BLOCKED
com motivo "Fase A exaurida"; seguir.

**Stop condition — por projeto (obrigatória):** orçamento esgotado → restantes BLOCKED.
Todos nesse estado → `<promise>BLUEPRINT_BLOCKED</promise>`.

**Anti-pattern:** jamais fabricar resposta de Fase B (Regra Inquebrável 3).

**Consequences:** questões BLOCKED viram semente da próxima descoberta.

### D2 — Ausência de precedente é resultado, não lacuna

**Decisão:** se nenhum peer tratar um problema, registrar isso como **achado**, com a
explicação de por que eles não precisam — em vez de marcar a questão BLOCKED.

**Rationale:** a ausência de defesa contra ReDoS nos peers em Go não é descuido: RE2 não
faz backtracking, então o problema **não existe** para eles. Registrar "nenhum peer trata"
sem explicar por quê levaria à conclusão errada de que também podemos ignorar. O valor da
descoberta aqui é justamente identificar onde **não há o que copiar**
(`rules/architecture.md § 6` — não transplantar o que depende do contexto de origem).

**Alternativas consideradas:** (a) marcar BLOCKED — seria falso, a questão foi respondida
e a resposta é "não existe"; (b) omitir a questão — apagaria a informação mais importante
do milestone.

**Consequences:** o blueprint terá uma seção sobre um problema sem precedente, e as
decisões dali serão nossas, com o ônus de justificativa que isso carrega.

### D3 — Peers em Go entram como contrato, nunca como código

**Decisão:** de `gitleaks` extrair **comportamento observável** — o que acontece com
regex inválida, o que é validado na carga —, nunca idioma Go.

**Rationale:** `rules/architecture.md § 6`. E aqui a diferença de motor é o próprio objeto
de estudo: o que o gitleaks pode fazer em segurança (compilar regex de usuário sem
proteção) é justamente o que nós **não** podemos.

**Consequences:** citações a gitleaks descrevem comportamento; a tradução para Python é
explicitamente diferente, não análoga.

## Research Questions

| # | Questão | Corner | Projeto(s) | Fase A (mapa amplo) | Fase B (leitura profunda) | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | Como o YAML é carregado e qual a superfície de uso da dependência? | techniques | ggshield | Ler `knowledge-base/references/ggshield/ggshield/core/config/utils.py` integralmente | Leitura integral | Funções do `yaml` usadas + o que é feito com o resultado, com `arquivo:linha` |
| Q2 | Como arquivo malformado é reportado ao usuário? | techniques | ggshield | Grep por `ParserError`, `ScannerError`, `raise`, `not a valid` em `knowledge-base/references/ggshield/ggshield/core/config/utils.py` | Ler o ramo de erro inteiro | Tipos de exceção capturados + formato da mensagem + se contém linha/coluna |
| Q3 | Como a regex vinda da config do usuário é tratada — na compilação (inválida) e na execução (patológica)? | techniques | gitleaks, ggshield | Grep por `MustCompile`, `regexp.Compile`, `invalid regex` em `knowledge-base/references/gitleaks/config/`; e por `ReDoS`, `catastrophic`, `timeout`, `deadline` em ambos os projetos | Ler os hotspots de compilação; se nada houver sobre patologia, registrar a ausência **com a explicação** (D2) | As **duas metades** do Risco nº 2, com comportamento literal e citação. Se nenhum peer protege, a resposta explica por quê |
| Q4 | Como a config é validada estruturalmente antes do uso? | tests | ggshield, gitleaks | Grep por `isinstance`, `should be`, `Validate`, `func.*validate` em `knowledge-base/references/ggshield/ggshield/core/config/utils.py` e `knowledge-base/references/gitleaks/config/rule.go` | Ler os validadores | Que invariantes são checadas na carga + como o erro é comunicado |
| Q5 | Qual a versão da dependência de YAML e como é pinada? | deps | ggshield | SKIP Fase A — forma textual. Ler `knowledge-base/references/ggshield/pyproject.toml` | Leitura da linha da dependência | Especificador de versão + o que ele permite |
| Q6 | Onde a config é procurada e em que ordem? | tools | ggshield | Grep por `find_local_config_path`, `find_global_config_path`, `exists` em `knowledge-base/references/ggshield/ggshield/core/config/utils.py` | Ler as funções de descoberta | Ordem de precedência + o que acontece quando nada é encontrado |

**Orçamento de questões:** 6 (faixa 5-10 ✓), máximo 3 por corner ✓, mínimo 1 por corner ✓.

## Coverage Matrix

| Corner | Questões mapeadas | Status |
|---|---|---|
| Integration tests | Q4 | Coberto |
| Dependencies | Q5 | Coberto |
| Tools | Q6 | Coberto |
| Techniques | Q1, Q2, Q3 | Coberto |

**Cobertura: 4/4 corners cobertos (100%)**

**Orçamento revisado:** 6 questões (faixa 5-10 ✓), máximo 3 por corner ✓. A versão
inicial tinha 7, com 4 no corner *techniques* — o gate de orçamento acusou, e a correção
foi **fundir** as duas questões sobre regex de usuário, que são as duas metades do mesmo
risco (inválida na compilação × patológica na execução). Separá-las em corners diferentes
para caber no teto seria contornar o gate em vez de respeitá-lo.

## Halt-loop Checkpoints

| Checkpoint | Asserção | Ação em caso de falha |
|---|---|---|
| Antes de responder Qx | Todo path da Fase A existe em disco | BLOCKED com motivo "path não encontrado" |
| Depois de responder Qx | Seção de Qx tem ≥ 1 citação `arquivo:linha` | Reiterar Qx (1 tentativa) |
| Q3 é irrenunciável | Q3 responde com o **comportamento literal**, transcrito da fonte | Reiterar; é o núcleo do Risco nº 2 |
| Q3, segunda metade (D2) | Se nenhum peer tratar patologia, a resposta explica **por que** eles não precisam | Reescrever; "nenhum peer trata" sem o porquê leva à conclusão errada |
| Ressalva de motor | Toda conclusão sobre regex declara a diferença RE2 × `re` | Reescrever a frase |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação |
| Antes de prometer completo | Os 4 corners com seção preenchida | Recusar a promessa; continuar |

## Acceptance Criteria

- [ ] Todas as 6 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação aponta para path real em `knowledge-base/references/`
- [ ] Q3 responde com o comportamento **literal** da fonte
- [ ] Q3 explica **por que** os peers não precisam da defesa contra patologia que nós precisamos
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M3
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m3-config-yaml-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam princípio de projeto — D2 e D3 citam `rules/architecture.md § 6`,
      D1 cita a Regra Inquebrável 3
