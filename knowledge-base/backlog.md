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

## B3 — `scan --history` custa ~6 s em repositório pequeno; o eixo é linhas, não commits

**Origem:** validação de integração do M5 (2026-07-27), rodando no próprio repositório.

**Medido:**

| Alvo | Commits | Linhas adicionadas | git | Varredura | Total |
|---|---|---|---|---|---|
| gitsafety (real) | 51 | 74.216 | 0,23 s | ~6 s | ~6 s |
| Sintético | 5.000 | ~10.000 | 0,20 s | 0,16 s | 0,37 s |
| Sintético | 1.000 | 50.000 | 0,10 s | 0,64 s | 0,74 s |

**A causa é o desenho, não um defeito:** o custo é `linhas × 53 regras`, e o perfil confirma
— 3,9 milhões de chamadas a `finditer`, com 4,6 s de overhead do laço em Python. Não há
linha patológica: a maior tem 884 caracteres e a mediana é 42.

**Por que o número sintético é otimista:** o gerador produz linhas curtas e uniformes
(~10 caracteres). Uma regex custa proporcionalmente ao comprimento, então o piso sintético
subestima o real em cerca de uma ordem de grandeza. O caveat está escrito no próprio
benchmark.

**Por que não foi otimizado no M5:** o `ROADMAP.md § M5` decide antecipadamente que o Risco
nº 1 se resolve **documentando o custo**, não adicionando flags de tuning. E o M2 já mediu
e decidiu contra um pré-filtro de literais. Reverter essa decisão exige medição própria —
uma tentativa rápida durante o M5 produziu um filtro que deixava passar 100% das linhas, ou
seja, ganho zero. Fazer direito é escopo de outro milestone.

**Quando revisitar:** se o dogfooding mostrar que alguém deixa de rodar o comando por causa
do tempo. O caminho provável é um pré-filtro de marcadores literais (`AKIA`, `ghp_`,
`postgresql://`) construído a partir do catálogo, medido contra o corpus real.

## B4 — `scan --history` não alcança commit reescrito (reflog)

**Origem:** medido na descoberta do M5 (Q5) e cobrado no review — o plano listou como
Risco nº 4 com a mitigação "declarado no blueprint e no backlog", e o registro no backlog
não tinha sido feito. Esta entrada fecha essa dívida.

**Medido:**

```
git commit -m oops              # com a credencial
git reset --soft HEAD~1 && git restore --staged leak.env && rm leak.env
gitsafety scan --history        # → Nenhum segredo encontrado
git log --all --reflog -p -U0 | grep -c AKIA   # → 1
```

**Por que:** `--all` percorre as referências (branches, tags, stash), e o reflog não é uma
referência — é o registro local de para onde `HEAD` já apontou. O commit reescrito sai das
refs mas o objeto sobrevive nele por ~90 dias.

**Por que não foi fechado no M5:** `--reflog` é uma flag só, mas muda o significado do
comando. O reflog é **local e pessoal** — ele contém o que *você* fez na sua máquina, não o
que está no repositório compartilhado. Um achado vindo dali diz "esta chave passou pelo seu
disco", não "esta chave está no histórico do projeto", e misturar as duas afirmações num
relatório só é pior que não ter a segunda.

**Mitigação entregue no M5:** o `README.md` § Histórico declara a lacuna e reforça que
reescrever o histórico não desfaz a exposição — revogar a chave é a única ação que resolve.

**Quando revisitar:** se o uso mostrar que gente conta com o comando para auditar a própria
máquina. Aí o caminho é uma seção separada no relatório, não misturar com o histórico.
