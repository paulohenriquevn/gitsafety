---
generated_by: roadmap-init
generated_on: 2026-07-27
slug: gitsafety-v1
peer_count_cloned: 6
peer_count_skipped: 4
---

# References catalog

Projetos state-of-the-art reunidos na criação do projeto pelo `/roadmap-init`.
Este arquivo é o contrato que o `/discover-plan` lê ao investigar um peer.

> **Localização.** O template do `/roadmap-init` prevê este arquivo em
> `knowledge-base/references/_catalog.md`, mas aquele diretório é **read-only por
> política do projeto** (`rules/audit-trail-rotation.md`). O catálogo vive aqui, como
> irmão do diretório que ele descreve.

> **Lifecycle:** todo peer abaixo tem lifecycle `cloned` (pasta presente em
> `knowledge-base/references/`) ou `skipped` (rejeitado na curadoria ou no license
> gate, mantido aqui para registro).

> **Intenção declarada: study-only.** O gitsafety é implementação própria sob MIT.
> Estes clones existem para entender decisões de design, não para transcrever código.
> Todas as licenças abaixo são permissivas (MIT / Apache-2.0), o que torna a cópia
> legalmente possível — mas ela continua vedada por decisão de projeto.

---

## detect-secrets (Yelp)

- **Pasta:** `knowledge-base/references/detect-secrets/`
- **Lifecycle:** cloned — SHA `5e14193`
- **Repo:** https://github.com/Yelp/detect-secrets
- **Licença:** `Apache-2.0`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2026-04-02
- **Stars / forks na clonagem:** 4601 / 563

### Por que este peer está aqui

É o **peer mais próximo** do gitsafety: Python, distribuído por pip, integrado ao
framework `pre-commit`, detecção organizada em plugins independentes. Resolve o mesmo
problema para o mesmo público, com as mesmas restrições de stack. Onde nossas decisões
divergirem das dele, a divergência precisa ser consciente.

### O que estudar

- Estrutura do pacote Python e definição do entry point do console.
- Como cada plugin de detecção é isolado, registrado e testado.
- O mecanismo de baseline — que nós **cortamos** de propósito (PRD § 10); entender o
  que ele resolve valida se o corte se sustenta.
- Tratamento de falso positivo sem recorrer a config booleana.

### Suporta os milestones

- **M0** — *porque:* é a referência de como empacotar uma CLI Python de scan e
  organizar a suíte de testes.
- **M1** — *porque:* mostra a integração com pre-commit já madura, incluindo os casos
  de borda de instalação.

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/Yelp/detect-secrets.git knowledge-base/references/detect-secrets/
```

---

## gitleaks

- **Pasta:** `knowledge-base/references/gitleaks/`
- **Lifecycle:** cloned — SHA `b58d3f1`
- **Repo:** https://github.com/gitleaks/gitleaks
- **Licença:** `MIT`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2026-07-22
- **Stars / forks na clonagem:** 28326 / 2160

### Por que este peer está aqui

Tem o **catálogo de padrões de credencial mais completo e mais mantido** da área — é a
referência de fato para "como se escreve uma regra de detecção que não gera falso
positivo". O gitsafety cobre um escopo deliberadamente menor, mas o M2 precisa de ≥ 40
padrões corretos, e essa é a fonte para conferir cada um.

O README e o PRD do gitsafety citam o gitleaks nominalmente como a recomendação honesta
para quem precisa do que cortamos.

### O que estudar

- `cmd/generate/config/rules/` — uma regra por arquivo, cada uma com caso de teste
  positivo e negativo. É o padrão de organização que o M2 deve seguir.
- Como padrões de provedor são delimitados para não casar em texto comum.
- Quais provedores estão cobertos, para dimensionar honestamente o nosso "≥ 40".

### Suporta os milestones

- **M2** — *porque:* é a fonte de conferência do catálogo de padrões e do formato de
  teste por regra (acerto + não-acerto).

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/gitleaks/gitleaks.git knowledge-base/references/gitleaks/
```

---

## ggshield (GitGuardian)

- **Pasta:** `knowledge-base/references/ggshield/`
- **Lifecycle:** cloned — SHA `dd09cac`
- **Repo:** https://github.com/GitGuardian/ggshield
- **Licença:** `MIT`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2026-07-27 (o mais ativo da lista)
- **Stars / forks na clonagem:** 1973 / 213

### Por que este peer está aqui

CLI Python madura, mantida por uma empresa cujo produto é exatamente isto — logo, a
ergonomia dela foi lapidada por atrito real de usuário. Interessa menos o motor (que é
serviço remoto, fora do nosso escopo) e mais **como a ferramenta conversa com o
usuário**: mensagens de erro, saída de finding, fluxo de instalação de hook.

### O que estudar

- Redação das mensagens de erro e de finding — nosso PRD FR-19 exige que a saída
  instrua a **revogar** a chave, não só a remover a linha.
- Estrutura de subcomandos e como mantiveram a CLI navegável.
- Convenções de empacotamento e distribuição Python.

### Suporta os milestones

- **M0** — *porque:* referência de estrutura de CLI Python e empacotamento.
- **M3** — *porque:* mostra como expor configuração sem afogar o usuário em opções.

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/GitGuardian/ggshield.git knowledge-base/references/ggshield/
```

---

## talisman (ThoughtWorks)

- **Pasta:** `knowledge-base/references/talisman/`
- **Lifecycle:** cloned — SHA `efcb1a3`
- **Repo:** https://github.com/thoughtworks/talisman
- **Licença:** `MIT`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2026-03-01
- **Stars / forks na clonagem:** 2094 / 251

### Por que este peer está aqui

É o peer cujo **foco é exatamente o hook**, não o motor de detecção. Trata em
profundidade o problema que o nosso FR-2 levanta: instalar um hook num repositório que
já tem `pre-commit`, sem destruir o do usuário. Escrito em Go — o que não atrapalha,
porque o que interessa aqui é a mecânica do git, não o código.

### O que estudar

- Instalação por repositório vs. global (`core.hooksPath`) e como detectam qual usar.
- Comportamento quando já existe um `pre-commit` — o caso que o gitsafety resolve
  **recusando** (FR-2).
- Como leem o conteúdo em stage (relevante para o risco nº 1 do nosso M1).

### Suporta os milestones

- **M1** — *porque:* é a referência direta da mecânica de instalação e execução do hook.

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/thoughtworks/talisman.git knowledge-base/references/talisman/
```

---

## ripsecrets

- **Pasta:** `knowledge-base/references/ripsecrets/`
- **Lifecycle:** cloned — SHA `34c9e03`
- **Repo:** https://github.com/sirwart/ripsecrets
- **Licença:** `MIT`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2025-12-15 — **o menos ativo da lista** (~7 meses)
- **Stars / forks na clonagem:** 906 / 26

### Por que este peer está aqui

É o único peer que declara **falso-positivo quase zero como objetivo primário de
produto**, e não como consequência. É exatamente o princípio do § 4 do nosso PRD
("simples, mas eficiente", empate resolvido a favor da confiança). O valor aqui é a
argumentação sobre o que **não** detectar.

Menor adoção e menos atividade recente que os demais — está na lista pela filosofia,
não pela maturidade. Não use como referência de engenharia.

### O que estudar

- A justificativa declarada de quais classes de segredo ficaram de fora e por quê.
- Como decidem entre precisão e recall quando as duas conflitam.
- Se usam algum sinal além de regex e, se sim, com qual custo de falso positivo.

### Suporta os milestones

- **M2** — *porque:* o catálogo de padrões é onde o trade-off precisão × cobertura é
  efetivamente decidido, padrão a padrão.

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/sirwart/ripsecrets.git knowledge-base/references/ripsecrets/
```

---

## secretlint

- **Pasta:** `knowledge-base/references/secretlint/`
- **Lifecycle:** cloned — SHA `7da613e`
- **Repo:** https://github.com/secretlint/secretlint
- **Licença:** `MIT`
- **Decisão do license gate:** auto-approved-permissive
- **Último push:** 2026-07-26
- **Stars / forks na clonagem:** 1435 / 53

### Por que este peer está aqui

TypeScript, portanto irrelevante como referência de implementação — está aqui por **um
aspecto só**: o design da configuração declarativa em arquivo (`.secretlintrc`). O
`.gitsafety.yml` do M3 promete três chaves e nada mais; vale ver como um projeto que
levou config a sério organizou a sua, e quais dores isso trouxe.

### O que estudar

- Formato do arquivo de config e como a validação reporta erro ao usuário (nosso FR-23
  exige arquivo e linha).
- Como regras customizadas do usuário são declaradas e carregadas.
- Onde a config deles ficou complexa demais — é o anti-exemplo que protege o M3.

### Suporta os milestones

- **M3** — *porque:* é a referência de design (e de anti-design) da configuração.

### Comando de clone usado

```bash
git clone --depth 1 --filter=blob:none https://github.com/secretlint/secretlint.git knowledge-base/references/secretlint/
```

---

## Peers descartados

> Identificados na descoberta SOTA e rejeitados na curadoria ou no license gate.
> Registrados para que a decisão seja auditável e não se repita no próximo projeto.

| Peer | Repo | Licença | Motivo do descarte |
|---|---|---|---|
| trufflehog | https://github.com/trufflesecurity/trufflehog | `AGPL-3.0` | Duplo: (a) license gate — AGPL contaminaria um derivado MIT se algum código fosse copiado; (b) escopo — o diferencial dele é verificar se a chave está **viva** contra a API do provedor, que é não-objetivo declarado (PRD § 5). |
| git-secrets | https://github.com/awslabs/git-secrets | `Apache-2.0` | Shell, padrões essencialmente só de AWS, sem push desde 2025-09-17. A abordagem já está bem representada por talisman, com manutenção ativa. |
| noseyparker | https://github.com/praetorian-inc/noseyparker | `Apache-2.0` | Rust, focado em varredura forense de grande escala (múltiplos repos, datastore próprio). Outro problema, outro público. |
| kingfisher | https://github.com/mongodb/kingfisher | `Apache-2.0` | Rust, mesma categoria do noseyparker — scan em escala com validação de credencial. Fora do escopo de pre-commit. |

---

## Protocolo de limpeza

- **Remover um peer:** apague a pasta em `knowledge-base/references/` **e** remova a
  entrada deste catálogo no mesmo commit.
- **Atualizar um peer:** `git -C knowledge-base/references/{peer}/ pull` e registre o
  novo SHA neste catálogo.
- **Substituir um peer por outro melhor:** trate como remover + adicionar. Não renomeie
  pastas — continuidade simbólica não significa nada quando o repositório por trás mudou.
