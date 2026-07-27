# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/) · Versionamento: [SemVer](https://semver.org/)

## [Unreleased]

### Fixed

- Gate `/discover-plan-confidence` sempre retornava `INVALID`, para qualquer plano.
  `rules/discover-plan-thresholds.txt` estava em formato `KEY = VALUE` enquanto o
  parser do scorer separa por `|`; nenhuma banda era lida e o cálculo de veredito caía
  no default `INVALID`, com `hard_caps_triggered` vazio — estado que o próprio golden
  rule declara impossível. Nenhum teste cobria o parser, por isso o defeito sobreviveu.
  Arquivo convertido para o formato canônico, com testes de regressão em
  `skills/discover-plan-confidence/tests/test_thresholds_parsing.py`.

### Added

- `skills/discover-plan-confidence/templates/discover-plan-thresholds.example.txt` —
  fallback que `_resolve_thresholds` já referenciava mas que não existia; sua ausência
  fazia o scorer levantar `FileNotFoundError` em qualquer projeto que adotasse a skill
  sem promover os próprios thresholds.

- `LICENSE` — MIT.
- README e PRD do produto: CLI em Python instalada via `pipx`, hook de pre-commit
  com um comando, configuração em `.gitsafety.yml` (`ignore` / `allow` / `rules`) e
  cobertura de notebooks Jupyter incluindo saídas de célula salvas.

### Removed

- Escopo herdado da documentação anterior, que descrevia outro produto: configuração
  TOML com herança, allowlists com condição `AND`/`OR`, regras compostas, entropia de
  Shannon, decoding recursivo, scan de archives, relatórios CSV/JUnit/SARIF/template e
  distribuição via Docker. Motivos por item em `docs/PRD.md` § 10.

> Referências de issue/PR serão adicionadas quando o tracker do projeto existir.
