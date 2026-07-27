# gitsafety — Roadmap

> Gerado por `/roadmap-init` em 2026-07-27 a partir do slug `gitsafety-v1`.
> Roadmap **macro**. A decomposição em tarefas é trabalho do `/to-plan`, por milestone.

## Visão

Uma CLI em Python que impede o desenvolvedor de commitar uma chave de API, instalada
com um comando e ajustada por um único arquivo YAML. O produto ganha não por detectar
mais que os concorrentes, mas por ser **tolerável o suficiente para continuar
instalado** — inclusive na máquina de quem não é de segurança.

## Problema

**Problema raiz:** chave de API commitada é incidente caro, comum e **irreversível** —
uma vez no histórico, está exposta para sempre, e bots varrem GitHub público em
minutos. A detecção chega tarde (code review, scan trimestral, ou a fatura), e as
ferramentas existentes são pesadas demais para quem não é de segurança: config TOML
com herança e condições booleanas, dezenas de flags, distribuição via Docker.

**Quem sente a dor hoje:** o desenvolvedor que commita por acidente e o cientista de
dados cujo notebook carrega a chave na **saída salva** de uma execução que ninguém
lembra que está lá. Ferramenta que não é adotada tem taxa de detecção zero.

## Usuários

- **Primários:** desenvolvedor individual e cientista de dados (externos, qualquer
  time, uso individual). Já têm Python; não têm Docker nem Go.
- **Secundário:** time de engenharia, usando o mesmo hook mais verificação no CI.
- **Explicitamente não-alvo:** AppSec fazendo auditoria forense de histórico longo com
  baseline e SARIF — para esse caso, gitleaks e trufflehog são as ferramentas certas.

## Escopo

### Dentro da V1 (necessário para o projeto estar vivo)

- `gitsafety install` — hook de pre-commit que bloqueia o commit com segredo.
- `gitsafety scan` com 4 flags: `--staged`, `--history`, `--config`, `--show-secrets`.
- Catálogo embutido de ≥ 40 padrões de credencial de provedores conhecidos.
- `.gitsafety.yml` com exatamente três chaves: `ignore`, `allow`, `rules`.
- Notebooks `.ipynb`: código das células **e saídas salvas**.
- Segredo mascarado por padrão em toda saída; exit codes 0 / 1 / 2.

### Explicitamente fora de escopo

- **Reescrita de histórico** — *por quê:* detectar e reescrever são problemas
  diferentes; reescrita é destrutiva e pertence a `git filter-repo` / BFG.
- **Entropia de Shannon** — *por quê:* é a fonte nº 1 de falso positivo, e falso
  positivo desinstala o hook. Padrão conhecido casou = finding.
- **Archives (`.zip`, `.tar.gz`) e decoding base64/hex** — *por quê:* caso de auditoria
  forense, não de pre-commit.
- **Herança de config, regra composta, `condition: AND/OR`** — *por quê:* lógica
  booleana em arquivo de configuração é o que faz o usuário desistir de configurar.
- **Relatórios CSV / JUnit / SARIF / template** — *por quê:* o público não consome;
  exit code cobre o CI.
- **Docker e execução como serviço** — *por quê:* exigência explícita do projeto.

> Itens desta lista estão vetados na V1. Para reconsiderar, escreva uma revisão do
> roadmap — não expanda o escopo em silêncio. Motivo item a item em `docs/PRD.md` § 10.

## Restrições

| Categoria | Restrição |
|---|---|
| Stack | Python 3.10+ (elevado de 3.9 no M0 — ADR D8: 3.9 EOL desde 2025-10-31 e impedia pytest sem CVE). Dependência externa: **apenas** o parser de YAML. |
| Legal | Implementação própria sob MIT. Peers em `knowledge-base/references/` são **study-only** — nenhum código copiado. |
| Prazo | Nenhum prazo externo. |
| Time | Um desenvolvedor. Isso é o que impõe o teto de escopo, mais que qualquer outra restrição. |
| Alvo de runtime | Linux, macOS, Windows. `git` no PATH só para `--staged` e `--history`. |
| Superfície de CLI | Máximo de 4 flags no `scan` (PRD NFR-3). Uma quinta exige justificativa escrita. |
| Orçamento | Zero. Sem infraestrutura, sem serviço pago. |

## Critérios de sucesso

**Critério de ship da V1 (mensurável):** num clone limpo do repositório,
`pip install -e .` seguido de `gitsafety install` faz `git commit` de um arquivo com
chave da AWS **falhar com exit code 1**, e `git commit --no-verify` passar — verificado
por teste de integração automatizado, não por demonstração manual. Publicação no PyPI
**não** faz parte da V1 (ver M6).

**North-star metric (pós-lançamento):** **retenção do hook** — percentual de
repositórios em que o hook continua instalado 30 dias depois. É o número que revela se
a ferramenta é tolerável; ferramenta desinstalada detecta zero.

---

## Milestones

> Cada milestone tem checkbox no cabeçalho. Vire `[ ]` → `[x]` conforme concluir.
> **Sequência escolhida: hook primeiro** — após M1 o produto já protege de verdade,
> mesmo com poucos padrões, e cada milestone seguinte aumenta cobertura sobre uma base
> que já funciona.

### M0 — [x] Esqueleto ponta a ponta

**Objetivo:** uma CLI instalável que detecta um padrão real em um arquivo e sai com o
exit code correto.

**Definition of done (tudo precisa valer):**

- [x] `pip install -e .` expõe o comando `gitsafety` no PATH.
- [x] `gitsafety scan <caminho>` percorre arquivos de texto, aplica **um** padrão real
      (AWS: `AKIA[0-9A-Z]{16}`) e imprime `arquivo:linha  regra`.
- [x] Exit code 0 sem finding, 1 com finding, 2 em erro (caminho inexistente) — cada um
      coberto por teste.
- [x] Suíte de testes roda com um comando e está verde no CI do próprio repositório.
- [x] Binários e arquivos acima de 1 MB são pulados (PRD FR-10).

**Dependências:** nenhuma (é a fundação).

**Riscos principais:**

1. O empacotamento Python (`console_scripts`, `pyproject.toml`) consumir mais tempo que
   a detecção em si — é o clássico "o difícil não era o problema".
2. A fronteira "arquivo de texto" ser mal definida: heurística de byte NUL erra em
   UTF-16, e pular um arquivo por engano é um falso negativo silencioso.

---

### M1 — [x] Hook de pre-commit — *a partir daqui já protege*

**Objetivo:** um comando instala o hook, e o commit que contém segredo é bloqueado.

**Definition of done:**

- [x] `gitsafety install` escreve `.git/hooks/pre-commit` executável chamando
      `gitsafety scan --staged`.
- [x] Hook `pre-commit` já existente → **recusa**, exit 2, e imprime a linha a adicionar
      manualmente. Nunca sobrescreve (PRD FR-2).
- [x] `gitsafety scan --staged` lê o **conteúdo em stage**, não o arquivo em disco.
- [x] Teste de integração: repositório git temporário, `git commit` com segredo é
      bloqueado; `git commit --no-verify` passa.
- [x] Fora de um repositório git → mensagem específica e exit 2 (PRD NFR-5).

**Dependências:** M0.

**Riscos principais:**

1. Ler do disco em vez de `git show :arquivo` deixa passar segredo quando o `git add -p`
   colocou só parte do arquivo em stage — falso negativo difícil de perceber.
2. Bit de execução do hook em Windows / repositórios com `core.hooksPath` customizado.

---

### M2 — [x] Catálogo de padrões e mascaramento

**Objetivo:** cobrir os provedores comuns e garantir que a saída não vire o próximo
vazamento.

**Definition of done:**

- [x] ≥ 40 padrões cobrindo as 6 categorias do README, **cada um** com teste de acerto
      e teste de não-acerto.
- [x] Segredo mascarado por padrão em toda saída; `--show-secrets` revela (PRD FR-16).
- [x] Repositório limpo de referência produz **zero findings** — é a métrica de falso
      positivo do PRD § 8, medida e registrada.
- [x] Padrões vivem em um arquivo de dados versionado, não espalhados pelo código.

**Dependências:** M0.

**Riscos principais:**

1. Um padrão largo demais gera falso positivo e derruba a confiança — o dano é maior
   que o benefício de um padrão a mais.
2. Regex com backtracking catastrófico trava o commit; exige teste com limite de tempo.

---

### M3 — [x] Configuração `.gitsafety.yml`

**Objetivo:** permitir ajuste sem manual — três chaves e nada mais.

**Definition of done:**

- [x] `ignore` (globs), `allow` (valores/regex) e `rules` (`id` + `pattern`)
      implementadas (PRD FR-12, FR-13, FR-8).
- [x] Comentário `# gitsafety: allow` suprime o finding daquela linha (PRD FR-14).
- [x] YAML malformado ou regex que não compila → exit 2 apontando arquivo e linha,
      coberto por **teste negativo** que verifica a mensagem, não só que levanta erro.
- [x] Sem arquivo de config, a ferramenta funciona com os padrões embutidos (PRD FR-22).
- [x] `--config PATH` aponta outro arquivo.

**Dependências:** M2.

**Riscos principais:**

1. O parser de YAML é a **única** dependência externa — versão fixada e superfície de
   uso mínima, para não virar porta de entrada de CVE.
2. Regex vinda da config do usuário é **entrada não confiável na fronteira do sistema**:
   precisa ser validada na carga e ter limite de tempo na execução.

---

### M4 — [x] Notebooks Jupyter

**Objetivo:** cobrir o vetor de vazamento específico do cientista de dados.

**Definition of done:**

- [ ] `.ipynb` é lido como JSON; o código das células **e as saídas salvas** são
      verificados (PRD FR-9).
- [ ] O finding aponta a célula e a linha dentro dela, não o offset bruto do JSON.
- [ ] `.ipynb` malformado → erro específico, sem stack trace.
- [ ] Teste com notebook real cujo segredo existe **apenas** na saída salva.

**Dependências:** M2.

**Riscos principais:**

1. `nbformat` v3 e v4 têm formatos de `outputs` diferentes — tratar só o v4 gera falso
   negativo silencioso em notebook antigo.
2. Notebook com saída grande estourar o limite de 1 MB e ser pulado **em silêncio** —
   o limite herdado do M0 precisa de exceção ou de aviso explícito aqui.

---

### M5 — [x] Histórico (`--history`) — *linha de chegada da V1*

**Objetivo:** encontrar a chave que já foi commitada no passado.

**Definition of done:**

- [ ] `gitsafety scan --history` percorre o histórico e reporta commit, autor e data
      (PRD FR-17).
- [ ] Reusa o **mesmo** matcher do scan de arquivos — sem segundo motor de detecção.
- [ ] Teste de integração num repositório onde o segredo foi introduzido e depois
      removido: ainda é detectado.
- [ ] Repositório sem commits → mensagem específica, sem crash.

**Dependências:** M1, M2.

**Riscos principais:**

1. Repositório grande tornar o comando lento a ponto de ninguém rodar — se acontecer, é
   sinal para documentar o custo, não para adicionar flags de tuning.
2. O mesmo segredo em vários commits poluir a saída; exige deduplicação por
   (regra, segredo, arquivo).

> **✅ V1 completa em M5.** Critério de ship: `pip install -e .` + `gitsafety install`
> + `git commit` bloqueado, verificado por teste de integração.

---

### M6 — [x] Publicação no PyPI *(pós-V1)*

**Objetivo:** tornar o `pipx install gitsafety` do README verdadeiro para terceiros.

**Definition of done:**

- [ ] Pacote publicado no PyPI; `pipx install gitsafety` funciona em máquina limpa.
- [ ] README confere com o pacote publicado — nenhuma flag documentada que não exista.
- [ ] `CHANGELOG.md` com a versão `1.0.0` e tag semver anotada.

**Dependências:** M0-M5.

**Riscos principais:**

1. ~~Nome ocupado no PyPI~~ — **verificado em 2026-07-27: `gitsafety` está LIVRE**
   (HTTP 404 em `pypi.org/pypi/gitsafety/json`). Risco rebaixado; registrar o nome cedo
   se houver receio de corrida.
2. O README prometer o que o pacote não entrega — daí o segundo item do DoD ser uma
   verificação, não uma leitura.

---

## Referências state-of-the-art

Peers clonados em `knowledge-base/references/` (raso, `--depth 1 --filter=blob:none`,
72 MB no total). Licenças verificadas via API do GitHub em 2026-07-27. Decisões de
license gate e notas de estudo em `knowledge-base/references-catalog.md` (fora do
diretório `references/`, que é read-only por `rules/audit-trail-rotation.md`).

| Peer | Licença | Por que está aqui | Milestones |
|---|---|---|---|
| **detect-secrets** (Yelp) | Apache-2.0 | Peer mais próximo: Python + pre-commit + detecção por plugins | M0, M1 |
| **gitleaks** | MIT | Catálogo de padrões mais completo da área | M2 |
| **ggshield** (GitGuardian) | MIT | CLI Python madura e em manutenção ativa | M0, M3 |
| **talisman** (ThoughtWorks) | MIT | Foco exclusivo na mecânica do hook de pre-commit | M1 |
| **ripsecrets** | MIT | Filosofia declarada de falso-positivo quase zero | M2 |
| **secretlint** | MIT | Design de configuração declarativa em arquivo | M3 |

> **Study-only.** Todas são permissivas, mas o gitsafety é implementação própria:
> nenhum código é copiado. Consulte para entender decisões, não para transcrever.

---

## Protocolo de revisão

- **Marcar progresso:** vire o checkbox no cabeçalho do milestone. Sem cerimônia.
- **Ajustar o DoD de um milestone:** edite no lugar e registre a data no `CHANGELOG.md`.
- **Adicionar milestone depois do M6:** o projeto extrapolou o escopo inicial — escreva
  uma revisão (`ROADMAP-v2.md`) em vez de inflar este documento.
- **Remover um milestone:** marque `~~M3 — [-] nome (cancelado AAAA-MM-DD — motivo)~~`
  em vez de apagar. O histórico importa.

## Em aberto na criação do roadmap

As 7 dimensões do grill foram todas respondidas (ver
`knowledge-base/grills/gitsafety-v1-roadmap-grill.md`). Pendências operacionais que
**não** bloqueiam o M0:

- **Titular do copyright no `LICENSE`** — está como "Paulo Henrique", derivado do
  `git config user.name`. Confirmar antes de qualquer publicação (afeta M6).
- **Branch de trabalho** — o repositório está em `main` e nada foi commitado ainda. A
  Regra Inquebrável 4 exige `develop`. Resolver antes do primeiro commit do M0.
