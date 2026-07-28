# gitsafety

**Não deixa você commitar uma chave de API.**

Você instala uma vez, e a partir daí o `git commit` avisa antes de a credencial sair da sua
máquina. Funciona em repositório git, em pasta solta e em notebook Jupyter.

> **Status:** pré-1.0. Publicado no PyPI e funcional — instale e use. O `1.0.0` fica
> reservado para depois de uso sustentado em trabalho real. Testes e revisão provam
> **corretude**; `1.0.0` deveria significar **uso**, e são coisas diferentes.

---

## Começando — 3 passos

Precisa de Python 3.10 ou mais novo. Nada de Docker, nada para compilar, nada para subir.

### 1. Instale

```bash
pipx install gitsafety
```

Se não tiver o `pipx`: `python3 -m pip install --user pipx && python3 -m pipx ensurepath`.

<details>
<summary>Prefere <code>pip</code> num ambiente virtual? Leia isto antes.</summary>

`pip install gitsafety` funciona, mas o hook chama `gitsafety` pelo PATH **na hora do
commit**. Se o ambiente virtual não estiver ativo naquele momento, **todo commit falha** com
`gitsafety: not found`. O `pipx` deixa o comando disponível sempre.

Descobrimos isso instalando no nosso próprio repositório — está registrado em
[`knowledge-base/dogfood/`](knowledge-base/dogfood/).
</details>

### 2. Ligue no seu projeto

Dentro da pasta do repositório, uma vez só:

```bash
gitsafety install
```

```console
  hook instalado em /home/ana/meu-projeto/.git/hooks/pre-commit
  A partir de agora o commit é verificado.
  Emergência: git commit --no-verify
```

### 3. Trabalhe normalmente

Não há passo 4. O `git commit` continua sendo `git commit` — a diferença aparece só quando
há uma credencial no que você está enviando:

```console
$ git commit -m "adiciona cliente S3"

  app.py:6   aws-access-key-id   AKIA••••••••••••MPLE

  1 segredo encontrado.
  Revogue a chave no provedor antes de qualquer outra coisa.
```

O commit **não** aconteceu. Tire a chave do código (use variável de ambiente, cofre, o que
o seu time usar), commite de novo, e pronto.

> **Por que "revogue a chave" e não "apague a linha".** Se a chave já saiu da sua máquina
> alguma vez, apagá-la do código não a desativa. Quem a copiou continua com ela. Revogar no
> provedor é a única ação que resolve de verdade — o resto é limpeza.

---

## Já commitei uma chave antes de instalar. E agora?

O hook protege daqui para frente. Para olhar para trás:

```bash
gitsafety scan --history
```

```console
  antigo.py:1   postgres-connection-string   post•••••••••••••••••••••••••••••.com
      6773ba6b  Ana  2026-07-28T08:35:13-03:00

  1 segredo encontrado no histórico.
  Revogue a chave no provedor antes de qualquer outra coisa.
  Remover o arquivo agora NÃO apaga o segredo do histórico.
```

Ele mostra **quando a chave entrou e por quem** — é o que decide a urgência. E funciona
mesmo que o arquivo já tenha sido apagado: o histórico do git lembra, e qualquer pessoa que
clonou o repositório também.

---

## Os três comandos, e quando usar cada um

| Comando | O que olha | Quando você usa |
|---|---|---|
| `gitsafety install` | — | Uma vez por repositório, no começo |
| *(o hook, sozinho)* | o que você está commitando | Automático, a cada `git commit` |
| `gitsafety scan` | os arquivos da pasta agora | Antes de abrir um PR, ou por curiosidade |
| `gitsafety scan --history` | tudo que já foi commitado | Ao adotar num projeto que já existe |

Emergência: `git commit --no-verify` passa por cima do hook. Existe porque bloquear alguém
sem saída faz a pessoa desinstalar a ferramenta.

---

## Por que ele não enche o saco

O hook verifica **apenas as linhas que você está introduzindo** — não o repositório
inteiro, e nem mesmo o arquivo inteiro. Para conteúdo de texto, medido: o commit fica
**~0,04 s** mais lento, independente de tocar 1 ou 200 arquivos
([benchmark](benchmarks/bench_hook.py)).

Commitar **binário** é outra história: o hook lê o conteúdo para não deixar um segredo
passar disfarçado de arquivo binário, e isso custa. Medido: 30 MB de binário no mesmo
commit levam ~4,5 s. Não é o caso comum — mas se o seu primeiro commit com a ferramenta
inclui uma pasta de assets, é bom saber. Ponha o caminho em `ignore:` se ele nunca vai
conter credencial.

Isso tem uma consequência que vale saber: se um arquivo **já tinha** um segredo commitado
antes e você edita outra linha dele, o hook não reclama. É deliberado — do contrário,
adotar a ferramenta num repositório com história bloquearia todo commit até alguém
limpar o passado. Para achar o que já está lá, use `gitsafety scan` na pasta inteira.

E ele só dispara em **padrão conhecido de credencial** — `AKIA` seguido de 16
maiúsculas é uma chave da AWS, não tem outra leitura. Nada de heurística de
"parece aleatório", que é o que enche relatório de falso positivo e faz o time
desligar a ferramenta na segunda semana.

A única regra que olha o **contexto** em vez do valor é a genérica: ela exige o nome da
variável (`password`, `api_key`, `aws_secret_access_key`…), o operador de atribuição, e um
valor de 20+ caracteres **com dígito e letra**. Isso é o que separa uma credencial de um
identificador de código — `secret_key = settings.SECRET_KEY` não casa, `token = os.environ[...]`
não casa. Medido: **zero** falsos positivos em 72.570 linhas de código dos projetos de
referência, e **3** num corpus maior de 1,3 milhão de linhas — a classe deles está descrita
logo abaixo.

Ela tem fronteira, e vale saber qual. **Não** pega: valor em outra linha, valor montado por
concatenação, senha com símbolo nos primeiros 20 caracteres (`"S3nh4@Sup3r..."`), senha só
de letras, e nomes que ela não conhece (`pwd`, `credential`). **Pega às vezes demais:**
anotação de tipo em Python tem a mesma forma de um segredo em YAML, e a regra não distingue
as duas <!-- gitsafety: allow -->. Foram 3 ocorrências em 1,3 milhão de linhas de código
real. Para essas, use `allow:` ou `ignore:`.

---

## O que ele detecta

Sem configurar nada:

| Categoria | Regras | Exemplos |
|---|---|---|
| Cloud | 8 | AWS, Google Cloud, Azure, DigitalOcean, Heroku, Cloudflare |
| Git / pacotes | 11 | GitHub (`ghp_`, `github_pat_`, `gho_`, `ghs_`, `ghr_`), GitLab, npm, PyPI, RubyGems, crates.io |
| IA e dados | 6 | OpenAI (`sk-`), Anthropic (`sk-ant-`), Hugging Face, Cohere, Replicate, W&B |
| Pagamentos e SaaS | 19 | Stripe, Twilio, SendGrid, Slack, Sentry, Shopify, Atlassian, Linear, JWT |
| Chaves privadas | 4 | Blocos PEM, PuTTY, PKCS#8 cifrada, age |
| Banco de dados | 5 | Strings de conexão com senha: PostgreSQL, MySQL, MongoDB, Redis, AMQP |
| Genéricas | 1 | Credencial atribuída a variável de nome revelador: `aws_secret_access_key`, `password`, `api_key`, `token`, `client_secret`… |

**54 padrões no total.** Cada um traz seus próprios exemplos de acerto e de não-acerto,
verificados a cada execução da suíte.

O que for específico do seu time entra no YAML — veja abaixo.

### Notebooks Jupyter

`.ipynb` é tratado como caso de primeira classe: o gitsafety lê o JSON do notebook e
verifica **o código das células e também as saídas salvas**. É onde a chave escapa
com mais frequência — você apaga a célula, mas o `print(os.environ)` de três
execuções atrás continua gravado no arquivo que vai para o commit.

O achado aponta a **célula**, não a linha do JSON:

```
analise.ipynb :: célula 4 (saída):1   postgres-connection-string   post•••••••••.com
```

Um notebook aberto no Jupyter não tem linha 50, então reportar a linha do arquivo não
ajudaria ninguém a achar o segredo. Saídas de `print`, de resultado de célula e de
traceback de erro são todas verificadas — o traceback de uma chamada autenticada que
falhou costuma guardar a credencial inteira.

Notebook corrompido ou truncado não quebra a varredura: ele volta a ser lido como texto,
porque um arquivo que o parser recusa ainda pode conter a chave.

### Histórico

O hook impede que a chave **entre**. Para saber se ela já entrou antes:

```bash
gitsafety scan --history
```

```
config.py:1   aws-access-key-id   AKIA••••••••••••MPLE
    b7cc2556  Ana  2026-07-27T15:33:54-03:00

1 segredo encontrado no histórico.
Revogue a chave no provedor antes de qualquer outra coisa.
Remover o arquivo agora NÃO apaga o segredo do histórico.
```

O commit mostrado é o da **introdução** — "desde quando esta chave está exposta?" é a
pergunta que decide a urgência. Apagar o arquivo hoje não resolve: o objeto continua no
histórico de todo mundo que já clonou o repositório.

Um segredo que aparece em vários commits vira **um** achado, com a contagem ao lado quando
foi reintroduzido depois de sair.

O custo é proporcional às **linhas** do histórico, não aos commits. No próprio repositório
do gitsafety — 74 commits, 77 mil linhas adicionadas — leva cerca de 2,5 segundos
([benchmark](benchmarks/bench_history.py)). É um comando para rodar de vez em quando, não a
cada commit; para isso existe o hook.

**O que ele não vê — e avisa.** Se você reescreveu o histórico com `git reset`, `rebase` ou
`commit --amend`, o commit antigo saiu das referências e o `--history` não o alcança. Ele
diz isso em vez de deixar você concluir que está limpo:

```
Nenhum segredo encontrado.

Atenção: 1 commit reescrito não foi verificado.
Se foi para remover uma chave, revogue-a: reescrever não desfaz a exposição.
```

O objeto continua no seu repositório local por cerca de 90 dias, recuperável pelo reflog. E
reescrever o histórico nunca desfez uma exposição: **revogar a chave no provedor** é a única
ação que resolve.

---

## Configuração

Opcional. Sem arquivo nenhum, os padrões embutidos valem. Para ajustar, crie um
`.gitsafety.yml` na raiz do repositório:

```yaml
# .gitsafety.yml — as três chaves são opcionais

# Caminhos que nem são abertos (glob)
ignore:
  - "tests/fixtures/**"
  - "docs/exemplos/**"

# Valores conhecidos e inofensivos (texto exato ou regex)
allow:
  - "AKIAIOSFODNN7EXAMPLE"    # chave de exemplo da documentação da AWS
  - "sk-test-.*"              # chaves do ambiente de teste do Stripe

# Seus próprios padrões
rules:
  - id: chave-interna
    pattern: "INTERNAL_KEY_[A-Za-z0-9]{20}"
  - id: token-do-cliente
    pattern: "cli_[a-f0-9]{32}"
```

Três chaves de topo — `ignore`, `allow`, `rules` — e nada mais. Sem herança de
config, sem `condition: AND/OR`, sem regra composta.

**Chave com erro de digitação não é ignorada.** `ignroe:` para o scan e sugere `ignore:` —
o silêncio custaria a você uma sessão de depuração descobrindo que a config nunca foi lida.

**Seus padrões são verificados antes de rodar.** Um regex inválido vira erro com o nome da
regra. Um regex que poderia travar a verificação no meio de um commit — como
`(a{1,50}){1,50}` — é recusado na carga, com a explicação. É o seu commit que estaria
pendurado.

YAML inválido ou regex que não compila **param o scan com erro apontando a linha**
(exit code 2). Nunca são ignorados em silêncio.

Outro arquivo: `gitsafety scan --config caminho/config.yml`.

### Quer pegar senha solta também?

Não vem ligado, porque gera falso positivo. Se o seu time aceita a troca, cole isto
no `rules:`:

```yaml
  - id: senha-hardcoded
    pattern: "(?i)(password|senha|secret|token|api_key)\\s*[=:]\\s*['\"][^'\"]{8,}['\"]"
```

---

## Ignorando um finding

Da forma mais local para a mais ampla:

**1. Na linha** — para segredo de teste commitado conscientemente:

```python
API_KEY = "sk-test-4eC39HqLyjWDarjtT1zdp7dc"  # gitsafety: allow
```

**2. Por valor** — no `allow:`, quando o mesmo valor aparece em vários arquivos.

**3. Por caminho** — no `ignore:`, quando a pasta inteira é irrelevante.

---

## Sobre o hook

`gitsafety install` escreve `.git/hooks/pre-commit` chamando
`gitsafety scan --staged`. Não depende do framework `pre-commit` nem de qualquer
outra ferramenta.

Se já existir um `pre-commit` no repositório, o comando **recusa e avisa** em vez de
sobrescrever o seu hook — ele te mostra a linha para adicionar no hook existente.

---

## No CI

Qualquer runner com Python. Em GitHub Actions:

```yaml
- name: Verifica segredos
  run: |
    pipx install gitsafety
    gitsafety scan --history
```

Exit code 1 quando encontra segredo, o que já reprova o job.

---

## Saída e exit codes

O segredo aparece **mascarado por padrão** — o relatório não pode virar o próximo
vazamento. `--show-secrets` mostra o valor completo quando você realmente precisa.

| Exit code | Significado |
|---|---|
| `0` | Nada encontrado |
| `1` | Segredo encontrado |
| `2` | Erro (config inválida, caminho inexistente, não é repositório git) |

---

## Todas as flags

```
gitsafety install              instala o hook de pre-commit
gitsafety scan [CAMINHO]       verifica arquivos
  --staged                     apenas o que está no index do git
  --history                    o histórico do git, em vez do disco
  --show-secrets               mostra o segredo completo
  --config PATH                arquivo de config (padrão: .gitsafety.yml)
gitsafety --version            mostra a versão instalada
```

**Quatro flags no `scan`, e é o teto.** Se você sentir falta de uma quinta, o caso
provavelmente é do `.gitsafety.yml` — flag é interface que todo mundo carrega para sempre;
configuração é escolha de quem precisa dela.

`--staged` e `--history` são alvos e por isso mutuamente exclusivos: o primeiro olha o que
você está commitando, o segundo o que já foi commitado, e sem nenhum dos dois ele olha o
disco.

Esta lista é a lista inteira. `gitsafety scan --help` mostra exatamente estas flags, e um
teste da suíte compara as duas nas duas direções a cada execução — flag documentada que não
existe, e flag que existe sem documentação.

---

## O que o gitsafety **não** faz

Fora de escopo de propósito — cada item é complexidade que o público não pediu:

- **Não remove o segredo do histórico.** Detectar e reescrever histórico são
  problemas diferentes; reescrita é destrutiva e fica com `git filter-repo` / BFG.
- **Não é cofre de senhas** nem rotaciona credenciais.
- **Não escaneia dentro de `.zip` / `.tar.gz`** nem decodifica base64 e hex.
- **Não usa entropia** nem herança de config, regra composta ou `condition AND/OR`.
- **Não emite CSV, JUnit, SARIF nem template** — saída humana e exit code.
- **Não roda como serviço** nem tem imagem Docker.

Precisa de algo dessa lista? [gitleaks](https://github.com/gitleaks/gitleaks) e
[trufflehog](https://github.com/trufflesecurity/trufflehog) cobrem esse território —
é a recomendação honesta.

---

## Regra número um

Segredo detectado é segredo **comprometido**. Apagar a linha, refazer o commit ou
adicionar ao `allow:` não desfaz a exposição.

1. **Revogue e rotacione a chave** no provedor.
2. Só depois limpe o código.

O gitsafety encontra; quem fecha a porta é você.

---

## Licença

Implementação própria, sob licença MIT (ver `LICENSE`).

A abordagem de hook de pre-commit com catálogo de padrões conhecidos é prática
consagrada na área — [gitleaks](https://github.com/gitleaks/gitleaks) é a referência
mais completa. Nenhum código foi copiado.
