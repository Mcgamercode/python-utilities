# Duplicate Finder — Tool #1 of the Nightly Python Series

Finds files that are byte-for-byte identical and moves the extras into a
`_duplicates/` review folder. **Never deletes anything** — and it writes a
restore script so you can undo the whole thing in one command.

## What it replaces

**Duplicate Cleaner Pro** — about **$40–55 for a lifetime license**
(verified Nov 5, 2026 from current comparison roundups). Your version: $0,
and you own the code.

## Run it

Windows PowerShell:

```powershell
python dupe_finder.py D:\FlashDrive
python dupe_finder.py D:\FlashDrive --quarantine
```

Termux / Linux:

```bash
python3 dupe_finder.py ~/storage --min-size 10MB
python3 dupe_finder.py ~/storage --quarantine
```

No installs needed — standard library only (`hashlib`, `pathlib`, `shutil`).

## How it works (the Python lesson)

- **`pathlib` + `os.walk`** — walk the whole drive, any depth, any OS.
- **Size first, hash second** — files are grouped by size before anything
  is read. Two files with different sizes can't be duplicates, so most
  files are ruled out for free.
- **`hashlib.sha256`** — a 64 KB prefix hash filters candidates fast, then
  a full-file SHA-256 confirms. Same hash = same file, no matter the name.
- **Quarantine, don't delete** — extras move to `_duplicates/` keeping
  their folder layout, plus `dupe_report.json` and a `restore_duplicates.py`
  that puts everything back.

## Safety

- Default mode is a dry run: report only, nothing moves.
- `--quarantine` moves files, never deletes them.
- The quarantine folder itself is skipped on later scans.
- Symlinks are skipped.

## Options

| Flag | What it does |
|---|---|
| `folder` | Folder to scan (required) |
| `--min-size 1MB` | Ignore files smaller than this (default 1MB) |
| `--quarantine` | Move extras into `<folder>/_duplicates/` |

## Verified test

Tested Nov 5, 2026 on sample files: 3 identical 2.3 MB videos in
different folders + 1 same-size-but-different file + 1 small file.
Correctly grouped only the true duplicates, moved 2 extras to quarantine,
left 1 copy in place, and the restore script put both back.
