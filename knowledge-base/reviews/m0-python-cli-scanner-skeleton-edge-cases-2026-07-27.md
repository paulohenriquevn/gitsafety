# Discover Edge Case Review — m0-python-cli-scanner-skeleton

Date: 2026-07-27
Discovery plan analyzed: `knowledge-base/discoveries/plans/m0-python-cli-scanner-skeleton-plan.md` (v1.0)
Research questions analyzed: 8
Edge cases found: 9 (MUST FIX: 3, SHOULD TEST: 3, DOCUMENT: 3)

> Cada item abaixo foi verificado contra os clones em disco antes de ser
> classificado. Risco especulado que a verificação derrubou está registrado em
> § Verificados e descartados — não inflar o relatório é parte do trabalho.

## MUST FIX

### EC-1: Q5 aponta para o diretório errado — os testes por regra do gitleaks não estão em `detect/`

- **Questão afetada:** Q5
- **Família:** Reference path / Scope
- **Cenário:** a Fase A de Q5 busca `func Test` em `knowledge-base/references/gitleaks/detect/`. A estrutura real de teste por regra de detecção vive em `knowledge-base/references/gitleaks/cmd/generate/config/rules/` — um arquivo por regra (`1password.go`, `adafruit.go`, `adobe.go`, `age.go`, `airtable.go`, …), que é exatamente o padrão que Q5 quer descrever. Pior: o plano declara `gitleaks/config/` como **fora de escopo**, e um leitor razoável estende essa exclusão a qualquer coisa com `config` no caminho.
- **Impacto:** Q5 encontraria testes de integração do detector (úteis, mas outra coisa) e concluiria que o gitleaks não tem estrutura de teste por regra — conclusão errada que contaminaria a decisão de layout de teste do M2.
- **Correção sugerida:** adicionar `cmd/generate/config/rules/` ao in-scope de gitleaks e à Fase A de Q5, com nota explícita de que a exclusão de `gitleaks/config/` não alcança esse caminho.

### EC-2: o comando de scan do ggshield está bloqueado pelo mesmo deny-glob do D3

- **Questões afetadas:** Q2, Q3
- **Família:** Reference path
- **Cenário:** o D3 registra três *peers* inacessíveis, mas trata `ggshield/ggshield/cmd/secret/` como uma exclusão menor de escopo. Ele não é menor: `cmd/secret/` é onde mora o comando de scan do ggshield — a orquestração que decide o que varrer e qual código de saída devolver. Q2 (heurística de descarte) e Q3 (contrato de exit code) estão escritas como se esse caminho estivesse disponível.
- **Impacto:** a Fase A de Q2/Q3 retorna só o que está em `core/`, e a resposta descreve as primitivas sem a política que as usa. O blueprint afirmaria o contrato do ggshield tendo lido metade dele.
- **Correção sugerida:** restringir Q2 e Q3 explicitamente a `ggshield/ggshield/core/` e promover a inacessibilidade de `cmd/secret/` de linha de out-of-scope para consequência declarada no D3, marcando as conclusões de Q2/Q3 sobre ggshield como confiança reduzida.

### EC-3: a Fase A de Q2 procura por um byte NUL literal

- **Questão afetada:** Q2
- **Família:** Method
- **Cenário:** a Fase A lista `\x00` entre os termos de Grep. Buscar o byte NUL literal em árvore de código-fonte é não determinístico — o que existe no fonte é a *grafia* do NUL na linguagem, não o byte.
- **Impacto:** zero matches, três variantes gastas, e Q2 marcada BLOCKED por "Fase A exaurida" quando a heurística existe e está a uma consulta de distância.
- **Correção sugerida:** trocar o termo por suas grafias em código — `\x00`, `\0`, `b"\0"`, `NUL`, `null byte` — mantendo os demais termos.

## SHOULD TEST

### EC-4: o contrato de exit code do talisman pode não estar em `cmd/`

- **Questão afetada:** Q3
- **Checkpoint sugerido no halt-loop:** se a Fase A de Q3 não encontrar `os.Exit` em `talisman/cmd/`, ampliar uma vez para a raiz de `talisman/` antes de marcar BLOCKED. O talisman recebe o menor orçamento do D1 (0.5h) e é o peer mais fácil de abandonar cedo por engano.

### EC-5: Q7 depende de Q3 e o plano não declara ordem

- **Questão afetada:** Q7 (depende de Q3)
- **Checkpoint sugerido no halt-loop:** responder Q3 antes de Q7. Q7 pergunta como o ggshield reporta config malformada; o caminho de erro quase certamente passa por `core/errors.py`, que é alvo de Q3. Responder Q7 primeiro duplica a leitura e arrisca duas descrições divergentes do mesmo módulo no blueprint.

### EC-6: a forma de resposta de Q2 não acomoda "delegado a uma dependência"

- **Questão afetada:** Q2
- **Checkpoint sugerido no halt-loop:** aceitar como resposta válida de Q2 a forma "delegado à dependência X" quando for o caso, em vez de forçar a tabela `sinal → limiar`. Detecção de binário é candidata natural a biblioteca de terceiros, e essa resposta é tão acionável quanto um limiar — inclusive resolve o degrau 2-4 da `rules/parsimony-ladder.md` diretamente.

## DOCUMENT

### EC-7: o ggshield usa `uv`, nós usaremos pip/pipx

- **Risco aceito:** `knowledge-base/references/ggshield/uv.lock` mostra que o ferramental de dependências do ggshield é `uv`. O `docs/PRD.md § NFR-1` trava instalação via `pipx`/`pip`. As respostas de Q8 (ferramental) e parte de Q6 (deps) precisam de tradução consciente, não adoção direta. Registrar no blueprint em vez de reescrever a questão — a estrutura de alvos do Makefile continua transferível mesmo com gerenciador diferente.

### EC-8: os clones não permitem arqueologia de git

- **Risco aceito:** `--depth 1 --filter=blob:none` significa um único commit e sem histórico. Nenhuma das 8 questões depende de `git log`, então o custo é zero hoje. Documentado para que uma descoberta futura que precise de "por que essa decisão mudou" saiba que precisa reclonar com profundidade.

### EC-9: a maior parte das dependências do ggshield serve a um backend remoto

- **Risco aceito:** o ggshield é cliente de um serviço comercial; boa parte das deps de runtime existe para falar com a API do GitGuardian, que é não-objetivo declarado (`docs/PRD.md § 5 NG2`). A coluna "o gitsafety precisa?" de Q6 tenderá a "não" com pouca informação nova. A questão continua valendo pelo que resta — o piso de versão, o parser de config e o que eles evitaram trazer.

## Verificados e descartados

Riscos que eu teria reportado por especulação e que a verificação derrubou. Registrados
para que não voltem na próxima revisão:

| Risco especulado | Verificação | Resultado |
|---|---|---|
| O piso de Python do ggshield é mais alto que o nosso, tornando o idioma de empacotamento inaplicável a 3.9 | `grep requires-python knowledge-base/references/ggshield/pyproject.toml` | **Descartado** — `requires-python = ">=3.9"`, idêntico ao nosso alvo |
| Q1 pode não achar a declaração de entry point | `grep '[project.scripts]' .../pyproject.toml:67-68` | **Descartado** — `ggshield = "ggshield.__main__:main"` está declarado e legível |

## Summary

| Questão | Edges | MUST FIX | SHOULD TEST | DOCUMENT |
|---|---|---|---|---|
| Q1 | 0 | 0 | 0 | 0 |
| Q2 | 3 | 2 (EC-2, EC-3) | 1 (EC-6) | 0 |
| Q3 | 2 | 1 (EC-2) | 1 (EC-4) | 0 |
| Q4 | 0 | 0 | 0 | 0 |
| Q5 | 1 | 1 (EC-1) | 0 | 0 |
| Q6 | 1 | 0 | 0 | 1 (EC-9) |
| Q7 | 1 | 0 | 1 (EC-5) | 0 |
| Q8 | 1 | 0 | 0 | 1 (EC-7) |
| (transversal) | 1 | 0 | 0 | 1 (EC-8) |

> EC-2 afeta Q2 e Q3; contado nas duas linhas, uma vez no total de 9.

**Veredito:** DISCOVERY PLAN NEEDS ADJUSTMENT — 3 MUST FIX a absorver antes de
`/discover-execute`. Nenhum deles exige nova questão nem novo projeto de referência:
dois são correção de caminho e um é troca de termo de busca.
