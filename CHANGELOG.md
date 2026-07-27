# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/) · Versionamento: [SemVer](https://semver.org/)

## [Unreleased]

### Added

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
