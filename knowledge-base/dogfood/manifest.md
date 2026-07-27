# Dogfood manifest — gitsafety

## Cenário-âncora

**Slug:** `hook-no-proprio-repositorio`

**Status:** `running`

**Descrição:** o `gitsafety` verifica todo commit do **próprio repositório do gitsafety**,
com o hook instalado e a configuração real em `.gitsafety.yml`. Nenhum commit entra sem
passar por ele.

**Por que este cenário.** Um detector de segredos é o caso extremo de falso positivo: o
catálogo e a suíte contêm valores de exemplo por natureza — 72 achados entre `src/` e
`tests/` antes de qualquer configuração. Se a ferramenta não conseguir proteger o próprio
repositório sem virar um estorvo, ela não vai conseguir proteger o de ninguém.

É desconfortável na medida certa: obriga a viver a fricção de adoção que o usuário vive no
primeiro dia — configurar `ignore:`, descobrir que o binário precisa estar no PATH, decidir
o que é exemplo e o que é vazamento.

## Por que `running`, e não `wired`

O `rules/dogfood-golden-rule.md § 2` define `wired` como *"o cenário é invocado ao menos uma
vez em CI ou num smoke manual"* e `running` como *"ativamente usado pelo time em
infraestrutura real"*.

O que existe aqui não é um smoke: o hook está gravado em `.git/hooks/pre-commit` e gata
**100% dos commits** deste repositório. **13 commits** passaram por ele, e ele **bloqueou
2** — um arquivo de vazamento de teste e uma linha do próprio README que casava a regra
genérica.

Registrei `wired` na primeira versão deste manifesto por conservadorismo, aplicando um
critério de **duração** que a regra não estabelece. A regra distingue *smoke* de *uso*, não
*um dia* de *um mês*. A duração está nos soft caps (§ 4), que é onde ela pertence — e é
exatamente por eles que o veredito não é `EVIDENCE_SUFFICIENT`.

## Estado honesto (2026-07-27)

Antes de hoje o projeto tinha **65 commits sem nenhuma verificação** — o detector de
segredos não rodava o próprio detector, e ninguém tinha notado. É precisamente o tipo de
coisa que este gate existe para expor.

**Veredito do gate: `EVIDENCE_WITH_CAVEATS`.** Os quatro hard caps passam; dois soft caps
disparam:

| Soft cap | Exigido | Temos |
|---|---|---|
| Evidências para o cenário-âncora | ≥ 3 | 2 |
| Histórias de falha | ≥ 1 | 5 fricções registradas ✓ |
| Operadores distintos | ≥ 2 | 1 |

**O `1.0.0` continua barrado**, e não por decisão minha: `EVIDENCE_WITH_CAVEATS` não é
`EVIDENCE_SUFFICIENT`, e `rules/public-copy.md § 3` veta a alegação de v1.0 sem evidência
sustentada. O gate diz isso toda vez que roda — não é um lembrete que alguém precisa manter.

## O que falta para `EVIDENCE_SUFFICIENT`

- Uma terceira evidência, vinda de uso em dia diferente. Registrar três hoje para bater o
  número seria o *dogfood theatre* que o § 7 nomeia — o soft cap existe porque um ponto não
  é tendência, e três pontos do mesmo dia também não.
- Um segundo operador, para não depender de "a única pessoa que sabe rodar".
