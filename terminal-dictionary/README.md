# term-dict — a working dictionary for your terminal

Leave it open while you work or watch TV. Type a word, get definitions,
roots/origin, pronunciation (IPA, plus spoken audio when available) and
example sentences. Acronyms and abbreviations work too — `API`, `JSON`,
`SQLi`, `SIEM`.

## Run it

```bash
python dict.py              # open it and leave it running
python dict.py serendipity  # one-shot lookup, then exit
python dict.py --ai         # REPL with local-AI extras on
```

Stdlib only — no `pip install` needed. Works on Termux/Android, Windows
PowerShell, WSL and Linux. Copy the single file anywhere and run it.

## REPL commands

| Command | What it does |
|---|---|
| `!help` | Show commands |
| `!history` | Your last 20 lookups |
| `!play` | Hear the last word (needs mpv, ffplay or cvlc) |
| `!say` | Speak the last word (needs espeak) |
| `!ai` | Toggle local-AI extras |
| `!clear` | Clear the screen |
| `!quit` | Exit (Ctrl-D works too) |

Lookups are saved to `~/.terminal_dict_history.json`.

## Where the answers come from

| Need | Source |
|---|---|
| Definitions, phonetics, examples | Free Dictionary API (dictionaryapi.dev — free, no key) |
| Roots / origin | Wiktionary Etymology section, markup stripped |
| Tech acronyms | Built-in map of ~70 terms, plain-English |
| Offline fallback | NLTK WordNet, when installed |
| Spoken pronunciation | Audio clip from the dictionary API, or espeak |

## Do you need a local AI? (the honest answer)

**No, not for reliable results.** A dictionary API is the ground truth for
definitions — it returns verified entries. A local model is *better* at two
things only: writing a natural example sentence, and explaining an origin in
plain English. But a model can also invent a confident-sounding wrong
definition, which is exactly what you don't want from a dictionary.

So this tool is dictionary-first. Local AI is an optional enrichment layer:
run with `--ai` (or type `!ai`) and, when Ollama is reachable on
`localhost:11434`, it asks a local model for one extra example sentence and
one plain-English origin note. That output is labeled AI-generated, and it
never replaces the dictionary entry. If Ollama isn't running, the tool just
works without it.

If you only want one of the two: dictionary-only is the reliable route;
AI-only would be the wrong tool for a dictionary.

## Tips

- Keep it open in a `tmux` pane or a second Termux session while you work.
- Words it can't find: check the spelling, or try the singular / base form.
- Acronyms are matched case-insensitively, so `api` and `API` both work.
- Set `OLLAMA_HOST` if your Ollama lives somewhere other than localhost.
