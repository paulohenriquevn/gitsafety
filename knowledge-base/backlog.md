# Backlog

Itens conhecidos, não silenciosos. Cada um traz de onde veio e por que ficou de fora.

## B1 — O hook reporta a linha do JSON em notebook; o `scan` reporta a célula

**Origem:** validação de integração do M4 (2026-07-27).

**O que acontece:**

```
gitsafety scan .   →  nb.ipynb :: célula 4 (saída):1
git commit         →  nb.ipynb:12
```

**Por que é assim:** o ADR D5 do plano do M4 decidiu que `--staged` não parseia notebooks.
O caminho do hook varre as linhas adicionadas do `git diff --staged`, não o arquivo;
mapear a linha do diff de volta para a célula exigiria ler o arquivo — um segundo caminho
de código, com risco próprio de divergir do primeiro.

**Impacto:** cosmético. O hook **bloqueia corretamente** (validado: exit 1, zero commits),
que é a função dele. O usuário roda `gitsafety scan` para saber onde está.

**Quando revisitar:** se o uso mostrar que a mensagem do hook confunde. Antes disso, seria
otimização especulativa.
