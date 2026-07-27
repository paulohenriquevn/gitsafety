# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/) · Versionamento: [SemVer](https://semver.org/)

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.5.0] - 2026-07-27

### Added

- **Notebooks Jupyter (`.ipynb`) passam a ser lidos como notebook, não como texto.** O
  achado aponta a **célula** e a linha dentro dela — `analise.ipynb :: célula 4 (saída):1`
  — em vez da linha do JSON, que não existe quando você abre o arquivo no Jupyter (#M4)
- Saídas salvas de `print`, de resultado de célula e de **traceback de erro** são
  verificadas. O traceback de uma chamada autenticada que falhou costuma guardar a
  credencial inteira (#M4)
- Notebooks no formato antigo (`nbformat` v3) são reconhecidos — antes o código dessas
  células passava sem verificação (#M4)
- **Todo o conteúdo do notebook é verificado**, não apenas o código e as saídas de texto:
  tabelas HTML de resultado (o `repr` de um DataFrame), saídas em JSON e markdown, anexos
  de células markdown, e os parâmetros de execução gravados pelo papermill nos metadados.
  Cada um desses já foi caminho de vazamento real (#M4)
- Segredo nos metadados do notebook é localizado como `metadados do notebook`; anexos e
  metadados de célula apontam a célula a que pertencem (#M4)
- Saídas em SVG são verificadas — SVG é texto, e um gráfico gerado com um rótulo indevido
  pode carregar a credencial (#M4)
- Segredo usado como **nome de campo** (e não como valor) é encontrado — por exemplo uma
  chave de API virando rótulo em metadados de célula (#M4)

### Changed

- Um segredo partido entre linhas de uma célula passa a ser encontrado. O Jupyter quebra
  linhas longas ao salvar, e o valor partido escapava da verificação (#M4)
- Notebook corrompido ou truncado volta a ser lido como texto em vez de ser recusado — um
  arquivo que o parser não entende ainda pode conter a chave (#M4)
- O mesmo segredo em dois lugares do notebook gera **dois** achados. Você precisa saber de
  todos os lugares de onde removê-lo, não apenas do primeiro (#M4)

### Fixed

- `# gitsafety: allow` volta a funcionar em linha que o Jupyter partiu ao salvar. A
  supressão que você pede não deve depender de onde o editor escolheu quebrar a linha (#M4)
- Segredo com acento ou outro caractere não-ASCII não é mais reportado duas vezes, e o
  valor exibido é o que está de fato no arquivo (#M4)
- Um `.ipynb` corrompido de forma extrema não interrompe mais a varredura dos demais
  arquivos do diretório (#M4)
- Um `# gitsafety: allow` em uma célula não silencia mais, por engano, um segredo
  **diferente** em outro ponto do mesmo notebook (#M4)
- Segredo contendo barra invertida não é mais reportado duas vezes (#M4)
- Um segredo em campo de forma inesperada, em imagem embutida, ou em duas saídas
  consecutivas sem quebra de linha entre elas volta a ser reportado — antes o notebook
  podia esconder o que a varredura de um arquivo comum encontraria (#M4)
- Um valor parecido com um segredo mas que não é um (a chave dentro de um nome de arquivo,
  por exemplo) não faz mais o mesmo segredo ser reportado duas vezes nem faz um
  `# gitsafety: allow` deixar de valer (#M4)
- Os achados de um notebook saem na ordem do arquivo, também quando ele foi salvo sem
  indentação (#M4)

## [0.4.0] - 2026-07-27

### Added

- **`.gitsafety.yml`** com três chaves: `ignore` (globs de caminho que nem são abertos),
  `allow` (valores conhecidos que não geram finding) e `rules` (seus próprios padrões).
  Todas opcionais — sem o arquivo, nada muda.
- **`# gitsafety: allow`** na linha suprime o finding daquela linha. Funciona com qualquer
  caractere de comentário.
- **`--config PATH`** aponta outro arquivo de configuração.
- Config malformada **para** a execução com exit 2 e a linha do erro; chave com erro de
  digitação sugere a correta em vez de ser ignorada em silêncio.
- Padrões vindos da sua configuração são **verificados antes de rodar**: regex inválida
  vira erro com o nome da regra, e padrões que poderiam travar a verificação durante um
  commit são recusados na carga.


### Changed

- **Primeira dependência de runtime do produto:** `pyyaml>=6.0.1,<7`, usada apenas através
  de `safe_load`. É a única que o projeto autoriza.

## [0.3.0] - 2026-07-27

### Added

- **Catálogo com 53 padrões de credencial** cobrindo as 6 categorias documentadas: cloud
  (AWS, GCP, Azure, DigitalOcean, Heroku, Cloudflare), controle de versão e pacotes
  (GitHub, GitLab, npm, PyPI, RubyGems, crates.io), IA (OpenAI, Anthropic, Hugging Face,
  Cohere, Replicate, W&B), pagamentos e SaaS (Stripe, Twilio, SendGrid, Slack, Sentry,
  Shopify, Atlassian, JWT), chaves privadas (PEM, PuTTY, PKCS#8, age) e bancos de dados
  (PostgreSQL, MySQL, MongoDB, Redis, AMQP).
- Cada padrão carrega seus próprios exemplos de acerto **e de não-acerto**, verificados
  a cada execução da suíte — uma regra que falha seus próprios exemplos não passa no CI.
- Verificação mecânica de que nenhum padrão tem quantificador sem teto, e medição de
  tempo por regra contra entradas adversariais: nenhuma regex pode pendurar o commit.
- Corpus limpo de referência para medir falso positivo de forma reprodutível.
  Resultado: **zero findings**.

## [0.2.0] - 2026-07-27

### Added

- **`gitsafety install`** — escreve `.git/hooks/pre-commit` e passa a verificar todo
  commit. Respeita `core.hooksPath`, é idempotente, e **recusa-se a sobrescrever** um hook
  de outra ferramenta: em vez disso imprime a linha exata a acrescentar no hook existente.
- **`gitsafety scan --staged`** — verifica o que está no index do git em vez do disco, e
  varre **apenas as linhas que estão sendo introduzidas**. Um segredo que está no disco mas
  não foi para o index não bloqueia o commit; um que já estava commitado num arquivo tocado
  também não. Para achar esses, use `gitsafety scan` na pasta.
- `benchmarks/bench_hook.py` — mede o custo que o hook impõe ao commit, por diferença
  pareada. Medido: **~0,04 s de overhead, constante** de 1 a 200 arquivos.

## [0.1.0] - 2026-07-27

### Added

- **`gitsafety scan [CAMINHO]`** — varre arquivos e diretórios em busca de chaves de
  acesso da AWS. Imprime `arquivo:linha regra segredo` com o segredo **mascarado por
  padrão**, e sai com `0` (nada encontrado), `1` (segredo encontrado) ou `2` (erro de
  uso, como caminho inexistente). A flag `--show-secrets` revela o valor íntegro.
- Arquivos binários e acima de 1 MB são pulados, e a quantidade de pulos aparece na
  saída — um arquivo não varrido nunca some em silêncio.
- Instalação como comando de console via `pip install -e .`; também funciona por
  `python -m gitsafety`.
- `benchmarks/bench_scan.py` — mede latência de varredura com corpus determinístico.
  Medição inicial: 1.000 arquivos em 0,0145 s (~69.000 arquivos/s) em Python 3.10.
- Integração contínua em matriz Python 3.10 e 3.13, com verificação explícita de que o
  `pytest` instalado está acima da versão com CVE.
- `LICENSE` — MIT.
- README e PRD do produto: CLI em Python instalada via `pipx`, hook de pre-commit com
  um comando, configuração em `.gitsafety.yml` (`ignore` / `allow` / `rules`) e
  cobertura de notebooks Jupyter incluindo saídas de célula salvas.
- `skills/discover-plan-confidence/templates/discover-plan-thresholds.example.txt` —
  fallback que `_resolve_thresholds` já referenciava mas que não existia; sua ausência
  fazia o scorer levantar `FileNotFoundError` em qualquer projeto que adotasse a skill
  sem promover os próprios thresholds.


### Changed

- **Piso de Python elevado de 3.9 para 3.10.** A auditoria de dependências encontrou
  `GHSA-6w46-j5rx-g56g` / `PYSEC-2026-1845` no `pytest` (manipulação vulnerável de
  tmpdir em UNIX), corrigido apenas em 9.0.3 — versão que exige Python >=3.10. Somado a
  isso, o Python 3.9 está sem suporte de segurança desde 2025-10-31. Um produto de
  segurança não declara suporte a interpretador que não recebe mais correção.


### Removed

- Escopo herdado da documentação anterior, que descrevia outro produto: configuração
  TOML com herança, allowlists com condição `AND`/`OR`, regras compostas, entropia de
  Shannon, decoding recursivo, scan de archives, relatórios CSV/JUnit/SARIF/template e
  distribuição via Docker. Motivos por item em `docs/PRD.md` § 10.


### Fixed

- Gate `/discover-plan-confidence` sempre retornava `INVALID`, para qualquer plano.
  `rules/discover-plan-thresholds.txt` estava em formato `KEY = VALUE` enquanto o
  parser do scorer separa por `|`; nenhuma banda era lida e o cálculo de veredito caía
  no default `INVALID`, com `hard_caps_triggered` vazio — estado que o próprio golden
  rule declara impossível. Nenhum teste cobria o parser, por isso o defeito sobreviveu.
  Arquivo convertido para o formato canônico, com testes de regressão em
  `skills/discover-plan-confidence/tests/test_thresholds_parsing.py`.

> Referências de issue/PR serão adicionadas quando o tracker do projeto existir.

