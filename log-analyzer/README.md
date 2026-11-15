# Log File Analyzer

Point it at a server or app log and get a plain-English summary in
seconds: total lines, time range, requests by status-code class (2xx /
3xx / 4xx / 5xx), errors grouped by type, top IPs, top requested
paths, busiest hours, and a per-hour timeline.

This is tool #5 in the nightly series — and the second of the
**professional** tools. Reading logs is the first thing any sysadmin,
IT pro, or backend developer does when something breaks, and the first
thing you do is ask the same questions every time: *what's erroring,
who's hitting us, and when did it start?* This answers all three
without opening a 200 MB file in a text editor.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\log-analyzer
python log_analyzer.py C:\inetpub\logs\access.log
```

**Termux (Android):**

```bash
cd ~/python-tools/log-analyzer
python log_analyzer.py access.log
```

That's it. One file, one command. Format is auto-detected.

## What you get

```text
FILE: access.log  (apache format)
Lines: 10  parsed: 9  unparsed: 1
Time range: 2026-11-08 09:12:03+00:00  to  2026-11-08 14:48:00+00:00

== Status codes ==
  2xx: 4 (44.4%) ##############################
  3xx: 1 (11.1%) ########
  4xx: 3 (33.3%) ######################
  5xx: 1 (11.1%) ########
  most common codes: 200 x3, 404 x3, 201 x1, 500 x1, 304 x1
  total bytes served: 23.7 KB

== Top 10 IPs ==
  203.0.113.7: 5
  198.51.100.23: 3

== Top 10 paths ==
  /index.html: 2
  /admin/login: 1
  /wp-admin/: 1

== Top 10 errors ==
  1x  404 GET /admin/login
  1x  500 GET /api/orders/#

== Busiest hours (all parsed lines) ==
  09:00        5  ##############################
  10:00        2  ############
  14:00        2  ############
```

For app logs it looks like this instead:

```text
FILE: app.log  (generic format)
Lines: 12  parsed: 12  unparsed: 0

== Severity levels ==
  INFO: 6
  WARN: 2
  ERROR: 3
  CRITICAL: 1

== Top 10 errors ==
  3x  db.py: failed to connect (timeout after #s)
  1x  worker.py: out of memory, restarting worker #
```

## Formats it understands

| Format | Example line |
|---|---|
| Apache / Nginx combined or common log | `203.0.113.7 - - [08/Nov/2026:09:12:03 +0000] "GET /index.html HTTP/1.1" 200 5123` |
| App log (ISO timestamp + severity) | `2026-11-08 09:11:22 ERROR db.py: failed to connect (timeout after 5s)` |
| Syslog-style | `Nov  8 10:15:33 myhost sshd[1234]: Failed password for root ...` |

Auto-detection sniffs the first 50 lines. If it guesses wrong, force
it: `--format apache` or `--format generic`.

## Useful flags

```bash
# Just the errors — what broke, nothing else
python log_analyzer.py access.log --errors-only

# More entries in the top-N lists
python log_analyzer.py access.log --top 20

# Machine-readable copy for a dashboard or a follow-up script
python log_analyzer.py access.log --json report.json
```

## The rules baked in

- **Read-only.** The tool only reads the log you point it at. It never
  writes to it, never rotates it, never deletes anything — your logs
  stay exactly as they were.
- **Errors are grouped, not listed.** `failed to connect (timeout
  after 5s)` and `(timeout after 8s)` count as the *same* failure —
  numbers, IPs, and quoted strings are collapsed before counting, so
  one bug shows up as `3x` instead of three separate lines. The status
  code is kept, so `404 GET /admin/login` and `500 GET /api/orders/#`
  never merge.
- **Query strings are stripped from paths** (`/logo.png?ver=3` counts
  as `/logo.png`) so one page with a dozen cache-busters doesn't flood
  the top-paths list.
- **Unparsed lines are counted, not hidden.** If a line doesn't match
  either format, the report says how many — a silent drop would hide a
  format change in the log.
- **No dependencies.** One `.py` file, standard library only — it runs
  anywhere Python runs, including a phone.

## The libraries lesson — 6 from the standard library, 0 to install

| Library | What it does here |
|---|---|
| `re` | The whole parser: one regex for Apache lines, one for app logs, one for syslog — plus the cleanup that collapses numbers and IPs so errors group together. |
| `collections` | `Counter` counts status codes, IPs, paths, error types, and per-hour hits; `most_common()` is every "top 10" list in the report. |
| `datetime` | Parses Apache's `08/Nov/2026:14:02:11 +0000` and ISO timestamps so the report can show a real time range and the busiest hour. |
| `argparse` | Turns the flags (`--format`, `--top`, `--errors-only`, `--json`) into a real CLI with `--help` — no manual string-splitting. |
| `json` | Writes the full summary as `report.json`, so another script or a dashboard can consume the same numbers. |
| `pathlib` | Finds the log file on Windows *and* Android with the same code — no hardcoded `C:\` or `/home/` paths. |

That's the point of the series: Python ships with a huge toolbox
already installed. Six libraries, zero downloads, and it does a job
people pay a subscription for.

## What it replaces — and the savings

**Papertrail** (SolarWinds) — cloud log management: send your logs to
their service, search them, get error counts and tallies in a web
dashboard. Verified price: entry paid plan **$7/month** (1 GB/month,
1-week search, 1-year archive; free tier is 50 MB/month with 48-hour
search). Sources: Papertrail/Loggly pricing comparisons, checked
Nov 8, 2026 (copyprogramming.com — "Papertrail's pricing tiers are:
$7/month (1GB), $18/month (2GB), up to $230/month (25GB)"). That's
**$84/year** for the entry tier.

| | Paid | This tool |
|---|---|---|
| Price | $7/mo ($84/yr) | $0 |
| Error counts, top IPs, busiest hours | yes | yes |
| Works offline, logs stay on your machine | no — logs leave your network | yes |
| Live tailing, alerts, multi-server aggregation | yes | no — one file at a time, after the fact |
| 1-year searchable archive in the cloud | yes | no — your files are your archive |

**Savings: $84/year.** It won't live-tail a fleet of servers or page
you at 3 AM — that's what you're paying Papertrail for — but for the
core job, *what broke in this log and when*, it does the job, and your
logs never leave your machine.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$40–55 one-time
+ ~$503.75/year in subscriptions avoided.
