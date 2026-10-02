# gitsafety

**Stops you from committing an API key.**

Install it once, and from then on `git commit` warns you before a credential leaves your
machine. Works in git repositories, in loose folders and in Jupyter notebooks.

> **Status:** pre-1.0. Published on PyPI and working — install it and use it. `1.0.0` is
> reserved for after sustained use in real work. Tests and review prove **correctness**;
> `1.0.0` should mean **use**, and those are different things.

> **Language note:** the CLI currently prints its messages in Portuguese. The output samples
> below are verbatim.

---

## Getting started — 3 steps

You need Python 3.10 or newer. No Docker, nothing to compile, nothing to run in the background.

### 1. Install

```bash
pipx install gitsafety
```

If you don't have `pipx`: `python3 -m pip install --user pipx && python3 -m pipx ensurepath`.

<details>
<summary>Prefer <code>pip</code> in a virtual environment? Read this first.</summary>

`pip install gitsafety` works, but the hook calls `gitsafety` from the PATH **at commit
time**. If the virtual environment is not active at that moment, **every commit fails** with
`gitsafety: not found`. `pipx` keeps the command available at all times.

We found this out by installing it in our own repository — it is recorded in
[`knowledge-base/dogfood/`](knowledge-base/dogfood/).
</details>

### 2. Turn it on in your project

Inside the repository folder, just once:

```bash
gitsafety install
```

```console
  hook instalado em /home/ana/meu-projeto/.git/hooks/pre-commit
  A partir de agora o commit é verificado.
  Emergência: git commit --no-verify
```

### 3. Work as usual

There is no step 4. `git commit` is still `git commit` — the difference only shows up when
there is a credential in what you are committing:

```console
$ git commit -m "adiciona cliente S3"

  app.py:6   aws-access-key-id   AKIA••••••••••••MPLE

  1 segredo encontrado.
  Revogue a chave no provedor antes de qualquer outra coisa.
```

The commit did **not** happen. Take the key out of the code (use an environment variable, a
vault, whatever your team uses), commit again, and you're done.

> **Why "revoke the key" and not "delete the line".** If the key has ever left your machine,
> deleting it from the code does not deactivate it. Whoever copied it still has it. Revoking it
> at the provider is the only action that actually fixes it — the rest is cleanup.

---

## I committed a key before installing. Now what?

The hook protects you from now on. To look back:

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

It shows **when the key came in and who added it** — that is what decides the urgency. And it
works even if the file has already been deleted: git history remembers, and so does everyone
who cloned the repository.

---

## The three commands, and when to use each

| Command | What it looks at | When you use it |
|---|---|---|
| `gitsafety install` | — | Once per repository, at the start |
| *(the hook, on its own)* | what you are committing | Automatically, on every `git commit` |
| `gitsafety scan` | the files in the folder right now | Before opening a PR, or out of curiosity |
| `gitsafety scan --history` | everything ever committed | When adopting it in an existing project |

Emergency: `git commit --no-verify` bypasses the hook. It exists because blocking someone
with no way out makes them uninstall the tool.

This README is the user guide. The full CLI reference is in
[`docs/API.md`](docs/API.md).

---

## Why it doesn't get in your way

The hook checks **only the lines you are introducing** — not the whole repository, and not
even the whole file. For text content, measured: the commit gets **~0.04 s** slower,
regardless of whether it touches 1 or 200 files ([benchmark](benchmarks/bench_hook.py)).

Committing **binaries** is another story: the hook reads the content so that a secret cannot
slip through disguised as a binary file, and that has a cost. Measured: 30 MB of binaries in
the same commit take ~4.5 s. It is not the common case — but if your first commit with the
tool includes an assets folder, it is good to know. Put the path under `ignore:` if it will
never contain a credential.

This has a consequence worth knowing: if a file **already had** a committed secret and you
edit another line of it, the hook does not complain. That is deliberate — otherwise, adopting
the tool in a repository with history would block every commit until someone cleaned up the
past. To find what is already there, run `gitsafety scan` on the whole folder.

And it only fires on a **known credential pattern** — `AKIA` followed by 16 uppercase
characters is an AWS key; there is no other reading. No "looks random" heuristics, which is
what fills reports with false positives and makes the team turn the tool off in the second
week.

The only rule that looks at **context** instead of the value is the generic one: it requires
the variable name (`password`, `api_key`, `aws_secret_access_key`…), the assignment operator,
and a value of 20+ characters **with a digit and a letter**. That is what separates a credential
from a code identifier — `secret_key = settings.SECRET_KEY` does not match,
`token = os.environ[...]` does not match. Measured: **zero** false positives in 72,570 lines of
code from the reference projects, and **3** in a larger corpus of 1.3 million lines — their
class is described right below.

It has a boundary, and it is worth knowing where. It does **not** catch: a value on another line,
a value built by concatenation, a password with a symbol in its first 20 characters
(`"S3nh4@Sup3r..."`), a letters-only password, and names it does not know (`pwd`,
`credential`). It **sometimes catches too much:** a Python type annotation has the same shape as
a secret in YAML, and the rule cannot tell the two apart <!-- gitsafety: allow -->. That was 3
occurrences in 1.3 million lines of real code. For those, use `allow:` or `ignore:`.

---

## What it detects

With zero configuration:

| Category | Rules | Examples |
|---|---|---|
| Cloud | 8 | AWS, Google Cloud, Azure, DigitalOcean, Heroku, Cloudflare |
| Git / packages | 11 | GitHub (`ghp_`, `github_pat_`, `gho_`, `ghs_`, `ghr_`), GitLab, npm, PyPI, RubyGems, crates.io |
| AI and data | 6 | OpenAI (`sk-`), Anthropic (`sk-ant-`), Hugging Face, Cohere, Replicate, W&B |
| Payments and SaaS | 19 | Stripe, Twilio, SendGrid, Slack, Sentry, Shopify, Atlassian, Linear, JWT |
| Private keys | 4 | PEM blocks, PuTTY, encrypted PKCS#8, age |
| Databases | 5 | Connection strings with a password: PostgreSQL, MySQL, MongoDB, Redis, AMQP |
| Generic | 1 | A credential assigned to a revealingly named variable: `aws_secret_access_key`, `password`, `api_key`, `token`, `client_secret`… |

**54 patterns in total.** Each one carries its own match and non-match examples, verified on
every run of the test suite.

Anything specific to your team goes in the YAML — see below.

### Jupyter notebooks

`.ipynb` is treated as a first-class case: gitsafety reads the notebook JSON and checks
**the cell code and also the saved outputs**. That is where keys leak most often — you delete
the cell, but the `print(os.environ)` from three runs ago is still stored in the file that is
about to be committed.

A finding points to the **cell**, not to the JSON line:

```
analise.ipynb :: célula 4 (saída):1   postgres-connection-string   post•••••••••.com
```

A notebook open in Jupyter has no line 50, so reporting the file line would not help anyone
find the secret. Outputs from `print`, from cell results and from error tracebacks are all
checked — the traceback of a failed authenticated call often holds the entire credential.

A corrupted or truncated notebook does not break the scan: it is read again as plain text,
because a file the parser rejects can still contain the key.

### History

The hook stops the key from **getting in**. To find out whether it already got in before:

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

The commit shown is the one that **introduced** it — "how long has this key been exposed?" is
the question that decides the urgency. Deleting the file today does not fix it: the object
stays in the history of everyone who has already cloned the repository.

A secret that appears in several commits becomes **one** finding, with the count next to it
when it was reintroduced after being removed.

The cost is proportional to the **lines** in the history, not to the number of commits. On the
gitsafety repository itself — 74 commits, 77 thousand lines added — it takes about 2.5 seconds
([benchmark](benchmarks/bench_history.py)). It is a command to run now and then, not on every
commit; that is what the hook is for.

**What it does not see — and tells you.** If you rewrote history with `git reset`, `rebase` or
`commit --amend`, the old commit is no longer referenced and `--history` cannot reach it. It
says so instead of letting you conclude everything is clean:

```
Nenhum segredo encontrado.

Atenção: 1 commit reescrito não foi verificado.
Se foi para remover uma chave, revogue-a: reescrever não desfaz a exposição.
```

The object stays in your local repository for about 90 days, recoverable through the reflog.
And rewriting history has never undone an exposure: **revoking the key at the provider** is the
only action that fixes it.

---

## Configuration

Optional. With no file at all, the built-in patterns apply. To adjust, create a
`.gitsafety.yml` at the root of the repository:

```yaml
# .gitsafety.yml — all three keys are optional

# Paths that are never even opened (glob)
ignore:
  - "tests/fixtures/**"
  - "docs/examples/**"

# Known, harmless values (exact text or regex)
allow:
  - "AKIAIOSFODNN7EXAMPLE"    # example key from the AWS documentation
  - "sk-test-.*"              # Stripe test-environment keys

# Your own patterns
rules:
  - id: internal-key
    pattern: "INTERNAL_KEY_[A-Za-z0-9]{20}"
  - id: customer-token
    pattern: "cli_[a-f0-9]{32}"
```

Three top-level keys — `ignore`, `allow`, `rules` — and nothing else. No config inheritance,
no `condition: AND/OR`, no composite rules.

**A misspelled key is not ignored.** `ignroe:` stops the scan and suggests `ignore:` —
silence would cost you a debugging session discovering that the config was never read.

**Your patterns are checked before running.** An invalid regex becomes an error naming the
rule. A regex that could hang the check in the middle of a commit — such as
`(a{1,50}){1,50}` — is rejected at load time, with an explanation. It is your commit that
would be hanging.

Invalid YAML or a regex that does not compile **stops the scan with an error pointing to the
line** (exit code 2). They are never silently ignored.

Another file: `gitsafety scan --config path/config.yml`.

### Want to catch loose passwords too?

It is off by default because it produces false positives. If your team accepts the trade-off,
paste this under `rules:`:

```yaml
  - id: hardcoded-password
    pattern: "(?i)(password|secret|token|api_key)\\s*[=:]\\s*['\"][^'\"]{8,}['\"]"
```

---

## Ignoring a finding

From the most local to the broadest:

**1. On the line** — for a test secret committed on purpose:

```python
API_KEY = "sk-test-4eC39HqLyjWDarjtT1zdp7dc"  # gitsafety: allow
```

**2. By value** — in `allow:`, when the same value shows up in several files.

**3. By path** — in `ignore:`, when the whole folder is irrelevant.

---

## About the hook

`gitsafety install` writes `.git/hooks/pre-commit`, which calls
`gitsafety scan --staged`. It does not depend on the `pre-commit` framework or on any
other tool.

If the repository already has a `pre-commit` hook, the command **refuses and tells you**
instead of overwriting your hook — it shows you the line to add to the existing one.

---

## In CI

Any runner with Python. In GitHub Actions:

```yaml
- name: Check for secrets
  run: |
    pipx install gitsafety
    gitsafety scan --history
```

Exit code 1 when it finds a secret, which already fails the job.

---

## Output and exit codes

Secrets are **masked by default** — the report must not become the next leak.
`--show-secrets` shows the full value when you really need it.

| Exit code | Meaning |
|---|---|
| `0` | Nothing found |
| `1` | Secret found |
| `2` | Error (invalid config, path does not exist, not a git repository) |

---

## All flags

```
gitsafety install              installs the pre-commit hook
gitsafety scan [PATH]          checks files
  --staged                     only what is in the git index
  --history                    the git history, instead of the disk
  --show-secrets               shows the full secret
  --config PATH                config file (default: .gitsafety.yml)
gitsafety --version            shows the installed version
```

**Four flags on `scan`, and that is the ceiling.** If you miss a fifth one, the case most likely
belongs in `.gitsafety.yml` — a flag is interface everyone carries forever; configuration is
a choice made by whoever needs it.

`--staged` and `--history` are targets and therefore mutually exclusive: the first looks at
what you are committing, the second at what has already been committed, and with neither it
looks at the disk.

This list is the whole list. `gitsafety scan --help` shows exactly these flags, and a test in
the suite compares the two in both directions on every run — a documented flag that does not
exist, and a flag that exists without documentation.

The full contract — every exit code, every output field, every configuration key and what
happens when it is wrong — is in [`docs/API.md`](docs/API.md).

---

## What gitsafety does **not** do

Out of scope on purpose — each item is complexity nobody asked for:

- **It does not remove the secret from history.** Detecting and rewriting history are
  different problems; rewriting is destructive and belongs to `git filter-repo` / BFG.
- **It is not a password vault** and does not rotate credentials.
- **It does not scan inside `.zip` / `.tar.gz`** nor decode base64 and hex.
- **It does not use entropy**, config inheritance, composite rules or `condition AND/OR`.
- **It does not emit CSV, JUnit, SARIF or templates** — human output and an exit code.
- **It does not run as a service** and has no Docker image.

Need something from this list? [gitleaks](https://github.com/gitleaks/gitleaks) and
[trufflehog](https://github.com/trufflesecurity/trufflehog) cover that territory —
that is the honest recommendation.

---

## Rule number one

A detected secret is a **compromised** secret. Deleting the line, redoing the commit or
adding it to `allow:` does not undo the exposure.

1. **Revoke and rotate the key** at the provider.
2. Only then clean up the code.

gitsafety finds it; closing the door is up to you.

---

## License

Original implementation, under the MIT license (see `LICENSE`).

The pre-commit hook approach with a catalog of known patterns is established practice in the
field — [gitleaks](https://github.com/gitleaks/gitleaks) is the most complete reference. No
code was copied.
