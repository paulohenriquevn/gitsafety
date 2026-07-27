# gitsafety

**Não deixa você commitar uma chave de API.**

Um comando para instalar, um YAML para ajustar. Funciona em repositório git, em
pasta solta e em notebook Jupyter.

> **Status:** pré-1.0, em desenvolvimento. A interface abaixo é o contrato que
> estamos construindo; ainda não há release publicado.

---

## Instalação

Requer Python 3.10 ou superior.

```bash
pipx install gitsafety     # recomendado — isolado, disponível no PATH
pip install gitsafety      # dentro de um venv ou de um ambiente de notebook
```

Sem Docker, sem compilar nada, sem serviço para subir.

---

## Uso

```bash
# 1. Instala o hook neste repositório — faça uma vez
gitsafety install

# 2. Pronto. O commit passa a ser verificado.
git commit -m "novo cliente da API"
```

```console
  src/client.py:18   openai-api-key   sk-p••••••••••••••••••••1a9f

  Commit bloqueado: 1 segredo encontrado.
  Revogue a chave antes de qualquer outra coisa.
```

Os outros dois usos:

```bash
gitsafety scan              # verifica os arquivos da pasta atual
gitsafety scan --history    # verifica o histórico do git (chave commitada no passado)
```

Emergência: `git commit --no-verify` passa por cima do hook.

---

## Por que ele não enche o saco

O hook verifica **apenas os arquivos que entram no commit** (`--staged`), não o
repositório inteiro. Fora isso, pula binários e arquivos acima de 1 MB. Na prática o
commit não fica perceptivelmente mais lento.

E ele só dispara em **padrão conhecido de credencial** — `AKIA` seguido de 16
maiúsculas é uma chave da AWS, não tem outra leitura. Nada de heurística de
"parece aleatório", que é o que enche relatório de falso positivo e faz o time
desligar a ferramenta na segunda semana.

---

## O que ele detecta

Sem configurar nada:

| Categoria | Exemplos |
|---|---|
| Cloud | AWS, Google Cloud, Azure |
| Git / pacotes | GitHub (`ghp_`, `github_pat_`), GitLab, npm, PyPI |
| IA e dados | OpenAI (`sk-`), Anthropic (`sk-ant-`), Hugging Face |
| Pagamentos e SaaS | Stripe, Twilio, SendGrid, Slack |
| Chaves privadas | Blocos PEM (`BEGIN ... PRIVATE KEY`) |
| Banco de dados | Strings de conexão com senha (`postgres://user:senha@host`) |

O que for específico do seu time entra no YAML — veja abaixo.

### Notebooks Jupyter

`.ipynb` é tratado como caso de primeira classe: o gitsafety lê o JSON do notebook e
verifica **o código das células e também as saídas salvas**. É onde a chave escapa
com mais frequência — você apaga a célula, mas o `print(os.environ)` de três
execuções atrás continua gravado no arquivo que vai para o commit.

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
gitsafety scan [CAMINHO]       verifica arquivos                        ✅ disponível
  --show-secrets               mostra o segredo completo                ✅ disponível
gitsafety --version                                                     ✅ disponível

gitsafety install              instala o hook de pre-commit             ⏳ em construção
  --staged                     apenas os arquivos em stage              ⏳ em construção
  --history                    também o histórico do git                ⏳ em construção
  --config PATH                arquivo de config (padrão: .gitsafety.yml) ⏳ em construção
```

Quatro flags no total. Se você sentir falta de uma quinta, provavelmente o caso é do
`.gitsafety.yml`.

> **⏳ em construção** = faz parte do contrato do produto e ainda não foi implementado.
> `gitsafety scan --help` sempre lista **apenas** o que existe de verdade no binário que
> você instalou — nenhuma flag anunciada na ajuda deixa de funcionar.

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
