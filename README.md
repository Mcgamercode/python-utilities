# python-utilities

A growing collection of small, professional Python tools — each one a single
job done well, each with its own README. Most are stdlib-only, cross-platform
(Windows PowerShell and Termux/Android), and read-only or dry-run by default
where that matters. No accounts, no cloud, no installers.

Built as a nightly series (Nov 5–18, 2026): one tool a night, tested before
it ships. The last few tools land as the series finishes.

## The tools

| Tool | What it does | Replaces |
| --- | --- | --- |
| [duplicate-finder](duplicate-finder/) | Finds byte-identical files, moves extras to a review folder, writes a restore script. Never deletes. | Duplicate Cleaner Pro (~$40–55 one-time) |
| [stale-listing-analyzer](stale-listing-analyzer/) | Reads a Marketplace inventory DB and flags stale listings: renew, cut, or pull. | Vendoo Starter ($14.99/mo) |
| [vikings-bet-tracker](vikings-bet-tracker/) | Log a prediction with a percentage before kickoff, then score it after the game. | Action Network PRO ($119.99/yr) |
| [csv-profiler](csv-profiler/) | Instant stats on any CSV: types, nulls, uniques, numeric distributions. | HQ Data Profiler ($9.99/mo) |
| [log-analyzer](log-analyzer/) | Parse app/server logs: errors by type, top IPs, busiest hours, timeline. | Papertrail ($7/mo) |
| [disk-usage-analyzer](disk-usage-analyzer/) | What's eating the drive: biggest files/folders, space by type. Read-only. | DiskSavvy Pro ($50 one-time) |
| [url-safety-checker](url-safety-checker/) | Expands short links, follows redirects, flags phishing patterns in the final domain. | URLCheck ($19.99/yr) |
| [json-yaml-tools](json-yaml-tools/) | Validate, pretty-print, and convert JSON/YAML, with exact error line and column. | JSONBuddy Standard ($39 one-time) |
| [bulk-file-renamer](bulk-file-renamer/) | Rename by pattern (find/replace, regex, numbering, date prefix). Dry-run default, undo log. | Bulk Rename Utility ($92.95 one-time) |
| [sqlite-query-helper](sqlite-query-helper/) | Query any SQLite DB, export to CSV/JSON, schema summary. Read-only by default. | TablePlus Basic ($99 one-time) |
| [password-generator-audit](password-generator-audit/) | Random passwords and Diceware passphrases; score one password; audit a list for weak/common/reused entries. | 1Password Individual ($3.99/mo) |
| [markdown-to-html](markdown-to-html/) | Convert any .md file to clean standalone HTML: TOC, tables, task lists, code blocks. Stdlib only. | Typora ($14.99 one-time) |
| [ollama-model-manager](ollama-model-manager/) | Manage local Ollama models: list, status, pull, remove, show, copy. Stdlib only. | — (saves ~10–15 min per model audit) |
| [duplicate-photo-finder](duplicate-photo-finder/) | Finds near-duplicate photos by perceptual hash: resized, recompressed, brightened copies. Report-only default, move-to-review + restore. Needs Pillow. | Duplicate Photo Cleaner ($39.95) |
| [terminal-dictionary](terminal-dictionary/) | A working dictionary in the terminal: definitions, roots, IPA, examples. | — |
| [termux-cleaner](termux-cleaner/) | Find what's eating Termux storage; clear the safe caches. Dry-run default. | — |
| [sql-injection-lab](sql-injection-lab/) | Local learning lab: vulnerable vs. safe logins against a real SQLite DB. Localhost only. | — |
| [mini-redteam-lab](mini-redteam-lab/) | A tiny red-team eval lab: one fake target, one rule, five tests, one visible bypass. | — |
| [ollama-redteam-harness](ollama-redteam-harness/) | Three-role eval harness (generator / target / judge) against local Ollama models. | — |

## Running a tool

```bash
cd <tool-folder>
python <tool>.py --help
```

Every tool has its own README with exact commands for PowerShell and Termux.
Python 3 is the only requirement for most tools; `json-yaml-tools` needs
PyYAML (`pip install pyyaml`), `duplicate-photo-finder` needs Pillow
(`pip install pillow`), and `sql-injection-lab` needs Flask for the
demo app. `ollama-redteam-harness` needs a local Ollama server with the
models listed in its README.

## What this replaces

| | |
| --- | --- |
| One-time purchases avoided | ~$376–391 |
| Annual subscriptions avoided | ~$571.62/yr |

Prices verified against the vendors' own pages when each tool was built
(sources in each tool's README). See [SAVINGS_LOG.md](SAVINGS_LOG.md) for
the running tally.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, break it, improve it.
