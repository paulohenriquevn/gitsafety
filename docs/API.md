# Referência do gitsafety

O contrato completo: comandos, flags, configuração, códigos de saída e formato de saída.
Para o passo a passo de quem está começando, veja o [README](../README.md).

Esta é a referência da versão **0.8.0**. Mudanças estão no [CHANGELOG](../CHANGELOG.md).

---

## Comandos

### `gitsafety install`

Escreve `.git/hooks/pre-commit` chamando `gitsafety scan --staged`. Não depende do framework
`pre-commit` nem de qualquer outra ferramenta.

```bash
gitsafety install
```

| | |
|---|---|
| Onde escreve | O caminho que `git rev-parse --git-path hooks` responde — respeita `core.hooksPath` |
| Se já existe um hook nosso | Reescreve, silenciosamente. É idempotente |
| Se já existe um hook de terceiro | **Recusa** e imprime a linha a acrescentar no hook existente. Nunca sobrescreve |
| Permissão | `0700` |
| Exige | Que `gitsafety` esteja no `PATH` — o hook o invoca por nome na hora do commit |

O comando verifica o `PATH` **no momento da instalação**. Se você instalar num ambiente
virtual e commitar fora dele, todo commit falhará com `gitsafety: not found`. Por isso o
README recomenda `pipx`.

### `gitsafety scan`

Verifica arquivos e reporta os segredos encontrados.

```bash
gitsafety scan [CAMINHO] [--staged | --history] [--show-secrets] [--config PATH]
```

`CAMINHO` é um arquivo ou diretório; o padrão é o diretório atual. Ele é **mutuamente
exclusivo** com `--staged` e `--history`, porque os três são alvos diferentes.

### `gitsafety --version`

Imprime a versão instalada. A versão vem do metadado do pacote, não de uma constante — não
há dois lugares para divergir.

---

## Superfície da CLI

O `scan` tem **quatro flags**, e esse é o teto declarado do projeto. Ampliar exige
justificativa explícita, porque flag é interface que todo usuário carrega para sempre,
enquanto configuração é escolha de quem precisa dela.

| Flag | Efeito |
|---|---|
| `--staged` | Verifica o índice do git em vez do disco — **apenas as linhas sendo introduzidas** |
| `--history` | Percorre o histórico do git em vez do disco |
| `--show-secrets` | Exibe o valor íntegro. Sem ela, o segredo sai mascarado |
| `--config PATH` | Usa outro arquivo de configuração |

### Os três alvos

| Alvo | O que examina | Consequência |
|---|---|---|
| *(padrão)* | Os arquivos que existem para o git | Pula binário por extensão e qualquer arquivo acima de 1 MB, e **reporta o pulo** |
| `--staged` | As linhas adicionadas no índice | Um segredo que já estava no arquivo e você não tocou **não** bloqueia o commit — do contrário, adotar a ferramenta num repositório com história bloquearia tudo |
| `--history` | As linhas adicionadas em todo o histórico | Encontra o que já foi commitado, mesmo que o arquivo tenha sido apagado depois |

#### O alvo padrão respeita o `.gitignore`

Dentro de um repositório git, o alvo padrão é o que o git enxerga: rastreados mais
não-rastreados que o `.gitignore` não exclui. `node_modules/`, `.venv/`, `dist/`,
`.terraform/` e o próprio `.git/` saem da varredura sem você configurar nada.

Não é otimização — é ruído. Achado dentro de `node_modules/` é falso positivo por
definição: você não escreveu aquele código e não pode corrigi-lo.

| Situação | O que acontece |
|---|---|
| Fora de repositório git | Varre o disco, como sempre |
| `git` ausente do `PATH` | Varre o disco — o git só é **exigido** por `--staged` e `--history` |
| Arquivo ignorado, mas versionado com `git add -f` | **Varrido.** O que está no repositório é o que pode vazar |
| Arquivo novo, ainda não adicionado | **Varrido.** É onde a chave recém-colada costuma estar |
| `gitsafety scan .env` num `.env` ignorado | **Varrido.** Alvo explícito é pedido explícito |

O que se perde: um `.env` gitignorado com credencial real não aparece no `scan` de pasta.
Ele também nunca seria commitado, que é o que a ferramenta existe para impedir — e
apontar o caminho direto continua funcionando. A decisão está em
[ADR 0003](../knowledge-base/adrs/0003-o-que-o-git-ignora-o-scan-tambem-ignora.md).

#### A configuração é a do alvo

`gitsafety scan /outro/projeto` usa o `.gitsafety.yml` de `/outro/projeto`, não o do
diretório de onde você chamou. `--staged` e `--history` continuam usando o do
repositório corrente, porque ali o alvo é ele mesmo.

---

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | Nenhum segredo encontrado |
| `1` | Segredo encontrado |
| `2` | Erro de uso: configuração inválida, caminho inexistente, não é repositório git, `git` ausente do `PATH`, falha do próprio git |

O `2` nunca é silencioso: vem acompanhado de mensagem específica em `stderr`. Não existe
"erro inesperado" nem varredura parcial sem aviso — se algo impede a verificação, o comando
para e diz o quê.

---

## Formato de saída

```
caminho:linha   id-da-regra   segredo-mascarado
```

Com `--history`, cada achado ganha uma segunda linha:

```
config.py:1   aws-access-key-id   AKIA••••••••••••MPLE
    b7cc2556  Ana  2026-07-27T15:33:54-03:00   (2 introduções)
```

| Campo | Conteúdo |
|---|---|
| sha abreviado | O commit onde a ocorrência foi **introduzida**, não o mais recente |
| autor | O `%an` do commit |
| data | ISO-8601, do `%aI` |
| `(N introduções)` | Aparece só quando N > 1: a credencial foi recolocada depois de ter saído |

Em notebook `.ipynb`, o caminho carrega a célula:

```
analise.ipynb :: célula 4 (saída):1   postgres-connection-string   post•••••••••.com
```

A origem é `código`, `saída`, `metadados`, `anexo` ou `conteúdo`. Saídas numeradas quando a
célula tem mais de uma.

Quando há achado, a última linha manda **revogar a chave no provedor**. É deliberada: apagar
a linha do arquivo não desfaz a exposição, e o reflexo de quem é pego pelo hook é editar o
arquivo e seguir. A chave já vazou no momento em que foi escrita.

### Mascaramento

O segredo sai **mascarado por padrão**, em toda saída. Só os quatro primeiros e os quatro
últimos caracteres aparecem; o miolo vira `•`. Valores de até oito caracteres são mascarados
por inteiro.

`--show-secrets` revela o valor. O padrão é o oposto porque a saída de um detector de
segredos vai para logs de CI, terminais compartilhados e capturas de tela.

---

## Configuração

Opcional. Sem arquivo nenhum a ferramenta funciona com os padrões embutidos — configuração é
para reduzir ruído, nunca para habilitar a detecção.

Procurado como `.gitsafety.yml` na raiz do repositório **que está sendo varrido**, ou
apontado por `--config PATH`.

```yaml
# Todas as três chaves são opcionais.

ignore:                          # globs de caminho que nem são abertos
  - "tests/fixtures/**"
  - "docs/exemplos/**"

allow:                           # valores que não geram achado (texto exato ou regex)
  - "AKIAIOSFODNN7EXAMPLE"
  - "sk-test-.*"

rules:                           # seus próprios padrões
  - id: chave-interna
    pattern: "INTERNAL_KEY_[A-Za-z0-9]{20}"
```

| Chave | Tipo | Aplica-se a |
|---|---|---|
| `ignore` | lista de globs | Caminho, relativo à raiz. Vale nos três alvos |
| `allow` | lista de texto ou regex | O **valor** encontrado |
| `rules` | lista de `{id, pattern}` | Acrescenta padrões aos embutidos |

Três chaves de topo e nada mais. Sem herança de configuração, sem `condition: AND/OR`, sem
regra composta.

### Validação

A configuração é lida e verificada **antes** da varredura — um erro nela aparece
imediatamente, não depois de percorrer mil arquivos.

| Situação | O que acontece |
|---|---|
| YAML malformado | Exit 2, com a linha do erro |
| Chave desconhecida | Exit 2, sugerindo a chave correta (`ignroe:` → `ignore:`) |
| Regex que não compila | Exit 2, nomeando a regra |
| Regex que pode travar o commit | **Recusada na carga**, com explicação |

A última linha merece atenção: um padrão como `(a{1,50}){1,50}` pode levar tempo
exponencial. Como as regras rodam dentro do `git commit`, uma regex ruim penduraria o seu
commit — então ela é recusada antes de rodar, e não depois.

---

## Supressão

Três níveis, do mais local para o mais amplo:

| Nível | Como | Quando |
|---|---|---|
| Linha | `# gitsafety: allow` na mesma linha | Segredo de teste commitado conscientemente |
| Valor | `allow:` na configuração | O mesmo valor aparece em vários arquivos |
| Caminho | `ignore:` na configuração | A pasta inteira é irrelevante |

O marcador de linha é procurado como **substring**, sem exigir caractere de comentário —
linguagens usam `#`, `//`, `--`, `;`, `%`, e exigir um deles obrigaria a saber a linguagem
do arquivo. Em Markdown, `<!-- gitsafety: allow -->` funciona pelo mesmo motivo.

---

## Detecção

54 padrões embutidos, em sete famílias. A lista com exemplos está no
[README](../README.md#o-que-ele-detecta).

Duas propriedades que valem para todos:

**Nenhuma heurística de entropia.** A detecção é por padrão conhecido de credencial. `AKIA`
seguido de 16 maiúsculas é uma chave da AWS e não tem outra leitura; "parece aleatório" tem
muitas, e é o que enche relatório de falso positivo.

**Cada regra carrega os próprios exemplos** de acerto e de não-acerto, verificados a cada
execução da suíte. Uma regra que falha os próprios exemplos não passa no CI.

### Notebooks Jupyter

`.ipynb` é lido como JSON, e **todo o conteúdo** é verificado: código das células, saídas
salvas (`print`, resultado de célula, traceback de erro), SVG, anexos e metadados de
execução. O arquivo bruto também é sempre varrido, de modo que o parsing só melhora a
localização — nunca reduz a cobertura.

Notebook corrompido ou truncado volta a ser lido como texto: um arquivo que o parser recusa
ainda pode conter a chave.

---

## Dependências

| | |
|---|---|
| Python | 3.10 ou superior |
| Dependência de runtime | Uma: `pyyaml>=6.0.1,<7` |
| Binário externo | `git`, necessário apenas para `--staged` e `--history` |
| Sistemas | Linux, macOS e Windows |

O piso de Python 3.10 não é preferência: o 3.9 está sem suporte de segurança desde
2025-10-31, e um produto de segurança não declara suporte a interpretador que não recebe
mais correção.

A dependência única é um limite declarado, não uma coincidência. Cada dependência de runtime
é superfície de ataque de cadeia de suprimentos numa ferramenta que roda em toda máquina de
desenvolvimento do time.

---

## Uso a partir de Python

Os módulos são importáveis, e `scan_path`, `scan_staged` e `scan_history` são os pontos de
entrada naturais para quem quiser roteirizar:

```python
from pathlib import Path
from gitsafety.scanner import scan_path

resultado = scan_path(Path("."))
for achado in resultado.findings:
    print(achado.path, achado.line, achado.rule_id, achado.masked_secret)
```

**Não há promessa de estabilidade nessa superfície até a 1.0.** O pacote declara apenas
`__version__` como público; o resto é organização interna e pode mudar entre versões menores
sem aviso no CHANGELOG. Se você depende disso hoje, fixe a versão.

O contrato estável é a **CLI** — comandos, flags, códigos de saída e formato de saída, tudo
descrito acima. É por ele que a ferramenta deve ser integrada.

---

## O que o gitsafety não faz

Fora de escopo por decisão, não por falta de tempo:

- **Não remove nem reescreve** segredo do histórico. Para isso existem `git filter-repo` e
  BFG — e mesmo eles não desfazem a exposição. Revogar a chave é a única ação que resolve.
- **Não é cofre** de credenciais e não as rotaciona.
- **Não escaneia archives** (`.zip`, `.tar.gz`) nem decodifica base64 ou hex. É caso de
  auditoria forense, não de pre-commit.
- **Não emite** CSV, JUnit, SARIF nem template customizado. O código de saída cobre CI.
- **Não tem imagem Docker** e não roda como serviço.

Para auditoria forense de histórico longo, com baseline e SARIF,
[gitleaks](https://github.com/gitleaks/gitleaks) e trufflehog são as ferramentas certas.

---

## Limitações

Documentadas porque existem, não porque são aceitáveis para sempre. As medições e o
raciocínio estão em [`knowledge-base/backlog.md`](../knowledge-base/backlog.md).

| Limitação | Efeito |
|---|---|
| Segredo genérico sem prefixo próprio depende do nome da variável ao lado | `password = "..."` é pego; um valor solto de 40 caracteres, não |
| Anotação de tipo em Python pode casar a regra genérica | 3 ocorrências em 1,3 milhão de linhas medidas. Use `allow:` |
| `--history` não alcança commit reescrito | O comando **avisa** quando detecta um; o objeto segue no reflog local por ~90 dias |
| Valor partido entre elementos de um notebook | Encontrado pelo `scan`; não pelo hook nem pelo `--history` |
| Custo cresce com as linhas do histórico | ~2,5 s para 77 mil linhas adicionadas. É comando de uso ocasional |
| Commit com muito binário | 30 MB levam ~4,5 s. Use `ignore:` no caminho dos assets |
