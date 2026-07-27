# PRD — gitsafety

> **Product Requirements Document** · Versão 2.0 · Status: **pré-1.0, em desenvolvimento**
>
> Substitui a versão 1.0, que descrevia um produto muito mais amplo (config TOML,
> regras compostas, decoding recursivo, scan de archives, quatro formatos de report,
> distribuição via Docker). O escopo foi deliberadamente reduzido — ver § 10.

---

## 1. Uma frase

Uma CLI em Python que **impede o desenvolvedor de commitar uma chave de API**,
instalada com um comando e ajustada por um único arquivo YAML.

---

## 2. Problema

Chave de API commitada é incidente caro e comum. Três agravantes:

1. **É irreversível.** Uma vez no histórico, a chave está exposta para sempre, mesmo
   apagada no commit seguinte. Bots varrem GitHub público em minutos.
2. **A detecção chega tarde.** Sem verificação no momento do commit, a descoberta
   acontece no code review, no scan trimestral de segurança, ou na fatura.
3. **As ferramentas existentes são pesadas para quem não é de segurança.** Config em
   TOML com herança e condições booleanas, dezenas de flags, distribuição via Docker.
   Um cientista de dados não passa da seção de configuração — e o que não é adotado
   não protege ninguém.

Há ainda um vetor específico e mal coberto: **notebooks Jupyter**. A chave costuma
sobreviver não no código da célula, mas na **saída salva** de uma execução antiga que
ninguém lembra que está lá.

---

## 3. Público-alvo

| Persona | Uso principal | O que ela tolera |
|---|---|---|
| Desenvolvedor individual | Hook de pre-commit | Um comando de instalação. Não vai ler manual. |
| Cientista de dados | Hook + scan de notebook | Já tem Python. Não tem Docker nem Go. |
| Time de engenharia | Mesmo hook + verificação no CI | Um YAML versionado no repositório |

**Não é público-alvo:** time de AppSec fazendo auditoria forense de histórico longo
com baseline e SARIF. Para esse caso, gitleaks e trufflehog são as ferramentas certas
e a recomendação é explícita no README.

---

## 4. Princípio de produto

**Simples, mas eficiente.** As duas metades têm o mesmo peso:

- **Simples** — um comando de instalação, quatro flags, três chaves de configuração.
  Complexidade só entra se pagar por si em detecção real.
- **Eficiente** — pega o vazamento de verdade e não atrapalha. No commit, verifica
  só o que está em stage; pula binários e arquivos acima de 1 MB.

O empate entre as duas é resolvido a favor da **confiança**: uma ferramenta que
grita falso positivo é desligada na segunda semana, e uma ferramenta desligada tem
taxa de detecção zero. Por isso a detecção é por **padrão conhecido de credencial**,
não por heurística de entropia.

---

## 5. Objetivos e não-objetivos

### Objetivos

- **G1.** Bloquear o commit que contém segredo, com instalação de um comando.
- **G2.** Manter falso positivo perto de zero por padrão — sem heurística de entropia.
- **G3.** Cobrir notebooks Jupyter, incluindo saídas de célula salvas.
- **G4.** Permitir ajuste por um YAML de três chaves, sem manual.
- **G5.** Encontrar segredo já commitado no passado (`--history`).

### Não-objetivos

- **NG1.** Não remove nem reescreve segredo do histórico (`git filter-repo` / BFG).
- **NG2.** Não é cofre de senhas nem rotaciona credenciais.
- **NG3.** Não escaneia archives (`.zip`, `.tar.gz`) nem decodifica base64/hex.
- **NG4.** Não usa entropia de Shannon, herança de config, regra composta ou
  `condition: AND/OR`.
- **NG5.** Não emite CSV, JUnit, SARIF nem template customizado.
- **NG6.** Não tem imagem Docker nem roda como serviço.

---

## 6. Requisitos funcionais

### 6.1 Comandos

| ID | Requisito |
|---|---|
| **FR-1** | `gitsafety install` — escreve `.git/hooks/pre-commit` chamando `gitsafety scan --staged`. Sem dependência do framework `pre-commit`. |
| **FR-2** | `gitsafety install` **recusa** se já existir um `pre-commit`, e exibe a linha a adicionar no hook existente. Nunca sobrescreve. |
| **FR-3** | `gitsafety scan [CAMINHO]` — verifica arquivos em disco; padrão é o diretório atual. |
| **FR-4** | `gitsafety scan --staged` — apenas arquivos em stage. |
| **FR-5** | `gitsafety scan --history` — percorre o histórico do git. |
| **FR-6** | `gitsafety --version`. |

Bypass de emergência é o nativo do git (`git commit --no-verify`) — sem mecanismo
próprio.

### 6.2 Detecção

| ID | Requisito |
|---|---|
| **FR-7** | Catálogo embutido de padrões de credencial de provedores conhecidos, cobrindo no mínimo: cloud (AWS, GCP, Azure), git/pacotes (GitHub, GitLab, npm, PyPI), IA (OpenAI, Anthropic, Hugging Face), SaaS (Stripe, Twilio, SendGrid, Slack), chaves privadas PEM e strings de conexão de banco com senha. **Alvo v1: ≥ 40 padrões.** |
| **FR-8** | Padrões custom em `rules:` no YAML — `id` + `pattern` (regex). |
| **FR-9** | `.ipynb` é lido como JSON: verifica o código das células **e as saídas salvas**. |
| **FR-10** | Arquivos binários e acima de 1 MB são pulados. |
| **FR-11** | Nenhuma verificação de entropia. Padrão casou = finding. |

### 6.3 Redução de ruído

| ID | Requisito |
|---|---|
| **FR-12** | `ignore:` — lista de globs de caminho que não são abertos. |
| **FR-13** | `allow:` — lista de valores conhecidos (texto exato ou regex) que não geram finding. |
| **FR-14** | Comentário `# gitsafety: allow` na linha suprime o finding daquela linha. |

### 6.4 Saída

| ID | Requisito |
|---|---|
| **FR-15** | Saída legível por humano: `arquivo:linha`, `id da regra`, segredo **mascarado**. |
| **FR-16** | `--show-secrets` exibe o valor completo. Mascarar é o padrão. |
| **FR-17** | No modo `--history`, o finding traz também commit, autor e data. |
| **FR-18** | Exit code: `0` limpo, `1` segredo encontrado, `2` erro de execução. |
| **FR-19** | A saída sempre instrui a **revogar a chave** — não apenas a remover a linha. |

### 6.5 Configuração

| ID | Requisito |
|---|---|
| **FR-20** | `.gitsafety.yml` na raiz do repositório; três chaves de topo: `ignore`, `allow`, `rules`. Todas opcionais. |
| **FR-21** | `--config PATH` aponta outro arquivo. |
| **FR-22** | Sem arquivo de config, os padrões embutidos valem — a ferramenta é útil com zero configuração. |
| **FR-23** | YAML malformado ou regex que não compila **abortam com erro apontando a linha** e exit code 2. Nunca degradam em silêncio. |

---

## 7. Requisitos não-funcionais

| ID | Requisito |
|---|---|
| **NFR-1** | **Instalação:** `pipx install gitsafety`. Python 3.9+. Dependência externa: apenas o parser de YAML. |
| **NFR-2** | **Latência no commit:** verificação dos arquivos em stage não deve ser perceptível no fluxo normal (alvo: < 1 s para um commit típico). |
| **NFR-3** | **Superfície de CLI:** no máximo 4 flags no `scan`. Ampliar exige justificativa explícita. |
| **NFR-4** | **A saída não vaza.** Segredo mascarado por padrão em toda saída e em qualquer log. |
| **NFR-5** | **Falha explícita.** Config inválida, caminho inexistente ou diretório que não é repositório git param com mensagem específica — nunca com "erro inesperado" nem com scan parcial silencioso. |
| **NFR-6** | **Portabilidade:** Linux, macOS e Windows, sem dependência de binário externo além do `git` (necessário só para `--staged` e `--history`). |

---

## 8. Métricas de sucesso

| Métrica | Alvo |
|---|---|
| Tempo até o primeiro uso | Instalação + hook ativo em menos de 2 minutos, sem ler manual |
| Falso positivo | Zero findings num repositório limpo de referência, sem configuração |
| Retenção | Hook continua instalado 30 dias depois — a métrica que revela se a ferramenta é tolerável |
| Cobertura de notebook | Segredo em saída de célula salva é detectado |

---

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Detecção por padrão conhecido não pega segredo custom ou senha solta | `rules:` no YAML; o README traz um padrão pronto de senha hardcoded para colar |
| Falso positivo mina a confiança e o hook é desinstalado | Sem entropia; três níveis de supressão (linha, valor, caminho) |
| Usuário remove a linha e acha que resolveu | A saída instrui a revogar a chave primeiro (FR-19) |
| `--no-verify` vira hábito e o hook deixa de proteger | Aceito: o bypass é do git e não deve ser combatido; a verificação no CI é a rede de segurança |
| Escopo voltar a crescer para o do PRD v1.0 | § 5 lista os não-objetivos nominalmente; NFR-3 limita a superfície de CLI |

---

## 10. Escopo cortado em relação ao PRD v1.0

Registrado para que a decisão não seja re-litigada a cada release:

| Recurso do v1.0 | Motivo do corte |
|---|---|
| Config TOML com `[extend]`, `useDefault`, `disabledRules` | Herança de config é o principal gerador de confusão. YAML plano de três chaves. |
| `[[rules.allowlists]]` com `condition AND/OR`, `regexTarget`, `stopwords` | Lógica booleana em config. Substituído por `ignore` + `allow`. |
| Composite rules (`withinLines`, `withinColumns`) | Complexidade de motor sem demanda do público-alvo. |
| Entropia de Shannon | Fonte principal de falso positivo. Padrão conhecido basta e é confiável. |
| `--max-decode-depth` (base64, hex, percent) | Caso de auditoria forense, não de pre-commit. |
| `--max-archive-depth` (zip, tarballs) | Idem. |
| Reports CSV, JUnit, SARIF, template Go + sprig | Público não consome. Exit code cobre CI. |
| Baseline (`--baseline-path`) | Assume repositório legado com centenas de findings — não é o cenário de entrada. |
| Distribuição via Docker (Docker Hub + ghcr.io) | Exigência explícita: sem Docker. |
| ~25 flags de CLI | Reduzido a 4. |
| Posicionamento "feature complete / sucessor Betterleaks" | Herdado da documentação de outro projeto; não descreve este produto. |

---

## 11. Proveniência

Implementação própria, sob licença MIT. A abordagem — hook de pre-commit com
catálogo de padrões conhecidos — é prática consagrada da área;
[gitleaks](https://github.com/gitleaks/gitleaks) é a referência mais completa e é
citada no README como recomendação para os casos fora deste escopo. Nenhum código
foi copiado.
