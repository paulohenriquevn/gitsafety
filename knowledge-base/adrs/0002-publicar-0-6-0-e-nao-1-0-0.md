# ADR 0002 — Publicar 0.6.0, não 1.0.0

**Data:** 2026-07-27
**Status:** aceito
**Contexto:** M6 — publicação no PyPI

## Decisão

O primeiro artefato publicado no PyPI é a **0.6.0**. O `1.0.0` fica reservado.

## O conflito

O `ROADMAP.md § M6` pede, no DoD: "`CHANGELOG.md` com a versão `1.0.0` e tag semver
anotada". Isso colide com duas regras do projeto:

- `rules/public-copy.md § 3` — "Until v1.0 with sustained measured evidence in real
  production" veta a alegação de production-ready sem evidência de uso sustentado.
- `rules/dogfood-golden-rule.md § 3` — o hard cap nº 1 (`anchor_missing`) dispara quando
  não há manifesto de dogfood. **Não há**: `knowledge-base/dogfood/` não existe. O veredito
  é `EVIDENCE_INSUFFICIENT`, e a skill existe precisamente para barrar a alegação de v1.0.

## Rationale

O roadmap é um documento de planejamento; as golden rules são **travadas** e exigem ADR para
mudar. Entre um item de DoD escrito antes de existir código e uma regra que o projeto marcou
como inquebrável, prevalece a regra.

E o mérito acompanha a hierarquia: `1.0.0` comunica ao usuário "isto foi usado a sério e
aguentou". Não foi. O produto tem 1568 testes e cinco rodadas de review adversarial, o que é
evidência de **corretude**, não de **uso**. São coisas diferentes, e confundi-las é o que a
regra impede.

Publicar no PyPI é irreversível: uma versão nunca é substituída, só retirada de circulação.
Se eu publicasse `1.0.0` e a alegação fosse falsa, ela ficaria gravada. Publicar `0.6.0` e
subir para `1.0.0` depois do dogfooding não custa nada.

## Alternativas consideradas

- **Publicar `1.0.0` como o DoD pede** — viola duas regras, uma delas travada, e faz uma
  alegação que o próprio projeto criou um gate para impedir.
- **Não publicar até haver dogfooding** — o objetivo do M6 é tornar verdadeiro o
  `pipx install gitsafety` do README. Adiar mantém o README mentindo, que é o problema que o
  milestone existe para resolver. E o roadmap recomenda registrar o nome cedo.
- **Publicar como `1.0.0rc1`** — pré-release não é instalável por `pipx install gitsafety`
  sem flag, então não satisfaz o DoD nº 1.

## Consequências

- O DoD nº 3 do M6 (`CHANGELOG` com `1.0.0`) fica **não cumprido**, deliberadamente, e o
  milestone é marcado com essa ressalva explícita — não como se estivesse completo.
- O caminho para o `1.0.0` passa a ser: criar `knowledge-base/dogfood/manifest.md` com um
  cenário-âncora, usar a ferramenta de verdade, registrar evidência, e rodar `/dogfood`.
  Enquanto o veredito não for `EVIDENCE_SUFFICIENT`, `1.0.0` continua barrado.
