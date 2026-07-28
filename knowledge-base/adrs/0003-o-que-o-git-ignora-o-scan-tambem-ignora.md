# ADR 0003 — O que o git ignora, o `scan` também ignora

**Data:** 2026-07-28
**Status:** aceito
**Contexto:** issue #8 — descoberto ao instalar a ferramenta num monorepo real

## Decisão

Dentro de um repositório git, `gitsafety scan` varre exatamente o conjunto que o git
enxerga: arquivos rastreados mais não-rastreados que o `.gitignore` não exclui. É o
**padrão**, sem flag para desligar.

Fora de repositório git, e quando o `git` não está no `PATH`, nada muda — a travessia do
sistema de arquivos continua valendo.

## O problema

Medido em `theo-cli`, um repositório real de 197 arquivos:

| | |
|---|---|
| Arquivos rastreados pelo git | 197 |
| Arquivos que o walker percorria | 20.479 |
| Só em `node_modules/`, gitignorado na linha 2 | ~19.700 |

96% do trabalho ia para código de terceiros que quem roda o scan não escreveu, não
controla e não pode corrigir. Achado ali é falso positivo por definição: não existe ação
possível. E falso positivo é a métrica que decide se a ferramenta continua instalada
(`ROADMAP.md § M2`, DoD nº 3).

O custo era o sintoma menor: o scan da raiz de um monorepo com 11 `node_modules` e dois
`.terraform` não terminou em dez minutos.

## Alternativas consideradas

**Interpretar o `.gitignore` no nosso código.** Recusada. A sintaxe tem precedência de
negação, `**`, âncora por barra, `.git/info/exclude` e `core.excludesFile`. Escrever um
parser para uma spec que já tem implementação canônica instalada na máquina é o
anti-pattern literal da Regra 9.

**Adicionar uma dependência (`pathspec`, `gitignore-parser`).** Recusada. O projeto
declara **uma** dependência de runtime, e cada uma é superfície de cadeia de suprimentos
numa ferramenta que roda em toda máquina do time. O git já é invocado por `--staged` e
`--history`; perguntar a ele não acrescenta nada ao inventário.

**Uma flag `--no-gitignore`.** Recusada por ora. O teto de quatro flags é declarado
(`docs/API.md § Superfície da CLI`), e a flag não tem caso de uso concreto: quem quer
varrer o que o git ignora aponta o caminho direto (`gitsafety scan node_modules/`), que
funciona porque alvo explícito é pedido explícito.

## Como

Uma invocação:

```
git ls-files -z --cached --others --exclude-standard
```

`--cached` traz os rastreados — inclusive o que foi `git add -f` sobre caminho
ignorado, que é decisão deliberada de versionar. `--others --exclude-standard` traz os
não-rastreados que o `.gitignore` não exclui — sem isso, o arquivo que você acabou de
escrever, onde a chave recém-colada está, não seria varrido. De brinde, `.git/` some: o
git nunca lista o próprio banco de dados.

O `-z` evita o C-quoting de caminho não-ASCII que já mordeu o `staged.py` (backlog B4b).

## O que se perde

Um `.env` gitignorado com credencial de verdade deixa de aparecer no `scan` de disco.

Aceito, por dois motivos. Ele nunca seria commitado — que é o que a ferramenta existe
para impedir — e o `.gitignore` é precisamente a declaração de que aquilo não entra no
repositório. Quem quer auditar o disco inteiro aponta o caminho: `gitsafety scan .env`
funciona, porque alvo explícito vence.

## Direção do fallback

Quando não dá para perguntar ao git — diretório que não é repositório, `git` fora do
`PATH`, comando falhando — a travessia cai no sistema de arquivos, varrendo **a mais**.

A direção é deliberada e não é simétrica: varrer demais gera ruído, varrer de menos
esconde credencial. Um irrita, o outro é o fracasso do produto.

## Consequências

- `docs/API.md § Os três alvos` passa a declarar o comportamento.
- `walk()` ganha `_do_git()`, que devolve `None` — e não lista vazia — quando não deu
  para perguntar. Repositório recém-criado responde `[]` legitimamente, e confundir os
  dois faria o fallback varrer os `.git/hooks/*.sample`.
- Um repositório sem `.gitignore` não muda de comportamento em nada.

## Relacionados

- Issue #8
- Regra 9 (Não Reinvente), Regra 10 (KISS), Regra 11 (YAGNI)
- `rules/parsimony-ladder.md` — a decisão para no degrau 3 (recurso nativo da plataforma)
