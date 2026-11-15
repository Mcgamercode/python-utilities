# Termux Cleaner

Find what's eating your phone's storage and clear the safe stuff — without
touching your scripts, projects, or downloads.

Termux balloons over time: apt package archives, pip/npm caches,
`__pycache__` folders, and cargo caches pile up silently. On Mike's phone
Termux hit 40–50 GB. This tool scans your Termux home, groups the bloat
by category, and tells you exactly what is safe to delete — before it
deletes anything.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Get it on your phone

Save `termux_cleaner.py` to your phone (it lands in `~/downloads`),
then in Termux:

```bash
cp ~/downloads/termux_cleaner.py ~/
cd ~/
python termux_cleaner.py
```

## Run it

Dry run first — this only reports, it deletes nothing:

```bash
python termux_cleaner.py
```

When you're happy with what it found, clean the safe stuff:

```bash
python termux_cleaner.py --clean
```

It prints the exact delete list and asks `Delete these? [y/N]` first.
Add `--yes` to skip the prompt:

```bash
python termux_cleaner.py --clean --yes
```

Show more of the biggest files:

```bash
python termux_cleaner.py --top 20
```

## What it deletes (SAFE) vs what it only reports (REVIEW)

| Category | Tier | Why |
|---|---|---|
| APT package archives (`.deb`) | SAFE | Re-downloaded by apt if ever needed |
| APT package lists | SAFE | Rebuilt by `apt update` |
| pip cache (`~/.cache/pip`) | SAFE | Wheels re-downloaded on next install |
| npm cache (`~/.npm`) | SAFE | Re-downloaded on next `npm install` |
| cargo registry cache | SAFE | Crates re-fetched by cargo |
| Python bytecode (`__pycache__` / `.pyc`) | SAFE | Regenerated on next import |
| Other `~/.cache/*` folders | REVIEW | Usually safe — check what's inside first |
| `~/downloads` | REVIEW | Your files — never auto-deleted |
| Virtualenvs (`venv`, `.venv`) | REVIEW | Your environments — delete by hand if unused |
| Largest files (over 50 MB) | REVIEW | Listed so you can judge them yourself |

Downloads can be cleaned too, but only if you opt in — and only files
older than 90 days:

```bash
python termux_cleaner.py --clean --include-downloads
python termux_cleaner.py --clean --include-downloads --older-than-days 30
```

## What you get

```text
Termux cleaner v1.0.0 — scanning /data/data/com.termux/files/home

== Storage by category ==
  [SAFE  ] pip cache                               3.2 GB
  [SAFE  ] APT package archives (.deb)             1.8 GB
  [SAFE  ] Python bytecode (__pycache__ / .pyc)  420.0 MB
  [REVIEW] Downloads (~/downloads)                6.1 GB
  [REVIEW] Virtualenv: ~/venv                      2.4 GB

Safe to reclaim (caches + bytecode): 5.4 GB
Review items (never auto-deleted):   8.5 GB

== Largest files (over 50 MB) ==
     1.2 GB  ~/downloads/big-backup.tar
   800.0 MB  ~/some-project/model.bin
```

## The rules baked in

- **Dry-run by default.** No flags = report only. Nothing is deleted
  unless you pass `--clean`.
- **Only safe categories are ever deleted.** Your scripts, projects,
  venvs, and downloads are never deleted automatically.
- **Exact delete list first.** `--clean` prints every path it will
  remove and asks for confirmation, unless you pass `--yes`.
- **No surprises.** Unreadable files and permission errors are skipped
  and reported, not fatal.

## The libraries lesson

| Library | What it does here |
|---|---|
| `pathlib` | Builds every path from `$HOME` / `$PREFIX` so the same code runs on Termux and on a normal Linux box |
| `os.walk` | Walks the whole home directory to find caches, venvs, and big files without following symlink loops |
| `argparse` | Turns the flags (`--clean`, `--yes`, `--top`, `--include-downloads`) into a real CLI with `--help` |
| `shutil` | `rmtree` removes whole cache directories in one call |
| `time` | Compares download file ages against the `--older-than-days` cutoff |

## What it replaces

There is no paid equivalent to name honestly — the usual "phone cleaner"
apps are adware that want subscriptions and permissions. This does the
job with one script you own, and it never uploads anything anywhere.
The savings are the storage itself: on a phone with 40–50 GB of Termux,
clearing stale caches routinely frees multiple gigabytes.

## Series note

This is a direct request from Mike (Nov 9, 2026), not a nightly-series
tool — it is not numbered in the series and is not in `SAVINGS_LOG.md`.
