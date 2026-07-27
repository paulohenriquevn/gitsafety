# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/) · Versionamento: [SemVer](https://semver.org/)

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

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

