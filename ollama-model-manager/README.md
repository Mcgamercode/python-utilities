# Ollama Model Manager

One command to manage the local LLM models on any Ollama server — list
what's installed and how much disk it eats, see what's loaded in memory
right now, pull a new model with a live progress bar, delete one safely,
or inspect a model's details. It talks to Ollama's local HTTP API
(`http://localhost:11434`), so it works against any host: your Windows
box, your WSL Ubuntu install, or another machine on your LAN.

This is tool #13 in the nightly series — a professional utility. Anyone
running local models (devs, ML engineers, red-teamers) juggles models
constantly: which 7B is still on disk, what's eating 13 GB, is the judge
model still loaded in VRAM? Ollama's own CLI answers each question one
command at a time and only on the machine you're sitting at. This gives
you one table for all of it, from anywhere on your network.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.
You do need an Ollama server running somewhere to manage — install
Ollama from [ollama.com](https://ollama.com) if you haven't yet.

## Run it

**Windows PowerShell** (talks to Ollama on the same machine):

```powershell
cd ~\python-tools\ollama-model-manager
python ollama_manager.py list
```

**Termux (Android)** — Ollama runs on your laptop/WSL box, so point
the tool at it over your home Wi-Fi:

```bash
cd ~/python-tools/ollama-model-manager
python ollama_manager.py --host http://192.168.68.126:11434 list
```

No subcommand means `list` — the thing you want most often.

## Useful flags

```bash
python ollama_manager.py status                    # is the server up? what version?
python ollama_manager.py list --sort size          # biggest models first
python ollama_manager.py list --json               # raw JSON — pipe it to jq or a script
python ollama_manager.py running                   # models loaded in memory (alias: ps)
python ollama_manager.py pull qwen2.5-coder:7b     # download with a live progress bar
python ollama_manager.py show qwen3.5:4b           # format, family, size, quant, template
python ollama_manager.py copy qwen2.5-coder:7b my-coder
python ollama_manager.py remove dolphin-phi        # asks first — see safety note
python ollama_manager.py remove dolphin-phi --yes  # skip the prompt (scripts only)
```

Point it at another machine permanently with the environment variable:

```powershell
$env:OLLAMA_HOST = "http://192.168.68.126:11434"   # PowerShell
export OLLAMA_HOST=http://192.168.68.126:11434     # Termux / bash
```

`--host` on the command line beats the environment variable.

## What it handles

- `status` — server up/down, version, model count, total disk, loaded count
- `list` — installed models with size and last-modified date, sorted by
  name, size, or date; total disk usage at the bottom
- `running` — models loaded in memory, VRAM used, family, and when
  Ollama will unload each one
- `pull` — streams Ollama's download progress as a live percentage
  with MB downloaded / MB total
- `remove` — deletes a model, after printing its name and size and
  asking you to confirm
- `show` — format, family, parameter size, quantization level, runtime
  parameters, prompt template, and Modelfile
- `copy` — duplicate a model under a new name (handy for a tuned copy
  you don't want to lose)
- `--json` on `list` and `running` for scripting

## What it does NOT do (on purpose)

- It never deletes a model without asking, unless you pass `--yes`.
  And if stdin isn't a terminal (you're piping it into a script) it
  refuses instead of guessing — deletes never happen silently.
- It never touches your files and never uploads anything. It only
  speaks to the Ollama API on the host you point it at.
- It doesn't chat with models — that's `ollama run <model>` or the
  Ollama desktop app. This is the manager, not the chat client.
- It doesn't secure your server. The Ollama API has no password: anyone
  who can reach the host can pull and delete models. Only point
  `--host` at machines you trust, on your own network. Never expose
  port 11434 to the internet.

## The libraries lesson

Four standard-library modules do all the work — no third-party
packages to install or keep updated:

- **`urllib.request`** — the HTTP client built into Python. `GET` for
  lists, `POST` with a JSON body for pull/show/copy, `DELETE` for
  remove. The same module can talk to any REST API: GitHub, Home
  Assistant, your own servers. If you can read these calls, you can
  script any web service without reaching for `requests`.
- **`json`** — every Ollama reply is JSON, and every request body is
  JSON too. `json.loads` turns a reply into a dict; `json.dumps`
  builds a request. The pull progress bar works by reading the
  streaming reply one JSON line at a time.
- **`argparse`** — turns the subcommands (`list`, `pull`, `remove`…)
  and flags (`--host`, `--sort`, `--json`, `--yes`) into a real CLI
  with `--help` for free, including the `remove`/`rm` and
  `running`/`ps` aliases.
- **`datetime` + `os`** — `datetime.fromisoformat` turns Ollama's
  timestamps into readable dates, and `os.environ` reads
  `OLLAMA_HOST` so you configure the server once instead of typing
  `--host` every time.

## Paid equivalent — verified, and the honest answer

There is no direct paid equivalent to claim here, and the log says so
plainly. Ollama itself is free and MIT-licensed — local model use costs
$0, verified against Ollama's own pricing page and multiple
Oct–Nov 2026 writeups. Its paid tiers (Pro $20/mo, Max $100/mo) only
buy *cloud* models you run on Ollama's servers, not local management,
so this tool doesn't replace them. The closest paid product in the
same category is **Ollamac Pro**, a native Mac Ollama client app at
**$49 one-time for one Mac / $99 for three** (per TrustMRR's
Stripe-verified listing, Oct 2026) — but it's Mac-only and a GUI chat
client, not a cross-platform CLI manager, so it isn't a like-for-like
replacement either. What this tool saves is **time**: auditing models
across two machines by hand — `ollama list`, `ollama ps`, raw `curl`
calls, and doing the size math yourself — is 10–15 minutes of fiddly
work every time; this is one command.

## Savings

| Tool | Replaces | Price | You pay |
|---|---|---|---|
| Ollama model manager | — (no paid equivalent; see above) | Time saved, ~10–15 min per audit | $0 |

Running series total after this tool: **~$336–351 one-time** +
**~$571.62/year** avoided (see `../SAVINGS_LOG.md`).
