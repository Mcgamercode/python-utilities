# SQLite Query Helper

Inspect any SQLite database, run SQL against it, and export the results —
from the terminal, with nothing to install. No GUI, no account, no
per-device license.

This is tool #10 in the nightly series — a professional utility. SQLite is
the database hiding inside almost everything: phone apps, browsers,
point-of-sale systems, Python projects, data-science notebooks. Sooner or
later every developer or analyst needs to open one up and ask it a
question. The paid GUI clients charge $99 for that privilege. This does
the everyday version — schema, queries, export — in one file, and it opens
the database **read-only by default**, so a typo can't corrupt a live app
database.

## Install — nothing to install

Standard library only. Python 3.8+ works.

```bash
python --version   # any 3.8 or newer
```

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\sqlite-query-helper
python sqlite_query.py C:\Users\mike\data\shop.db --schema
```

**Termux (Android):**

```bash
cd ~/python-tools/sqlite-query-helper
python sqlite_query.py ~/data/shop.db --schema
```

## What you can do

| Command | What it does |
|---|---|
| `--schema` | Full summary: tables, views, columns, types, primary keys, row counts, indexes, file size |
| `--tables` | Quick list of tables/views with row counts |
| `--describe TABLE` | Columns of one table — type, nullable, default, PK |
| `--query "SQL"` | Run one query, print a neat aligned table |
| `--sql-file report.sql` | Run the SQL in a file (several statements, one after another) |
| `--csv out.csv` | Export the query results to CSV (pairs with `--query` / `--sql-file`) |
| `--json` | Print results as JSON instead of a table |
| `--limit N` | Max rows shown/exported (default 100, `0` = all) |
| `--interactive` | Small SQL prompt: type SQL, `.tables`, `.schema`, `.quit` |
| `--write` | Allow writes (INSERT/UPDATE/DELETE). **Off by default** — without it the database is opened read-only and SQLite itself enforces that |

## Examples

```bash
# What is in this database?
python sqlite_query.py shop.db --schema

# Top 5 biggest orders
python sqlite_query.py shop.db --query "SELECT item, price * qty AS total FROM orders ORDER BY total DESC LIMIT 5"

# Same query, straight into a spreadsheet
python sqlite_query.py shop.db --query "SELECT * FROM orders" --csv orders.csv

# Ask it questions interactively
python sqlite_query.py shop.db --interactive
sql> SELECT name FROM users WHERE signup < '2026-06-01';
sql> .quit
```

## The safety rules (read these — they are the point)

1. **Read-only by default.** The database is opened with SQLite's own
   `mode=ro`, so even a bug in this script can't write to the file.
   Writes are refused with a clear message until you add `--write`.
2. **Destructive statements ask first.** In `--write` mode, `DROP`, or a
   `DELETE`/`UPDATE` with no `WHERE`, prints a warning and waits for you
   to type `YES`. Add `--force` to skip the prompt (scripts only).
3. **Nothing is ever deleted by this tool on its own.** There is no
   delete-the-file option, and `--write` only runs the SQL you typed.

## The libraries lesson

Three stdlib modules do all the work — no `pip install` needed:

| Library | What it does here |
|---|---|
| `sqlite3` | Python's built-in SQLite engine: opens the file, runs SQL, returns rows. The whole database lives in one file, and this module is the key to it |
| `argparse` | Turns the `--schema`, `--query`, `--csv` flags into a real command-line tool with `--help` |
| `csv` / `json` | Export results in the two formats every analyst actually hands to someone else |

## What it replaces

**TablePlus Basic — $99 one-time for 1 device** (tableplus.com pricing
page; verified Nov 13, 2026 via pricing reviews checked against the
vendor's page in Oct 2026 — Basic $99, Standard $129 for 2 devices,
renewal $59/yr for updates only).

Honest note: TablePlus is a full GUI client for 20+ database engines, and
free SQLite GUIs exist too (DB Browser for SQLite is free and good). This
tool isn't a TablePlus clone — it's the focused, scriptable, terminal
version for the SQLite work a developer does every day: inspect, query,
export. If you wanted the paid GUI's SQLite workflow on one machine,
that's the $99 this replaces.

**You pay: $0. Saved: $99 one-time.**

## Try it (no database handy?)

```bash
# Build the sample database used to test this tool
python -c "import sqlite3; c=sqlite3.connect('shop.db'); c.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)'); c.executemany('INSERT INTO users VALUES (?,?,?)', [(1,'Ada','ada@example.com'),(2,'Alan','alan@example.com')]); c.commit()"
python sqlite_query.py shop.db --schema
python sqlite_query.py shop.db --query "SELECT * FROM users"
```

## Files

- `sqlite_query.py` — the whole tool, one file
- `README.md` — this file
