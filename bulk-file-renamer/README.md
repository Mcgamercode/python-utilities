# Bulk File Renamer

Rename dozens of files in one shot — without the fear. Every run shows a
preview first, refuses to overwrite anything, and writes an undo log, so a
bad rename is one command away from being reversed.

This is tool #9 in the nightly series — a professional utility. Renaming
files one by one is the kind of busywork that eats an afternoon: photo
dumps from a camera (`IMG_4821.jpg`), downloaded files with spaces and
` (1)` copy suffixes, datasets that need clean numbered names before
analysis. A bulk renamer is a standard tool in every IT pro's and data
analyst's kit — and the paid ones charge for the privilege.

## Install — nothing to install

Standard library only. Python 3.8+ works.

```bash
python --version   # any 3.8 or newer
```

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\bulk-file-renamer
python bulk_rename.py C:\Users\mike\Pictures --pattern "*.jpg" --spaces-to _
```

**Termux (Android):**

```bash
cd ~/python-tools/bulk-file-renamer
python bulk_rename.py ~/Pictures --pattern "*.jpg" --spaces-to _
```

That first run is a **dry run** — it only prints a preview. Nothing is
renamed until you add `--apply`:

```bash
python bulk_rename.py ~/Pictures --pattern "*.jpg" --spaces-to _ --apply
```

## What you can do

| Option | What it does | Example |
|---|---|---|
| `--find X --replace Y` | Replace text in the name | `--find "IMG" --replace "photo"` |
| `--regex` | Treat `--find` as a regular expression | `--regex --find " \(\d+\)$" --replace ""` strips ` (1)` copy suffixes |
| `--case lower/upper/title` | Change the case of the name | `--case lower` |
| `--spaces-to _` or `-` | Replace every space | `--spaces-to _` |
| `--date mtime` or `today` | Prefix `YYYY-MM-DD` from the file's date, or today | `--date mtime` |
| `--number` | Append a counter: `_001`, `_002` … | `--number --number-start 1 --number-pad 3` |
| `--prefix` / `--suffix` | Add text at the start / end of the name | `--prefix "2026-"` |
| `--pattern "*.jpg"` | Only match certain files (a glob) | `--pattern "IMG*.jpg"` |
| `--recursive` | Also rename in subfolders | |
| `--apply` | Actually rename (without it: preview only) | |

Combine them — they run in that order. A typical photo cleanup:

```bash
# Preview: lowercase, underscores, strip copy suffixes, number the set
python bulk_rename.py ~/Photos --pattern "*.jpg" --case lower --spaces-to _ \
    --regex --find " \(\d+\)$" --replace "" --number --number-pad 3

# Looks right? Do it for real.
python bulk_rename.py ~/Photos --pattern "*.jpg" --case lower --spaces-to _ \
    --regex --find " \(\d+\)$" --replace "" --number --number-pad 3 --apply
```

## Safety — the part that matters

- **Dry-run is the default.** No `--apply`, no renames. Ever.
- **Nothing is ever overwritten.** A rename that would clobber an existing
  file is skipped and reported, never forced. If two files would land on
  the same new name, both are skipped.
- **Every real run writes an undo log** (a JSON file in the target folder,
  named `.bulk-rename-undo-YYYYMMDD-HHMMSS.json`). To reverse a run:

```bash
python bulk_rename.py --undo .bulk-rename-undo-20261112-212000.json
```

- **Swaps work.** Renaming `a.txt` → `b.txt` while `b.txt` → `a.txt`
  happens in two phases (temp name, then final name), so nothing is lost.

## What you get

Dry run — a plain old → new table, skips explained:

```text
OLD NAME              ->  NEW NAME
----------------------------------------------------
IMG 2024-01-01.jpg    ->  IMG_2024-01-01.jpg
Vacation Photo 1.png  ->  Vacation_Photo_1.png
notes.txt             --  SKIPPED: no change

2 file(s) would be renamed, 1 skipped.
Run the same command with --apply to do it for real.
```

Real run:

```text
Renamed 2 file(s), 1 skipped.
Undo log: .bulk-rename-undo-20261112-212000.json
To reverse this run: python bulk_rename.py --undo ".bulk-rename-undo-20261112-212000.json"
```

## The libraries lesson

This tool is **standard library only** — and that's the point. Three modules
do all the heavy lifting:

- **`pathlib`** — files and folders as objects (`Path.glob`, `with_name`,
  `rename`) instead of string juggling. Same code on Windows and Android.
- **`argparse`** — turns the command-line flags into a real interface
  (`--help` works, bad input gets a clear error instead of a crash).
- **`re` + `json`** — `re` powers the regex find/replace; `json` writes the
  undo log in a format any other tool can read.

No pip install, nothing to break on the next Python update.

## What it replaces

**Bulk Rename Utility** — the standard Windows bulk renamer. Free for
personal use at home, but a commercial license (required for any work or
business use) is **$92.95 one-time per computer**. Source: the official
buy page, https://www.bulkrenameutility.co.uk/Buy.php (checked Nov 12, 2026).

This tool costs $0, runs on Windows and Android, and adds the two things
that matter most when renaming in bulk: a dry-run preview and a one-command
undo.

## Tested

Tested Nov 12, 2026 on sample files in `/tmp`: dry-run preview, real
rename, undo round-trip (original names restored exactly), true `a ↔ b`
swap, two-files-one-name collision (both refused), regex copy-suffix
strip + numbering, and bad-folder / no-transform error handling. No files
were overwritten in any test.
