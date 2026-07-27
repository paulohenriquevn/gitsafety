# Discovery Plan: Esqueleto de CLI Python para varredura de arquivos (M0)

> **Version 1.1** (2026-07-27) — absorve os 3 MUST FIX de
> `knowledge-base/reviews/m0-python-cli-scanner-skeleton-edge-cases-2026-07-27.md`:
> EC-1 (testes por regra do gitleaks estão em `cmd/generate/config/rules/`, não em
> `detect/`), EC-2 (o comando de scan do ggshield está bloqueado pelo mesmo deny-glob
> do D3 — Q2/Q3 restritas a `core/` e marcadas como confiança reduzida) e EC-3 (Fase A
> de Q2 buscava byte NUL literal; trocado pelas grafias em código). Os 3 SHOULD TEST
> viraram checkpoints do halt-loop.
>
> **Version 1.0** — Investiga como peers maduros de detecção de segredos estruturam o
> esqueleto que o M0 precisa entregar: empacotamento de CLI Python com entry point,
> travessia de arquivos com descarte de binário e limite de tamanho, contrato de exit
> codes, e organização da suíte de testes. Projetos em escopo: `ggshield` (Python — peer
> primário), `gitleaks` e `talisman` (Go — comparação de contrato, não de código). A
> saída é um blueprint que trava essas quatro decisões antes de `/to-plan` do M0, para
> que a implementação não descubra o formato certo na terceira refatoração.

**Slug:** `m0-python-cli-scanner-skeleton`
**Owner:** paulohenriquevn
**Created:** 2026-07-27
**Time budget:** 3.5h (quebra por projeto em D1)

## Context

O `ROADMAP.md § M0` exige cinco itens de DoD verificáveis: `pip install -e .` expõe o
comando, `scan` aplica um padrão real, exit codes 0/1/2 testados, suíte verde em CI, e
descarte de binários e arquivos acima de 1 MB. Dois desses itens têm armadilha
documentada como risco no próprio roadmap:

- **Risco M0 nº 1** — "o empacotamento Python consumir mais tempo que a detecção".
- **Risco M0 nº 2** — "a fronteira 'arquivo de texto' ser mal definida: heurística de
  byte NUL erra em UTF-16, e pular um arquivo por engano é um falso negativo silencioso".

Ambos são exatamente o tipo de problema que peers já resolveram e erraram antes. O
`rules/parsimony-ladder.md` § rung 2-4 obriga a olhar o que já existe antes de escrever
código próprio; esta descoberta é a execução formal desse degrau.

O `docs/PRD.md § NFR-1` trava a stack (Python 3.9+, dependência externa só o parser de
YAML) e o `§ NFR-5` exige falha explícita — decisões que o contrato de exit code do
blueprint precisa respeitar. O `rules/testing.md § 2` define a pirâmide que a
organização da suíte deve seguir.

## Objective

O blueprint deve permitir decidir, **antes de escrever a primeira linha do M0**, qual
formato de empacotamento, qual heurística de descarte de arquivo, qual contrato de exit
code e qual layout de teste adotar — cada um com precedente citado e linha de arquivo.

Critérios de sucesso mensuráveis:

- [ ] Todas as questões de pesquisa respondidas com citação a `knowledge-base/references/`
- [ ] Tabela comparativa preenchida para cada projeto em escopo
- [ ] Ao menos uma proposta de decisão concreta por questão
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS

## In-Scope / Out-of-Scope

### In-Scope (por projeto de referência)

| Projeto | Subdiretórios em escopo | Motivo |
|---|---|---|
| `knowledge-base/references/ggshield/` | `pyproject.toml`, `setup.cfg`, `Makefile`, `ggshield/__main__.py`, `ggshield/core/errors.py`, `ggshield/core/filter.py`, `ggshield/core/lines.py`, `ggshield/core/scan/`, `ggshield/core/config/`, `tests/` | **Peer primário.** Única CLI Python legível (ver D3). Mesma stack, mesmo público, empacotamento moderno. |
| `knowledge-base/references/gitleaks/` | `main.go`, `sources/`, `detect/`, `testdata/`, `Makefile`, `cmd/generate/config/rules/` | Contrato de exit code e travessia de fontes. `cmd/generate/config/rules/` é onde vive a estrutura de teste por regra — incluído por EC-1. Go — comparação de **contrato**, nunca de código. |
| `knowledge-base/references/talisman/` | `cmd/`, `scanner/`, `detector/` | Contrato de saída do hook. Escopo mínimo — o peso dele é no M1, não no M0. |

### Out-of-Scope (explícito)

| Projeto / Subdir | Por que excluído |
|---|---|
| `knowledge-base/references/detect-secrets/`, `ripsecrets/`, `secretlint/` | **Inacessíveis** — ver ADR D3. Não é escolha editorial, é bloqueio de permissão. |
| `gitleaks/report_templates/` e `gitleaks/config/` (formatos de report e config TOML) | Cortados no `docs/PRD.md § 10`. **A exclusão de `gitleaks/config/` NÃO alcança `gitleaks/cmd/generate/config/rules/`**, que está em escopo por EC-1. |
| `ggshield/ggshield/verticals/`, `ggshield/ggshield/cmd/{ai,auth,hmsl,honeytoken,machine,quota}` | Funcionalidades de produto comercial com backend remoto — não-objetivo declarado (`docs/PRD.md § 5 NG2`). |
| `ggshield/docker/`, `ggshield/Dockerfile`, `ggshield/actions*/` | Docker é não-objetivo explícito (`docs/PRD.md § 5 NG6`). |
| `ggshield/ggshield/cmd/` inteiro, incluindo `cmd/secret/` | Bloqueado pelo mesmo deny-glob do D3 — ver consequência declarada lá. Q2 e Q3 ficam restritas a `ggshield/core/`. |
| `talisman/` fora de `cmd/`, `scanner/`, `detector/` | Instalação global e prompts pertencem ao M1. |
| Qualquer projeto não clonado em `knowledge-base/references/` | Nunca afirmar comportamento de um projeto sem ler a fonte. |

## ADRs

### D1 — Orçamento de tempo e condições de parada

**Decisão:** ggshield 2h, gitleaks 1h, talisman 0.5h. Total 3.5h.

**Rationale:** ggshield é a única CLI Python legível e concentra 6 das 8 questões — é o
peer cujas decisões são diretamente transplantáveis. gitleaks entra pelo contrato de
exit code e pela organização de testes por regra (que o M2 herdará). talisman recebe o
mínimo porque seu valor está no M1 (mecânica do hook), não no esqueleto.

**Alternativas consideradas:** (a) divisão igual entre os três — rejeitada, trata peer
de linguagem diferente como equivalente ao de mesma stack; (b) só ggshield — rejeitada,
perde a triangulação do contrato de exit code, que é justamente onde um único
precedente engana; (c) sem orçamento — rejeitada, o halt-loop não teria condição de
parada e o `cycle-discover § Stop conditions` exige uma.

**Stop condition — por questão (obrigatória):** quando a Fase A de uma questão retorna
zero matches após 3 tentativas com variantes diferentes de consulta, marcar a questão
BLOCKED com motivo "Fase A exaurida" e seguir para a próxima. Não preencher com
hotspots de outra questão.

**Stop condition — por projeto (obrigatória):** orçamento esgotado com questões
pendentes → marcar as restantes daquele projeto como BLOCKED com motivo "orçamento
esgotado" e avançar. Se todos os projetos estiverem nesse estado, emitir
`<promise>BLUEPRINT_BLOCKED</promise>` — nunca `BLUEPRINT_COMPLETE`.

**Anti-pattern:** jamais fabricar resposta de Fase B para fechar questão cuja Fase A foi
exaurida. BLOCKED honesto é obrigatório (Regra Inquebrável 3).

**Consequences:** o blueprint pode sair com questões BLOCKED explícitas; elas viram
semente da próxima descoberta em vez de buraco silencioso.

### D2 — Profundidade da investigação

**Decisão:** leitura integral dos arquivos pequenos e de contrato (`pyproject.toml`,
`setup.cfg`, `Makefile`, `errors.py`, `main.go`); Grep dirigido seguido de leitura por
hotspot nos diretórios grandes (`ggshield/core/scan/`, `ggshield/tests/`,
`gitleaks/sources/`).

**Rationale:** arquivos de contrato são curtos e o valor está no conjunto — ler
parcialmente produz conclusão errada sobre um contrato. Diretórios de implementação são
grandes e o valor está em pontos específicos; ler tudo estoura o orçamento do D1 sem
ganho. Aplica `rules/parsimony-ladder.md` § rung 1 à própria pesquisa.

**Alternativas consideradas:** (a) ler tudo — estoura o orçamento; (b) só Grep — produz
citação sem entendimento de intenção, que é o modo de falha que o
`discover-blueprint-golden-rule.md § 4` chama de "deep-research theatre".

**Consequences:** as respostas de contrato terão alta confiança; as de implementação
citarão hotspots específicos e declararão o que não foi lido.

### D3 — Três dos seis peers estão inacessíveis (bloqueio de permissão)

**Decisão:** conduzir a descoberta com `ggshield`, `gitleaks` e `talisman`. Registrar
`detect-secrets`, `ripsecrets` e `secretlint` como **deferidos por bloqueio de
ferramenta**, não por decisão editorial.

**Rationale:** `.claude/settings.json` § `permissions.deny` contém `Read(**/*secret*)`,
uma proteção para não ler arquivos de credencial. O glob casa com o **nome do
diretório** dos três peers (`detect-secrets`, `ripsecrets`, `secretlint`), tornando-os
ilegíveis por `Read` e por `Bash`. Verificado empiricamente em 2026-07-27: `Read` em
`knowledge-base/references/detect-secrets/setup.cfg` retorna
*"File is in a directory that is denied by your permission settings"*.

O peer mais próximo do gitsafety é justamente `detect-secrets` (Python + pre-commit,
conforme `knowledge-base/references-catalog.md`). Sua ausência é a maior limitação desta
descoberta e precisa ser declarada no blueprint, não diluída.

**Alternativas consideradas:** (a) afrouxar o deny-glob para `Read(**/*.secret)` ou
adicionar exceção para `knowledge-base/references/**` — é a correção certa, mas alterar
a política de segurança do repositório no meio de uma descoberta é mudança de escopo com
risco de segurança; fica como recomendação ao humano. (b) Reclonar os peers com nome
alterado — burla a proteção por caminho oblíquo e deixa o catálogo mentindo sobre a
origem. (c) Prosseguir sem declarar — viola a Regra Inquebrável 3.

**Consequences:** a cobertura do corner *techniques* fica apoiada em um único peer
Python (ggshield). O blueprint DEVE marcar toda conclusão que se beneficiaria de
`detect-secrets` como confiança reduzida. Recomendação ao humano registrada no blueprint.

**Consequência adicional (EC-2, absorvida em v1.1):** o mesmo glob bloqueia
`ggshield/ggshield/cmd/secret/` — o comando de scan do próprio ggshield, onde mora a
**política** que orquestra as primitivas de `core/`. Não é exclusão menor de escopo: Q2
e Q3 passam a ler apenas as primitivas em `ggshield/core/`, sem a política que as usa.
Toda conclusão de Q2/Q3 sobre o ggshield é, portanto, **de confiança reduzida** e o
blueprint deve dizer isso na própria frase, não em nota de rodapé.

### D4 — Peers em Go entram como contrato, nunca como código

**Decisão:** de `gitleaks` e `talisman` extrair apenas **contratos observáveis** —
valores de exit code, formato de saída, organização de casos de teste. Nunca padrões de
implementação em Go.

**Rationale:** transplantar idioma de Go para Python produz código não-idiomático, o que
o `rules/architecture.md § 6` classifica como anti-pattern de abstração vazada. O que
viaja entre linguagens é o contrato; o que não viaja é a implementação.

**Consequences:** as citações a gitleaks/talisman no blueprint serão de comportamento
observável, e as recomendações derivadas delas precisam de tradução explícita para
Python.

## Research Questions

| # | Questão | Corner | Projeto(s) | Fase A (mapa amplo) | Fase B (leitura profunda) | Formato esperado |
|---|---|---|---|---|---|---|
| Q1 | Como o ggshield declara o entry point do console e qual o piso de versão do Python? | techniques | ggshield | SKIP Fase A — forma textual. Ler `knowledge-base/references/ggshield/pyproject.toml` e `setup.cfg` | Leitura integral de ambos (D2) | Bloco de configuração exato do entry point + piso de versão + citação `arquivo:linha` |
| Q2 | Qual heurística decide que um arquivo deve ser pulado (binário, tamanho, caminho) e onde ela mora? | techniques | ggshield (**só `core/`** — EC-2), gitleaks | Grep por `binary`, `is_binary`, `max_size`, `MAX_` e pelas **grafias de byte NUL em código** — `\x00`, `\0`, `b"\0"`, `NUL` (EC-3; nunca o byte literal) — em `knowledge-base/references/ggshield/ggshield/core/` e `knowledge-base/references/gitleaks/sources/` | Ler cada hotspot; capturar a heurística e o comentário que a justifica | Tabela: sinal → limiar → arquivo:linha → o que acontece com falso positivo. **Forma alternativa aceita (EC-6):** "delegado à dependência X", quando for o caso |
| Q3 | Qual o contrato de exit code de cada peer e como distinguem "achou segredo" de "erro de execução"? | techniques | ggshield (**só `core/`** — EC-2), gitleaks, talisman | Grep por `exit`, `ExitCode`, `sys.exit`, `os.Exit` em `knowledge-base/references/ggshield/ggshield/core/errors.py`, `knowledge-base/references/gitleaks/main.go`, `knowledge-base/references/talisman/cmd/`. **Fallback (EC-4):** se `talisman/cmd/` não retornar, ampliar uma vez para a raiz de `talisman/` antes de marcar BLOCKED | Ler `errors.py` integralmente (contrato, D2); nos Go, ler só os hotspots | Tabela comparativa: peer → código → significado → citação. Acomodar código de saída **configurável** (valor default + flag que o altera) |
| Q4 | Como o ggshield organiza a suíte de testes entre unitário, integração e ponta a ponta? | tests | ggshield | `ls knowledge-base/references/ggshield/tests/` + Grep por `conftest`, `fixture`, `tmp_path` | Ler os `conftest.py` e 2-3 testes representativos de cada nível | Árvore de diretórios anotada com o nível da pirâmide + convenção de nome |
| Q5 | Como o gitleaks estrutura o caso de teste de uma regra de detecção (acerto e não-acerto)? | tests | gitleaks | **Alvo primário (EC-1):** `ls knowledge-base/references/gitleaks/cmd/generate/config/rules/` — um arquivo por regra, é ali que mora o padrão procurado. Complementar: `ls knowledge-base/references/gitleaks/testdata/` + Grep por `func Test` em `knowledge-base/references/gitleaks/detect/` | Ler 2-3 arquivos de regra ponta a ponta com seus casos de acerto e não-acerto | Formato do par (fixture, asserção) + como o não-acerto é expresso + arquivo:linha |
| Q6 | Quais dependências de runtime o ggshield declara, e quais delas o gitsafety conseguiria evitar? | deps | ggshield | SKIP Fase A — forma textual. Ler `knowledge-base/references/ggshield/pyproject.toml` | Leitura integral; classificar cada dep em essencial / evitável para o nosso escopo | Tabela: dep → propósito → o gitsafety precisa? → alternativa na stdlib |
| Q7 | Que parser de configuração o ggshield usa e como reporta erro de config malformada ao usuário? | deps | ggshield | Grep por `yaml`, `safe_load`, `ValidationError` em `knowledge-base/references/ggshield/ggshield/core/config/` | Ler o carregador de config e o caminho de erro | Nome do parser + formato da mensagem de erro + citação (insumo direto do FR-23) |
| Q8 | Qual o ferramental de build/test/lint e como o comando de teste é exposto? | tools | ggshield, gitleaks | SKIP Fase A — forma textual. Ler `knowledge-base/references/ggshield/Makefile`, `knowledge-base/references/ggshield/setup.cfg`, `knowledge-base/references/gitleaks/Makefile` | Leitura integral dos três | Lista de alvos + comando de teste canônico de cada peer |

**Orçamento de questões:** 8 questões (faixa permitida 5-10 ✓), máximo 3 por corner ✓,
mínimo 1 por corner ✓.

## Coverage Matrix

| Corner | Questões mapeadas | Status |
|---|---|---|
| Integration tests | Q4, Q5 | Coberto |
| Dependencies | Q6, Q7 | Coberto |
| Tools | Q8 | Coberto |
| Techniques | Q1, Q2, Q3 | Coberto |

**Cobertura: 4/4 corners cobertos (100%)**

## Halt-loop Checkpoints

| Checkpoint | Asserção | Ação em caso de falha |
|---|---|---|
| Antes de responder Qx | Todo path declarado na Fase A de Qx existe em disco | Marcar Qx BLOCKED com motivo "path não encontrado"; seguir |
| Orçamento de Fase A por questão | Fase A retornou ≥ 1 hotspot OU 3 variantes já tentadas | Após 3 variantes vazias, BLOCKED com motivo "Fase A exaurida" |
| Depois de responder Qx | A seção de Qx no blueprint tem ≥ 1 citação `arquivo:linha` | Reiterar Qx (1 tentativa) |
| Sanidade de meio de loop | Toda afirmação sobre comportamento de peer tem citação | Adicionar citação ao parágrafo sem lastro (1 tentativa) |
| Orçamento por projeto | Orçamento do D1 não esgotado | Ao esgotar, marcar as questões restantes daquele projeto BLOCKED; avançar |
| Peer inacessível | Nenhuma afirmação sobre detect-secrets / ripsecrets / secretlint | Remover a afirmação — D3 proíbe |
| Ordem Q3 → Q7 (EC-5) | Q3 respondida antes de Q7 começar | Adiar Q7; o caminho de erro de config passa por `core/errors.py`, alvo de Q3 — responder fora de ordem duplica leitura e arrisca duas descrições divergentes do mesmo módulo |
| Fallback do talisman (EC-4) | Q3 tentou `talisman/cmd/` E, se vazio, a raiz de `talisman/` | Só marcar BLOCKED após as duas tentativas — o talisman tem o menor orçamento e é o mais fácil de abandonar cedo por engano |
| Confiança de Q2/Q3 sobre ggshield (EC-2) | Toda conclusão sobre ggshield em Q2/Q3 declara, na própria frase, que a política em `cmd/secret/` não foi lida | Reescrever a frase; nota de rodapé não satisfaz |
| Antes de prometer completo | Os 4 corners têm seção preenchida | Recusar a promessa; continuar iterando |

## Acceptance Criteria

- [ ] Todas as 8 questões respondidas OU marcadas BLOCKED com motivo
- [ ] Os 4 corners com seção preenchida no blueprint
- [ ] Toda citação aponta para um path real em `knowledge-base/references/`
- [ ] Nenhuma afirmação sobre os três peers inacessíveis (D3)
- [ ] Ao menos um ADR no blueprint sintetizando decisão para o M0
- [ ] Toda conclusão enfraquecida pela ausência do detect-secrets marcada como confiança reduzida
- [ ] Orçamento de tempo do D1 respeitado
- [ ] Veredito `/discover-confidence` ≥ SHIPPABLE_WITH_CAVEATS
- [ ] Blueprint salvo em `knowledge-base/discoveries/blueprints/m0-python-cli-scanner-skeleton-blueprint.md`

## Global Definition of Done

- [ ] Todas as fases concluídas (plan → edge-cases → plan-confidence → execute → confidence)
- [ ] Veredito final registrado no cabeçalho do blueprint
- [ ] Nenhuma citação fabricada
- [ ] Coverage Matrix 100%
- [ ] ADRs referenciam ao menos um princípio de projeto — D2 cita `rules/parsimony-ladder.md`, D4 cita `rules/architecture.md § 6`, D3 cita a Regra Inquebrável 3
