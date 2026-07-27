# Discovery Plan: Notebooks Jupyter (M4)

> **Version 1.0** — Investiga o formato `.ipynb` e o que a varredura atual, que trata o
> arquivo como texto, deixa escapar. **Nenhum peer parseia notebook** — a única menção a
> `.ipynb` no gitleaks é formatação de link. A investigação é, portanto, majoritariamente
> sobre o **formato** e sobre a **medição da lacuna atual**, não sobre copiar precedente.

**Slug:** `m4-notebooks`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 2h (quebra em D1)

## Context

O `ROADMAP.md § M4` chama notebooks de "caso de primeira classe" e o `docs/PRD.md § 2`
identifica a saída salva de célula como **o vetor específico e mal coberto** que motiva o
público de cientistas de dados: a chave sobrevive não no código, mas no `print` de uma
execução que ninguém lembra.

Os dois riscos declarados:

- **Risco M4 nº 1** — "`nbformat` v3 e v4 têm formatos de `outputs` diferentes; tratar só
  o v4 gera falso negativo silencioso em notebook antigo".
- **Risco M4 nº 2** — "notebook com saída grande estourar o limite de 1 MB e ser pulado
  **em silêncio**".

**Medição da linha de base, feita antes deste plano:** um notebook com 3 segredos
plantados — um partido entre elementos de `source`, um bloco PEM numa saída `stream`, e
uma chave numa saída `execute_result` — produziu **2 achados**. A varredura como texto
funciona para o caso comum e falha no valor partido; e as linhas reportadas são do JSON,
não da célula.

## Objective

O blueprint deve permitir decidir: qual a estrutura mínima do `.ipynb` a percorrer, como
localizar um achado de forma útil ao usuário, quais formatos de saída existem, e o que
fazer com notebook malformado ou grande demais.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões respondidas com citação a `knowledge-base/references/` ou a
      evidência de execução reproduzível
- [ ] Tabela comparativa preenchida
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope

| Fonte | Em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/gitleaks/detect/utils.go` | Tratamento de `.ipynb` | Única menção a notebook em qualquer peer legível — precisa ser lida para confirmar que **não** é parsing |
| `knowledge-base/references/gitleaks/config/gitleaks.toml` | Menções a `ipynb` | Verificar se há regra ou exclusão específica |
| **Notebooks sintéticos** gerados localmente | Estrutura real do formato | Sem peer que parseie, a fonte primária é o **formato** e a medição do comportamento atual |
| `src/gitsafety/` | Comportamento atual | A lacuna é medida contra o código que já existe |

### Out-of-Scope (explícito)

| Item | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | Inacessíveis pelo deny-glob — limitação herdada desde o M0 |
| Biblioteca `nbformat` do PyPI | Seria a **segunda** dependência de runtime; o `docs/PRD.md § NFR-1` autoriza uma, gasta no M3 |
| Notebooks de outros ambientes (Zeppelin, Observable) | Fora do que o `README.md` promete |
| Renderização de notebook | Não somos visualizador |
| Qualquer projeto não clonado em `knowledge-base/references/` | Nunca afirmar comportamento sem ler a fonte |

## ADRs

### D1 — Orçamento e condições de parada

**Decisão:** peers 0.5h (há pouco a ler), formato e medição 1.5h. Total 2h.

**Rationale:** a alocação inverte a dos milestones anteriores porque a fonte primária
mudou: sem precedente a copiar, o tempo vai para caracterizar o formato e **medir** o que
a implementação atual perde. Medir a lacuna é o que transforma "notebooks são importantes"
em requisito verificável.

**Alternativas consideradas:** (a) manter a divisão dos milestones anteriores — gastaria
1,5h lendo peers que não parseiam notebook; (b) pular os peers — perderia a confirmação de
que a menção do gitleaks é só link, que é justamente o que sustenta o D2; (c) sem orçamento
— `cycle-discover § Stop conditions` exige.

**Stop condition — por questão:** Fase A vazia após 3 variantes → BLOCKED com motivo.

**Stop condition — por projeto:** orçamento esgotado → restantes BLOCKED. Todos nesse
estado → `<promise>BLUEPRINT_BLOCKED</promise>`.

**Anti-pattern:** jamais fabricar resposta de Fase B (Regra Inquebrável 3).

**Consequences:** o blueprint terá mais evidência de execução própria que citação de peer,
e precisa dizer isso.

### D2 — Ausência de precedente é resultado; a fonte primária vira o formato e a medição

**Decisão:** quando nenhum peer resolve o problema, a evidência aceita passa a ser
**execução reproduzível** — notebooks sintéticos com comando e saída registrados — no
mesmo nível de rigor de uma citação `arquivo:linha`.

**Rationale:** é a segunda vez no projeto que a descoberta encontra ausência de precedente
(a primeira foi o M3, sobre ReDoS). Marcar as questões BLOCKED seria falso: elas têm
resposta. O que muda é a **fonte** da evidência, e trocar citação por execução exige a
mesma disciplina — comando exato, saída transcrita, reprodutível.

**Alternativas consideradas:** (a) marcar BLOCKED — falso, há resposta; (b) aceitar
afirmação sobre o formato sem execução — é exatamente o "deep-research theatre" que o
`discover-blueprint-golden-rule.md § 4` nomeia; (c) adotar `nbformat` do PyPI para ter uma
"fonte autoritativa" — gastaria a segunda dependência, vedada pelo `NFR-1`.

**Consequences:** o blueprint cita comandos e saídas próprios. Toda afirmação sobre o
formato precisa vir de um notebook que foi de fato gerado e varrido.

### D3 — Sem segunda dependência: o formato é JSON, e `json` é stdlib

**Decisão:** o parsing usa `json` da biblioteca padrão. `nbformat` não entra.

**Rationale:** `.ipynb` **é** um documento JSON, e a estrutura que precisamos —
`cells[].source`, `cells[].outputs[]` — é acessível com dicionários. `nbformat` traz
validação de esquema e migração entre versões, que não precisamos: nossa tolerância a
notebook estranho é "varra o que der para varrer", não "valide o documento".
`rules/parsimony-ladder.md` rung 2: se a stdlib resolve, use a stdlib. E o `NFR-1` já está
esgotado.

**Alternativas consideradas:** (a) `nbformat` — segunda dependência vedada, e traz validação
que não queremos: um notebook que o `nbformat` rejeita ainda pode ter segredo que devemos
achar; (b) continuar tratando como texto — a medição mostrou que perde valor partido e
reporta linha inútil.

**Consequences:** precisamos tolerar variações de formato por conta própria, incluindo
`nbformat` v3 vs v4 (Risco nº 1). O blueprint precisa caracterizar essas variações.

## Research Questions

| # | Questão | Corner | Fonte | Fase A | Fase B | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | O que exatamente o gitleaks faz com `.ipynb`? | techniques | gitleaks | Grep por `ipynb` em `knowledge-base/references/gitleaks/detect/utils.go` e `knowledge-base/references/gitleaks/config/gitleaks.toml` | Ler os hotspots | Confirmação (ou refutação) de que é só formatação de link, com `arquivo:linha` |
| Q2 | Qual a estrutura mínima de um `.ipynb` que precisamos percorrer? | techniques | notebook sintético | Gerar notebook com célula de código, de markdown e saídas; inspecionar as chaves | Percorrer a estrutura e registrar os caminhos | Mapa das chaves: `cells[].cell_type`, `.source`, `.outputs[]`, com exemplo |
| Q3 | Quais formatos de saída existem, e onde o texto mora em cada um? | techniques | notebook sintético | Gerar saídas `stream`, `execute_result`, `display_data` e `error`; inspecionar | Registrar o caminho do texto em cada tipo | Tabela: `output_type` → onde está o texto. **Cobre o Risco nº 1** |
| Q4 | O que a varredura atual perde, medido? | tests | gitsafety atual | Gerar notebook com N segredos em posições distintas; rodar `gitsafety scan`; contar | Comparar plantados × encontrados | Número exato de falsos negativos + qual posição os causa |
| Q5 | Notebook grande é pulado em silêncio? | tools | gitsafety atual | Gerar notebook acima de 1 MB; rodar `scan` | Observar `skipped` na saída | Confirmação de que aparece no resumo (Risco nº 2) |
| Q6 | O parsing acrescenta dependência? | deps | stdlib | SKIP Fase A — `json` é stdlib | Confirmar que `cells`/`outputs` são alcançáveis com dicionários | Veredito: stdlib basta? |

**Orçamento de questões:** 6 (faixa 5-10 ✓), máximo 3 por corner ✓, mínimo 1 por corner ✓.

## Coverage Matrix

| Corner | Questões mapeadas | Status |
|---|---|---|
| Integration tests | Q4 | Coberto |
| Dependencies | Q6 | Coberto |
| Tools | Q5 | Coberto |
| Techniques | Q1, Q2, Q3 | Coberto |

**Cobertura: 4/4 corners cobertos (100%)**

## Halt-loop Checkpoints

| Checkpoint | Asserção | Ação em caso de falha |
|---|---|---|
| Antes de responder Qx | Todo path da Fase A existe em disco | BLOCKED com motivo "path não encontrado" |
| Evidência de execução (D2) | Toda afirmação sobre o formato tem comando e saída transcritos | Reescrever com a execução; afirmação sem execução é teatro |
| Q4 é irrenunciável | Q4 responde com **números** — plantados × encontrados | Reiterar; sem número não há requisito verificável |
| Q1 antes de Q2 | A confirmação sobre o gitleaks precede as decisões de formato | Reordenar; se ele parseia, o plano muda |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação |
| Antes de prometer completo | Os 4 corners com seção preenchida | Recusar a promessa; continuar |

## Acceptance Criteria

- [ ] Todas as 6 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação a peer aponta para path real
- [ ] Toda afirmação sobre o formato vem de execução reproduzível (D2)
- [ ] Q4 responde com números, não com adjetivos
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M4
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m4-notebooks-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam princípio de projeto — D3 cita `rules/parsimony-ladder.md`, D2 cita
      `discover-blueprint-golden-rule.md § 4`, D1 cita a Regra Inquebrável 3
