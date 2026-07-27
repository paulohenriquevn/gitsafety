---
scenario: hook-no-proprio-repositorio
date: 2026-07-27
operator: paulohenriquevn
outcome: partial
summary: Hook instalado no próprio repositório; bloqueou vazamento e deixou passar commit legítimo, mas exigiu configuração e ambiente ativo antes de funcionar.
---

# Instalação do hook no repositório do gitsafety

## O que foi feito

`gitsafety install` no próprio repositório, com `.gitsafety.yml` configurando `ignore:`.

## O que funcionou

- Commit com `CHAVE = 'AKIAIOSFODNN7EXAMPLE'` foi **bloqueado**; o arquivo não entrou.
- Commit legítimo passou sem atrito perceptível.
- `ignore:` resolveu os 72 achados de exemplo do catálogo e das fixtures.

## As três fricções — e esta é a parte útil

**1. O projeto tinha 65 commits sem verificação nenhuma.** O detector de segredos não
rodava o próprio detector. Ninguém tinha notado, o que diz algo sobre o quanto "instalar o
hook" é fácil de esquecer mesmo por quem escreveu a ferramenta.

**2. `install` falhou na primeira tentativa** com `'gitsafety' não foi encontrado no PATH`,
porque eu chamava o binário pelo caminho do venv sem o venv ativo. A mensagem estava certa
e explicava o que fazer — mas o fato de a primeira tentativa falhar num ambiente comum de
Python (venv não ativado) é atrito real de adoção, e o README não avisa disso.

**3. Sem configurar, o hook bloquearia tudo.** 72 achados entre `src/` e `tests/`, todos
exemplos legítimos. O usuário que instala num projeto com fixtures vai bater nisso no
primeiro commit. O README documenta `ignore:`, mas depois da seção de instalação — quem
segue a ordem do documento bate no muro antes de ler a saída.

**4. Com o hook instalado, todo commit falha se o venv não estiver ativo.** Aconteceu
comigo imediatamente depois de instalar: `sh: gitsafety: not found`, exit 127, commit
bloqueado. O `install` verifica o PATH **no momento da instalação** e nada verifica no
momento do commit — e o ambiente de quem commita não é necessariamente o de quem instalou.

Falhar fechado é a decisão certa para uma ferramenta de segurança. Mas a mensagem que o
usuário vê é do `sh`, não nossa, e não diz o que fazer. Um usuário que instala numa
sexta-feira e volta na segunda com o venv desativado vai achar que a ferramenta quebrou.

**5. O hook bloqueou um commit por causa da própria documentação.** Ao escrever no README
o exemplo de falso positivo da regra genérica — `private_key: PKCS7PrivateKeyTypes` — o
hook barrou o commit, corretamente: a linha casa a regra. A solução foi a que o próprio
README ensina, um `<!-- gitsafety: allow -->` na linha.

Vale registrar porque é o caso mais comum de atrito legítimo: **documentação que mostra o
que a ferramenta detecta é, por definição, detectável**. Quem escreve um guia de segurança,
um post-mortem ou um runbook vai bater nisso.

## O que isto NÃO prova

Um dia de uso não é uso sustentado. Nada aqui sustenta uma alegação de `production-ready`
ou `1.0.0` — o `Status` do manifesto segue `wired`, e é o correto.
