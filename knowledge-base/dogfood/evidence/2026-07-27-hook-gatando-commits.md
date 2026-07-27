---
scenario: hook-no-proprio-repositorio
date: 2026-07-27
operator: paulohenriquevn
outcome: pass
summary: Hook gatou 13 commits do próprio repositório e bloqueou 2 — um vazamento de teste e uma linha do README que casava a regra nova.
---

# O hook em uso, não em teste

## O que aconteceu

Depois de instalado, o hook passou a verificar **todo** commit deste repositório. Nas horas
seguintes, 13 commits passaram por ele e **2 foram bloqueados**.

## Bloqueio 1 — vazamento deliberado

`vazamento-teste.py` com uma chave AWS de exemplo. Bloqueado, exit 1, arquivo não entrou.
Era um teste meu, e serviu para confirmar o caminho feliz do bloqueio.

## Bloqueio 2 — e este eu não esperava

Ao escrever no `README.md` o exemplo de falso positivo da regra genérica — a linha
`private_key: PKCS7PrivateKeyTypes` —, o hook **bloqueou o commit da documentação**. Ele
estava certo: a linha casa a regra.

Resolvido com o marcador que o próprio README ensina, `<!-- gitsafety: allow -->`.

**Por que isto importa mais que o bloqueio 1:** documentação que mostra o que a ferramenta
detecta é, por definição, detectável. Quem escreve um guia de segurança, um post-mortem ou
um runbook vai bater nisso — e não vai ter escrito a ferramenta para saber que o marcador
existe. É atrito legítimo, não defeito, mas é atrito que a documentação de adoção deveria
antecipar.

## O que isto prova, e o que não prova

**Prova** que o cenário-âncora está `running` pela definição do
`rules/dogfood-golden-rule.md § 2`: uso ativo em infraestrutura real, não um smoke.

**Não prova** uso sustentado. É um dia. Os soft caps do § 4 continuam disparando, o veredito
é `EVIDENCE_WITH_CAVEATS`, e o `1.0.0` segue barrado.
