# CSV Quick-Stats Profiler

Point it at any CSV and get instant stats in seconds: row/column counts,
per-column detected types, null counts, unique counts, numeric
distributions (min / max / mean / median / stdev), top values for text
columns, and duplicate-row counts.

This is tool #4 in the nightly series — and the first of the
**professional** tools. No personal data, no inside jokes: this is the
kind of utility a working data analyst runs on every new dataset before
a single chart or SQL query. It answers the first question of any data
job: *what's actually in this file?*

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\csv-profiler
python csv_profiler.py data.csv
```

**Termux (Android):**

```bash
cd ~/python-tools/csv-profiler
python csv_profiler.py data.csv
```

That's it. One file, one command.

## What you get

```text
FILE: sales.csv  (464 bytes)
Delimiter: ','   Encoding: utf-8-sig
Rows: 10   Columns: 7
! 1 exact duplicate rows

order_id  [integer]  non-null 10/10  nulls 0 (0.0%)  unique 9 (90.0%)
    min 1001  max 1009  mean 1004.6  median 1004.5  stdev 2.8752  sum 10046

price  [float]  non-null 9/10  nulls 1 (10.0%)  unique 5 (55.6%)
    min 5.5  max 149  mean 44.0233  median 19.99  stdev 59.8655  sum 396.21

order_date  [date]  non-null 10/10  nulls 0 (0.0%)  unique 8 (80.0%)
    earliest 2026-10-01T00:00:00  latest 2026-10-09T00:00:00

product  [text]  non-null 10/10  nulls 0 (0.0%)  unique 4 (40.0%)
    top: 'Widget A' x4, 'Widget B' x3, 'Gadget X' x2, 'Widget C' x1
```

Per column it tells you:

- **Type** — integer, float, boolean, date, text, mixed, or empty. A
  column only gets a type if 90% of its values agree; otherwise it's
  flagged `mixed` with the breakdown (e.g. `integer: 4, text: 1`) — a
  stray `"hello"` in a numbers column is exactly the kind of thing that
  breaks a load downstream.
- **Nulls** — count and percentage. Empty cells plus `NA`, `N/A`,
  `null`, `none`, `nan`, `-` all count as missing.
- **Uniques** — how many distinct values, and what share of the column
  they are. 100% unique on an ID column is healthy; 100% unique on a
  "category" column means the column is useless.
- **Numeric stats** — min, max, mean, median, stdev, sum.
- **Dates** — earliest and latest.
- **Top values** — the most common values and their counts.

It also flags, at the top of the report: exact duplicate rows, ragged
rows (wrong number of fields — padded, never silently dropped), and
completely empty rows.

## Useful flags

```bash
# Save a machine-readable copy alongside the screen report
python csv_profiler.py data.csv --json report.json

# Show 10 top values per column instead of 5
python csv_profiler.py data.csv --top 10

# Print 5 sample data rows after the report
python csv_profiler.py data.csv --sample 5

# Semicolon-delimited export, or a file with no header row
python csv_profiler.py export.csv --delimiter ";"
python csv_profiler.py raw.csv --no-header
```

The delimiter is auto-detected by default (comma, semicolon, tab, or
pipe), and encoding falls back from UTF-8 to latin-1, so European
exports with `;` separators and accented characters just work.

## The rules baked in

- **Read-only.** The tool only reads the file you point it at. It never
  writes to it, never deletes anything, and never uploads anything —
  your data stays on your machine.
- **Ragged rows are counted, not hidden.** If a row has the wrong number
  of fields, the report says so and pads it — a silent drop would hide
  a broken export.
- **Duplicate column names get renamed** (`name`, `name_2`) instead of
  colliding.
- **No dependencies.** One `.py` file, standard library only — it runs
  anywhere Python runs, including a phone.

## The libraries lesson — 6 from the standard library, 0 to install

| Library | What it does here |
|---|---|
| `csv` | Reads the file properly — quoted commas, embedded newlines, all of it — and `csv.Sniffer` auto-detects the delimiter instead of you guessing. |
| `statistics` | `fmean`, `median`, `stdev` — the numeric distributions in one line each, no hand-rolled math. |
| `collections` | `Counter` counts top values, unique values, and type breakdowns; `most_common()` is the whole "top 5" feature. |
| `argparse` | Turns the flags (`--json`, `--top`, `--sample`, `--delimiter`) into a real CLI with `--help` — no manual string-splitting. |
| `json` | Writes the full profile as `report.json`, so another script (or your SQL study) can consume the same numbers. |
| `pathlib` | Finds and sizes the file on Windows *and* Android with the same code — no hardcoded `C:\` or `/home/` paths. |

That's the point of the series: Python ships with a huge toolbox already
installed. Six libraries, zero downloads, and it does a job people pay a
subscription for.

## What it replaces — and the savings

**HQ Data Profiler** — a desktop CSV/data profiler: column stats, types,
nulls, uniques, top values, anomaly detection. Verified price:
**$9.99/month per user** (SourceForge listing and Slashdot listing both
show "Starting Price: $9.99/month/user", checked Nov 7, 2026;
hqdataprofiler.com). That's **$119.88/year**.

| | Paid | This tool |
|---|---|---|
| Price | $9.99/mo ($119.88/yr) | $0 |
| Column stats, types, nulls, uniques | yes | yes |
| Numeric distributions + top values | yes | yes |
| JSON export | yes | yes |
| Works offline, your data stays yours | yes | yes |
| ML anomaly detection, Excel/Parquet input | yes | no — CSV only, for now |

**Savings: $119.88/year.** It won't do the ML outlier detection or
read Excel files — that's the part you're paying for there — but for the
core job, *what's in this CSV and can I trust it*, it does the job.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$40–55 one-time +
~$419.75/year in subscriptions avoided.
