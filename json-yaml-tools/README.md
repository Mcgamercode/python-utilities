# JSON / YAML Validator, Formatter & Converter

Point it at a config file and get a straight answer: valid or not — and
if not, the **exact line, column, and a snippet with a caret** pointing
at the problem, instead of a bare "invalid JSON" shrug. It also
pretty-prints, minifies, sorts keys, and converts between JSON and
YAML. Point it at a folder with `--check` and it validates every config
in it — the kind of check you run before a deploy, or in CI.

This is tool #8 in the nightly series — a professional utility. JSON
and YAML are the config languages of modern development: Docker Compose
files, GitHub Actions workflows, Kubernetes manifests, app settings.
Every developer has stared at a YAML error that pointed at the wrong
line. This tool points at the right one.

## Install — one command

JSON is standard library. YAML needs one package:

```bash
pip install pyyaml
```

Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\json-yaml-tools
pip install pyyaml
python json_yaml.py config.json
```

**Termux (Android):**

```bash
cd ~/python-tools/json-yaml-tools
pip install pyyaml
python json_yaml.py config.json
```

## What you get

Valid file — a shape summary on stderr, the formatted document on
stdout (so you can redirect it cleanly):

```text
config.json: valid object, 5 top-level keys ['name', 'port', 'debug', 'tags', 'limits']
{
  "name": "demo-app",
  "port": 8080,
  "debug": true,
  ...
}
```

Broken file — the exact spot, with a caret:

```text
bad.json: Invalid JSON — Expecting ',' delimiter (line 4, column 3)
      "debug": true
      ^
```

That missing comma after `"port": 8080` is a two-second fix once you
can *see* it. Without the location, it's a ten-minute stare.

## Useful flags

```bash
# Validate only — no output document, exit 0 if valid, 1 if not
python json_yaml.py config.json --check

# Validate a whole folder of configs (add -r to recurse into subfolders)
python json_yaml.py configs/ --check
python json_yaml.py configs/ --check -r

# Convert YAML to JSON, or JSON to YAML
python json_yaml.py docker-compose.yml --to json
python json_yaml.py settings.json --to yaml

# Compact JSON for sending over the wire, or sorted keys for clean diffs
python json_yaml.py config.json --minify
python json_yaml.py config.json --sort-keys

# 4-space indent, or write the result to a file instead of stdout
python json_yaml.py config.json --indent 4
python json_yaml.py config.json --to yaml -o config.yaml

# Pipe it: read from stdin, write to stdout
cat config.json | python json_yaml.py -

# Rewrite the file in place — only when you ask for it explicitly
python json_yaml.py config.json --in-place
```

Exit codes are CI-friendly: `0` valid, `1` invalid, `2` usage error
(missing file, bad flag, folder without `--check`).

## The rules baked in

- **Read-only by default.** The tool never overwrites your input.
  `--in-place` is the only way it writes back to the same file, and
  you have to type it on purpose.
- **Duplicate keys are errors, not silent overwrites.** `{"a": 1, "a": 3}`
  is flagged in JSON *and* YAML — a duplicate key in a config is almost
  always a copy/paste bug, and both parsers normally swallow it quietly.
- **YAML is parsed with `safe_load` only** — never `yaml.load()` — so a
  config file can never execute code.
- **YAML merge keys (`<<: *anchor`) work**, and multi-document YAML
  (`---` separated) converts to a JSON array.
- **stdout stays a clean document.** The summary line goes to stderr,
  so `python json_yaml.py config.json > out.json` contains only JSON —
  safe to pipe into the next tool in a chain.
- **Extensionless files work**: format is guessed from the extension,
  then from the content (`{` or `[` means JSON), and `--format` forces
  it when both guesses are wrong.

## The libraries lesson — 2 core libraries, 1 install

| Library | What it does here |
|---|---|
| `json` (stdlib) | `json.loads` / `json.dumps` — parsing, pretty-printing, minifying, and sorting keys. Its `JSONDecodeError` already carries line and column, which is what makes the exact error location possible. The `object_pairs_hook` argument is how duplicate keys get caught. |
| `yaml` (PyYAML, `pip install pyyaml`) | `yaml.safe_load` / `safe_dump` — the YAML side. Subclassing `SafeLoader` is how duplicate-key detection and merge-key support are added without giving up safe parsing. |
| `argparse` (stdlib) | Turns the flags (`--to`, `--check`, `--minify`, `--in-place`…) into a real CLI with `--help` — no manual string-splitting. |
| `pathlib` (stdlib) | Finds files and folders on Windows *and* Android with the same code — no hardcoded `C:\` or `/home/` paths. |

Two libraries do the whole job, and one of them ships with Python.
That's the point of the series: the toolbox is already installed.

## What it replaces — and the savings

**JSONBuddy Standard** — a desktop JSON editor and validator: syntax
checking, validation, formatting, and JSON/YAML conversion tools.
Verified price: **$39.00 one-time**, single-user perpetual license
(json-buddy.com purchase page and SourceForge listing both show
"$39 one-time payment", checked Nov 11, 2026).

| | Paid | This tool |
|---|---|---|
| Price | $39 one-time | $0 |
| Validate JSON with exact error location | yes | yes |
| Validate YAML with exact error location | yes | yes |
| Pretty-print / minify / sort keys | yes | yes |
| Convert JSON ↔ YAML | yes | yes |
| Batch-check a folder of configs, CI exit codes | yes | yes |
| Duplicate-key detection | yes | yes |
| GUI grid editor, JSON Schema debugger, VS extension | yes | no — CLI only |

**Savings: $39.00 one-time.** It won't give you the visual grid
editor or the schema debugger — that's the part you're paying for
there — but for the core job, *is this config valid, where is it
broken, and give me the clean version*, it does the job from any
terminal, including a phone.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$129–144
one-time + ~$523.74/year in subscriptions avoided.
