# term-lookup — plain-English tech glossary + flashcards

**What it is:** you type a tech word you don't know yet, and it answers in plain
English: what it means, one real example from code or logs, and one thing to
watch out for. Every card you look at is saved to a local glossary, so your
collection grows as you learn. No account, no internet, no cost, stdlib only.

**Who it is for:** a self-taught builder with no formal CS/IT schooling who
keeps tripping over jargon in code, logs, and tool output — and wants the words
to become second nature instead of a wall.

## The learning loop (how the connections form)

1. **Look a term up** — you get a card, not a dictionary definition.
2. **Follow a "See also" link** — every card points at 2–3 related terms.
   One lookup leads to the next idea. That chain is the neural connection.
3. **Quiz yourself** — `--quiz` shows the plain meaning and asks for the term.
   Your weakest terms come first, and your score is remembered, so you can
   watch yourself get better instead of guessing whether you are.
4. **Walk a topic** — `--learn python` goes card by card through one topic
   at your pace. `--today` gives you one new term a day.

## Install

```powershell
# Windows PowerShell
python term_lookup.py regex --context logs
```

```bash
# Linux / WSL / Termux
python3 term_lookup.py regex --context logs
```

No packages to install. Your glossary lives at
`~/.local/share/term_lookup/glossary.json` (same place as v1, so your old
glossary still works).

## Usage

```bash
# Look up a term (saves it to your glossary)
python3 term_lookup.py regex --context logs

# Browse instead of guessing
python3 term_lookup.py --categories        # topics + counts
python3 term_lookup.py --category logs      # every term in one topic
python3 term_lookup.py --all                # the whole deck, grouped
python3 term_lookup.py --search output      # find terms by keyword

# Learn
python3 term_lookup.py --quiz               # 5 flashcards, weakest first
python3 term_lookup.py --quiz 10            # 10 rounds
python3 term_lookup.py --learn python       # walk the Python topic card by card
python3 term_lookup.py --learn              # walk the whole deck
python3 term_lookup.py --today              # one new term a day
python3 term_lookup.py --random             # a surprise card

# Your own words
python3 term_lookup.py --add "my term"      # write your own card, it sticks better
python3 term_lookup.py --list               # everything you have saved
python3 term_lookup.py --stats              # size, quiz score, weakest terms

# Take it with you
python3 term_lookup.py --export md          # term-glossary.md study sheet
python3 term_lookup.py --export html        # term-glossary.html, phone-friendly

# Interactive mode (no term given): type terms, or :quiz :random :today :list :stats :help :quit
python3 term_lookup.py

# Plain output for scripts (the old v1 card format)
python3 term_lookup.py regex --plain

# No colour / ASCII boxes (old terminals, piped output)
python3 term_lookup.py regex --no-color
python3 term_lookup.py regex --ascii
```

## The Ollama hookup — new terms write themselves

When a term has no built-in card, `--ollama` asks your **local** Ollama model
to write one on the spot. Nothing leaves your machine.

```bash
# Ollama must be running first (in WSL, or wherever yours lives):
ollama serve

# Then any unknown term gets a card written by your local model:
python3 term_lookup.py frobnicate --ollama
python3 term_lookup.py "rate limit" --ollama --ollama-model qwen3.5:4b
```

Defaults: host `http://localhost:11434`, model `qwen3.5:4b` (the fast one) or
whatever `OLLAMA_MODEL` is set to. If Ollama is not running, you get the
normal "no card yet" note instead of an error — nothing crashes.

Ollama-written cards are saved with `source: ollama`, so you can tell them
apart from the built-ins and your own notes. Read them once with a sceptical
eye: a small local model can get a detail wrong, and your own check is the
real learning.

## The deck — 88 built-in terms, 9 topics

| Topic | Terms | What's in it |
|---|---|---|
| Python | 18 | variable, function, argument, parameter, return value, loop, list, dictionary, string, boolean, class, object, method, module, import, exception, virtual environment, pip |
| Terminal & CLI | 12 | cli, flag, stdin, stdout, stderr, pipe, shell, environment variable, PATH, working directory, absolute path, exit code |
| Logs | 7 | regex, parse, timestamp, log level, grep, stack trace, tail |
| Networking | 14 | IP address, port, localhost, DNS, HTTP, status code, request, response, header, TCP, SSH, server, client, API |
| Git & GitHub | 8 | repository, commit, branch, merge, pull request, clone, push, remote |
| Security | 10 | vulnerability, exploit, payload, hash, encryption, authentication, authorization, token, SQL injection, brute force |
| Data | 7 | CSV, JSON, YAML, database, query, SQLite, schema |
| Dev concepts | 8 | algorithm, library, framework, dependency, debug, refactor, syntax, cache |
| Files | 4 | file path, extension, checksum, encoding |

Every card has a **plain meaning**, a **real example** (mostly from this repo's
own tools — log-analyzer, csv-profiler, sqlite-query-helper, PocketRecon,
pentest-ops, the HTB path), a **watch out**, and **see also** links.

## Glossary file

`~/.local/share/term_lookup/glossary.json` — one JSON object per term:

```json
{
  "regex": {
    "term": "regex",
    "context": "logs",
    "plain": "A pattern rule that searches...",
    "example": "Collapsing 'timeout after 5s'...",
    "watch_out": "One wrong symbol can match too much...",
    "category": "logs",
    "related": ["parse", "grep", "string"],
    "source": "built-in",
    "updated_at": "2026-11-18T20:30:00+00:00",
    "stats": {"lookups": 3, "quiz_seen": 1, "quiz_correct": 1}
  }
}
```

v1 glossaries load fine — missing fields are filled in with defaults.

## Replaces

Quizlet Plus (flashcards + study sets) — **$35.99/year** ($2.99/mo billed
annually; $7.99/mo month-to-month, verified Nov 18, 2026 from Quizlet's own
upgrade page via multiple 2026 pricing roundups). This tool does the glossary
+ flashcards job for $0, offline, with terms written for a builder reading
real code and logs.

## Files

- `term_lookup.py` — the whole tool, stdlib only, ~1,440 lines
- `README.md` — this file
