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

## B2 — Nenhuma regra da família `keyword_assignment` no catálogo

**Origem:** controle do oráculo de cobertura do M4 (2026-07-27), ao montar um vetor que
acabou sendo vazio.

**O que acontece:** as 53 regras do catálogo são todas `unique_token` — valores que se
identificam sozinhos por um prefixo literal (`AKIA`, `ghp_`, `postgresql://`). Não há
nenhuma regra que detecte um segredo pelo **nome da variável ao lado dele**.

**Impacto medido:** `aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"`
não é detectado em `.py`, `.env`, `.json` nem notebook. E essa é a credencial de fato — o
`AKIA...` que detectamos é só o identificador, inútil sozinho para um atacante. Vale para
qualquer segredo genérico: senha de banco, chave HMAC, token interno.

**Por que ficou de fora:** o M2 construiu `keyword_assignment` em `patterns.py` mas não
compôs nenhuma regra com ela. A razão é real — valores sem marcador têm alta taxa de falso
positivo, e o M2 mediu zero falsos positivos no corpus limpo justamente por não os ter.
Fechar isso exige medir a taxa de falso positivo, não só adicionar padrões.

**Impacto na promessa pública:** o `README.md` e o `docs/PRD.md` precisam ser conferidos —
se prometem "detecta credenciais AWS" sem qualificar, a frase está mais larga que o
comportamento.

**Nota de processo:** a regra do usuário manda abrir issue no tracker para achado com repro
e evidência. O `gh` desta máquina está autenticado como outro usuário e não consegue criar
no repositório (`must be a collaborator`), então o registro fica aqui. Vale promover a
issue quando a autenticação estiver correta.
