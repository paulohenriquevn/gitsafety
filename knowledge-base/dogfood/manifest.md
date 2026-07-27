# Dogfood manifest — gitsafety

## Cenário-âncora

**Slug:** `hook-no-proprio-repositorio`

**Status:** `wired`

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

## Estado honesto (2026-07-27)

O hook foi instalado **hoje**. Antes disso o projeto tinha **65 commits sem nenhuma
verificação** — o detector de segredos não rodava o próprio detector, o que é precisamente
o tipo de coisa que este gate existe para expor.

`Status: wired` e não `running` porque `running` significa, pelo
`rules/dogfood-golden-rule.md § 2`, "ativamente usado pelo time em infraestrutura real" — e
um dia de uso não é uso sustentado. Declarar `running` hoje seria o "dogfood theatre" que o
§ 7 da mesma regra nomeia como modo de falha.

**Consequência: o `1.0.0` continua barrado**, e essa é a resposta correta.

## O que falta para `running`

- Uso continuado, com commits reais passando pelo hook ao longo de semanas.
- Ao menos três evidências registradas, sendo uma delas uma história de **falha**.
- Idealmente um segundo operador — para não depender de "a única pessoa que sabe rodar".
