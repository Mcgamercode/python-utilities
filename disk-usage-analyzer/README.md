# Disk Usage Analyzer

**What it does:** Point it at any folder and it tells you exactly what is eating the space — biggest files, biggest folders, space by file type, and how old the big stuff is. The classic "my drive is full, where did it all go?" question, answered in seconds.

**The professional problem it solves:** Every IT pro and developer hits a full disk eventually — a runaway log folder, a forgotten video export, a `node_modules` forest. Guessing wastes an afternoon; this shows the answer in one scan.

**It never deletes anything.** Read-only by design. It reports; you decide what to remove.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\disk-usage-analyzer
python disk_analyzer.py C:\Users\mike\Downloads
```

**Termux (Android):**

```bash
cd ~/python-tools/disk-usage-analyzer
python disk_analyzer.py ~/storage/downloads
```

## Options

| Flag | What it does |
|---|---|
| `--top 30` | Show the 30 biggest files/folders instead of 20 |
| `--depth 2` | Only scan 2 folders deep (fast overview of a huge drive) |
| `--exclude name1 name2` | Skip extra folders by name, e.g. `--exclude .git node_modules` |
| `--no-default-excludes` | Also scan `.git`, `node_modules`, `__pycache__`, `.venv` (skipped by default — they're almost never what you're looking for) |
| `--min-size 1MB` | Ignore files smaller than 1 MB (also accepts `500KB`, `1024`) |
| `--json report.json` | Write the full report as JSON — feed it to another script or a dashboard |
| `--csv top-files.csv` | Write the biggest-files list as CSV — open it in Excel or Google Sheets |

## Example output

```
Disk usage: C:\Users\mike\Downloads
============================================================
  Total size:    14.2 GB
  Files:         3,418
  Folders:       212
  Drive:         38.6 GB free of 237 GB (16.3% free)

Top 20 biggest folders:
  ########################################  6.10 GB  C:\Users\mike\Downloads\Videos
  ####################                     3.02 GB  C:\Users\mike\Downloads\Backups
  ...

Top 20 biggest files:
     1.8 GB  C:\Users\mike\Downloads\Videos\wedding-final.mp4
   912.4 MB  C:\Users\mike\Downloads\Backups\phone-2026-10.zip
  ...

Space by file type:
  .mp4             412 files     6.10 GB  ( 43.0%)
  .zip              38 files     3.40 GB  ( 23.9%)
  ...

Space by file age:
  over 1 year (stale)   1,204 files     5.60 GB

Cleanup hint: 5.60 GB sits in files untouched for over a year — review those before deleting anything.
```

## How it works (the "vast libraries" lesson)

This tool uses **only the standard library** — the point is how much Python ships with:

| Library | What it does here |
|---|---|
| `os.scandir` | Fast directory walking — returns file sizes without a second system call per file, so big trees scan quickly |
| `pathlib` | Cross-platform paths — the same code works on `C:\Users\...` and `~/storage/...` |
| `shutil.disk_usage` | Free/total space of the drive the folder lives on |
| `argparse` | The `--top`, `--json`, `--exclude` flags and the built-in `--help` text |
| `json` / `csv` | Exporting the report so other tools (Excel, a dashboard, a cleanup script) can use it |

**Why `os.scandir` instead of `os.listdir`?** `listdir` gives you names only — every size check costs another call to the OS. `scandir` returns directory entries that already carry size and type, which is noticeably faster on folders with thousands of files.

## Paid equivalent it replaces

**DiskSavvy Pro — $50 one-time.** A Windows disk-space analyzer with the same core job: scan a drive, rank folders and files by size, break usage down by file type, and export reports. Price verified Nov 9, 2026 via Help Desk Geek ("Upgrading to DiskSavvy Pro will set you back $50") and MakeUseOf ("purchase Disk Savvy Pro for $50") — [helpdeskgeek.com](https://helpdeskgeek.com/free-tools-review/6-best-disk-space-analyzers-to-find-lost-gigabytes/) and [makeuseof.com](https://www.makeuseof.com/tag/need-disk-cleanup-visualize-takes-space-windows-pc/). Cross-check: TreeSize Professional starts at ~$49 on JAM Software's own site.

**You pay:** $0. **You save:** $50 one-time.

## Notes

- Permission-denied folders (system folders, other users' profiles) are skipped and counted, never fatal — the scan finishes and tells you how many entries it couldn't read.
- Symbolic links are not followed, so a link loop can't send the scanner in circles.
- Hidden folders are scanned (except the default excludes above). If a scan is slow, `--depth 2` gives the big picture fast.
