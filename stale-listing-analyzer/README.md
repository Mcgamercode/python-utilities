# Stale Listing Analyzer — Tool #2 of the Nightly Python Series

Reads your Marketplace `inventory.db` and tells you which listings are going
stale, what to do about each one (renew, cut the price, or pull it), and
what's actually selling. Built for a volume game: with ~19 live listings,
the ones sitting 30+ days are the ones quietly costing you sales.

**Read-only by default** — it never changes the database. The only write is
`--pull`, which marks 60+ day "dead" listings as pulled, and only after you
type `PULL` to confirm. It never deletes a Facebook listing; you still pull
that in the app yourself.

## What it replaces

**Vendoo Starter — $14.99/month (~$179.88/yr; $149.88/yr billed annually)**,
verified Nov 5, 2026 from 2026 pricing roundups
([nifty.ai Vendoo pricing](https://nifty.ai/post/vendoo-pricing),
[3dsellers Vendoo review](https://www.3dsellers.com/marketplace-apps/vendoo)).
Vendoo is a reseller listing manager: its Starter tier is the cheapest one
with inventory analytics plus delist/relist — the "refresh stale listings"
feature this tool covers. Your version: $0, and it reads the database you
already keep.

## Run it

Windows PowerShell:

```powershell
python stale_listings.py
python stale_listings.py --markdown report.md
```

Termux / Linux:

```bash
python3 stale_listings.py
python3 stale_listings.py --db ~/workspace/marketplace/inventory.db --json report.json
```

No installs needed — standard library only
(`sqlite3`, `argparse`, `datetime`, `pathlib`, `re`).

## How it works (the Python lesson)

- **`sqlite3`** — opens your `inventory.db` in read-only mode
  (`mode=ro` in the connection string, so a bug can't write to it) and
  pulls every item with one `SELECT`.
- **`datetime`** — your dates come in three formats (`2026-09-11`,
  `2026-10-09T23:59:00.873210`, `2026-10-14 22:08:36`), so the parser
  tries each format in turn. Age in days = today − date listed.
- **`re` (regular expressions)** — fishes `Floor $100` out of the notes
  field, so a suggested price cut never goes below the floor you set
  (the Harley exhaust and the Kenwood consignment both have floors).
- **`argparse`** — the flags (`--db`, `--stale-days`, `--markdown`,
  `--json`, `--pull`) with help text, so `python3 stale_listings.py --help`
  documents itself.

## The rules it applies

| Age | Bucket | What it tells you |
|---|---|---|
| Under 14 days | Fresh | Leave it alone |
| 14–29 days | Warming | Watch it — goes stale next week |
| 30–59 days | Stale | Renew it, or cut 10% |
| 60+ days | Dead | Pull it, or cut 15% |

Plus two extra checks: **price flags** (listed below your target price —
7 listings are asking less than the target right now) and **floor guard**
(a cut suggestion stops at your floor instead of going under it).

## Safety

- Default mode is report-only: no writes, no deletes, no Facebook actions.
- `--pull` only touches 60+ day listings, prints them first, and requires
  you to type `PULL`. Anything else cancels with nothing changed.
- A `--pull` still doesn't delete the Facebook listing — that's yours to
  do in the app.

## Options

| Flag | What it does |
|---|---|
| `--db PATH` | Path to inventory.db (default: `~/workspace/marketplace/inventory.db`) |
| `--stale-days 30` | Days old before a listing counts as stale (default 30) |
| `--dead-days 60` | Days old before a listing counts as dead (default 60) |
| `--as-of YYYY-MM-DD` | Pretend "today" is another date (useful for re-checks) |
| `--markdown FILE` | Also write the report as Markdown |
| `--json FILE` | Also write the report data as JSON |
| `--pull` | Mark 60+ day listings as `pulled` in the DB (asks first) |

## Verified test

Tested Nov 5, 2026 on a sample database (fresh / warming / stale / dead
listings, a list-below-target case, a floor that blocks a 15% cut, an
ISO-datetime list date, a listing with no date, sold items fast and slow):
every bucket, recommendation, and price flag came out right; `--pull`
cancelled cleanly on "no" and marked exactly the 2 dead listings on `PULL`.

Run against the real `inventory.db` on Nov 5, 2026: **19 active listings,
$1,040 asking value, $160 of it stale** — the roadside vacuum ($10) and
the Pioneer SX-V500 ($150), both 55 days old. **0 dead.** 15 more listings
hit 30 days next week (the Oct 9–10 batch). Median time from listed to
sold is **8 days** (fastest: MTX speakers, 2 days). 5 items are still
sitting in inventory unlisted, including the Emerson TV combo (target $90).

One data note: the two "stale" listings carry a Sep 11 list date in the
database, but their notes say they were listed Oct 9 — if Oct 9 is right,
they're only warming, not stale. Worth a glance at the dates before
cutting the Pioneer's price.
