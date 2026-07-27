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

## B3 — RESOLVIDO POR DECISÃO: o custo do `--history` fica como está

**Origem:** validação de integração do M5; investigado a fundo ao fechar a issue #4.

**O custo, medido:** ~6 s no repositório do gitsafety (51 commits, 74 mil linhas
adicionadas). O eixo é `linhas × regras`, não commits. O perfil mostra 4 milhões de
chamadas a `finditer` e ~4,6 s de overhead do laço em Python.

**Três otimizações medidas — duas piores, uma rejeitada:**

| Hipótese | Resultado |
|---|---|
| Pré-filtro de marcadores literais | **2× mais lento**, e perdia 1 casamento |
| Regex única combinada com grupos nomeados | **3,5× mais lento**, e perdia 11 casamentos |
| Pular linhas mais curtas que o menor casamento possível | **1,40× mais rápido**, achados idênticos |

O pré-filtro falha porque 23 das 54 regras não têm literal obrigatório e rodam de qualquer
forma, e porque o `re` do Python **já** otimiza prefixo literal internamente — o filtro
explícito duplica trabalho que a biblioteca faz melhor. Isso explica o "ganho zero" da
tentativa anterior, que eu tinha registrado sem entender.

A regex combinada falha porque a alternância para no primeiro casamento de cada posição:
dois segredos sobrepostos de regras diferentes viram um.

**Por que a terceira, que funciona, foi rejeitada.**

O ganho é 1,40× — de ~6 s para ~4,3 s. Isso não muda a decisão de ninguém sobre rodar ou
não o comando. E o mecanismo tem uma condição de correção que eu não sei **provar**: o piso
teria de ser o menor casamento que qualquer regra pode produzir, e isso não é derivável do
`re` sem escrever um analisador de regex. Um piso derivado dos exemplos do catálogo é
empírico — uma regra futura que case algo mais curto que os próprios exemplos vira **falso
negativo silencioso**.

Trocar 1,7 segundo por um mecanismo cuja falha é silenciosa é exatamente o negócio que o M4
mostrou ser ruim: cinco rodadas de review para eliminar defeitos dessa classe. E o
`ROADMAP.md § M5` já tinha decidido: documentar o custo, não adicionar tuning.

**Se alguém revisitar:** o caminho é derivar o piso **soundly** da estrutura da regex (soma
dos mínimos de literais e quantificadores), com um teste que fuzza cada regra procurando
casamento abaixo do piso. Aí o mecanismo deixa de ser empírico. Antes disso, não vale.

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

## B4b — RESOLVIDO: C-quoting de caminho (era MEDIUM do review do M5)

Corrigido em `staged.py::_decode_path`. `ignore:` valia para nome ASCII e falhava em
silêncio para nome acentuado — mesma classe do defeito que a validação de integração do M5
pegou, com o eixo no nome do arquivo em vez de no alvo. Direção da falha era ruído (reportava
a mais), mas num projeto brasileiro acento em nome de arquivo é o caso comum.

## B5 — `--text` custa caro em binário, e não há teto por arquivo no hook

**Origem:** review do M5, ao atacar as flags introduzidas para fechar o fail-open do
`.gitattributes`.

**Medido** (30 MB de binário aleatório no index, contra 200 arquivos de texto):

| Conteúdo | Tempo | Pico de memória | Achados |
|---|---|---|---|
| 200 arquivos de texto | 0,22 s | — | 0 |
| 30 MB de binário | **5,67 s** | **416 MB** | 0 |

**Por que a flag existe mesmo assim:** sem `--text`, um `.gitattributes` com `-diff`, um
byte NUL ou um driver `textconv` faziam o hook **deixar passar** o commit da credencial.
Reverter reabre o fail-open. O custo é o preço da defesa.

**Direção da falha:** segura. Se o hook estourar a memória e for morto, o git vê exit
não-zero e **bloqueia** o commit. Degrada fechado.

**Por que o teto por arquivo não entrou no M5:** o `scan` pula arquivo acima de 1 MB e
**reporta o pulo** (`ScanResult.skipped`, contrato do M0). Copiar esse teto para o hook
parece óbvio e não é: um arquivo de **texto** de 2 MB com uma credencial deixaria de
bloquear o commit. Isso é perda de cobertura no único caminho que não pode perder. Um teto
que sirva aqui precisa distinguir volume de risco — provavelmente por conteúdo binário, não
por tamanho — e essa é uma decisão com medição própria, não uma cópia.

**Quando revisitar:** M6 ou antes, se o dogfooding mostrar alguém desinstalando o hook por
causa do primeiro commit num projeto com assets.
