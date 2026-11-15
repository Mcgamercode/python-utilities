#!/usr/bin/env python3
"""Termux storage cleaner — find what's eating your phone's storage, safely.

Termux balloons over time: apt package archives, pip/npm caches,
__pycache__ folders, cargo caches, and old downloads pile up silently.
This tool scans your Termux home, groups the bloat by category, and
tells you exactly what is safe to delete — before it deletes anything.

Rules baked in:
- DRY-RUN BY DEFAULT. Running it with no flags only reports. Nothing
  is deleted unless you pass --clean.
- Only "safe" categories are ever deleted: package caches and
  regenerable bytecode/caches. Your scripts, projects, venvs, and
  downloads are NEVER deleted automatically.
- Downloads are report-only unless you pass --include-downloads, and
  then only files older than --older-than-days (default 90).
- --clean always shows the exact delete list first and asks for
  confirmation, unless you also pass --yes.

Usage (in Termux):
    python termux_cleaner.py               # dry-run report
    python termux_cleaner.py --clean       # delete safe caches (asks first)
    python termux_cleaner.py --clean --yes # delete safe caches, no prompt
    python termux_cleaner.py --top 20      # show 20 biggest files

Stdlib only — no pip installs. Python 3.8+.
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

VERSION = "1.0.0"

# Files/dirs bigger than this show up in the "largest files" list.
LARGE_MIN_MB = 50

# Category labels
SAFE = "safe"      # deleted by --clean
REVIEW = "review"  # reported only, never auto-deleted


def human(nbytes):
    """Format a byte count like 1.4 GB / 320.5 MB / 12.0 KB."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(nbytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def dir_size(path):
    """Total size of all files under a directory (no symlink loops)."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def find_pycache(root):
    """All __pycache__ dirs and stray .pyc/.pyo files under root.

    A __pycache__ dir covers the .pyc files inside it, so we don't
    descend into it — otherwise the same bytes get counted twice.
    """
    hits = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if "__pycache__" in dirnames:
            hits.append(Path(dirpath) / "__pycache__")
            dirnames.remove("__pycache__")
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                hits.append(Path(dirpath) / name)
    return hits


def find_venvs(root):
    """Dirs that look like Python virtualenvs (contain pyvenv.cfg)."""
    venvs = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Don't descend into a venv once found — count it as one item.
        if "pyvenv.cfg" in filenames:
            venvs.append(Path(dirpath))
            dirnames[:] = []
    return venvs


def find_large_files(root, min_bytes, limit):
    """Largest individual files under root, biggest first."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size >= min_bytes:
                found.append((size, p))
    found.sort(key=lambda item: item[0], reverse=True)
    return found[:limit]


def collect(root, prefix):
    """Scan and bucket everything into (label, tier, size, paths) rows.

    Returns (rows, safe_paths, review_notes):
      rows: list of dicts with label/tier/size/detail for the report.
      safe_paths: list of Paths --clean may delete.
      review_notes: extra lines for the report.
    """
    rows = []
    safe_paths = []

    def add(label, tier, size, paths, detail=""):
        rows.append({"label": label, "tier": tier, "size": size,
                     "detail": detail})
        if tier == SAFE:
            safe_paths.extend(paths)

    # --- apt package cache: .deb files + package lists (regenerable) ---
    apt_archives = prefix / "var" / "cache" / "apt" / "archives"
    if apt_archives.is_dir():
        debs = [p for p in apt_archives.glob("*.deb") if p.is_file()]
        size = sum(file_size(p) for p in debs)
        add("APT package archives (.deb)", SAFE, size, debs,
            f"{len(debs)} files — re-downloaded by apt if needed")
    apt_lists = prefix / "var" / "lib" / "apt" / "lists"
    if apt_lists.is_dir():
        files = [p for p in apt_lists.iterdir() if p.is_file()]
        size = sum(file_size(p) for p in files)
        add("APT package lists", SAFE, size, files,
            f"{len(files)} files — rebuilt by `apt update`")

    # --- pip cache ---
    pip_cache = root / ".cache" / "pip"
    if pip_cache.is_dir():
        add("pip cache", SAFE, dir_size(pip_cache), [pip_cache],
            "wheels + http cache — re-downloaded on next install")

    # --- npm cache ---
    npm_cache = root / ".npm"
    if npm_cache.is_dir():
        add("npm cache", SAFE, dir_size(npm_cache), [npm_cache],
            "re-downloaded on next `npm install`")

    # --- cargo registry cache (downloaded .crate files) ---
    cargo_cache = root / ".cargo" / "registry" / "cache"
    if cargo_cache.is_dir():
        add("cargo registry cache", SAFE, dir_size(cargo_cache),
            [cargo_cache], "downloaded crates — re-fetched by cargo")
    cargo_src = root / ".cargo" / "registry" / "src"
    if cargo_src.is_dir():
        add("cargo registry sources (extracted)", REVIEW,
            dir_size(cargo_src), [],
            "extracted crate sources — review before deleting")

    # --- __pycache__ / .pyc (regenerated on next import) ---
    pycache = find_pycache(root)
    if pycache:
        size = sum(dir_size(p) if p.is_dir() else file_size(p)
                   for p in pycache)
        add("Python bytecode (__pycache__ / .pyc)", SAFE, size, pycache,
            f"{len(pycache)} dirs/files — regenerated on next import")

    # --- other ~/.cache subdirs: report, don't auto-delete ---
    cache_dir = root / ".cache"
    if cache_dir.is_dir():
        for child in sorted(cache_dir.iterdir()):
            if child.name in ("pip",):
                continue  # already counted above
            if child.is_dir():
                size = dir_size(child)
                if size > 0:
                    add(f"Cache: ~/.cache/{child.name}", REVIEW, size, [],
                        "review — usually safe, check what's inside first")
            elif child.is_file():
                size = file_size(child)
                if size > 0:
                    add(f"Cache file: ~/.cache/{child.name}", REVIEW, size,
                        [], "")

    # --- downloads: report only ---
    downloads = root / "downloads"
    if downloads.is_dir():
        files = [p for p in downloads.rglob("*") if p.is_file()]
        size = sum(file_size(p) for p in files)
        add("Downloads (~/downloads)", REVIEW, size, [],
            f"{len(files)} files — never auto-deleted; "
            "use --include-downloads to clean old ones")

    # --- virtualenvs: report only, they're your working environments ---
    venvs = find_venvs(root)
    for venv in venvs:
        add(f"Virtualenv: ~/{venv.relative_to(root)}", REVIEW,
            dir_size(venv), [],
            "your environment — delete only by hand if unused")

    return rows, safe_paths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Termux storage cleaner — dry-run report by default, "
                    "--clean to delete safe caches.")
    parser.add_argument("--root", default=None,
                        help="Termux home to scan (default: $HOME)")
    parser.add_argument("--prefix", default=None,
                        help="Termux $PREFIX (default: $PREFIX env or "
                             "/data/data/com.termux/files/usr)")
    parser.add_argument("--clean", action="store_true",
                        help="Delete the SAFE categories (asks first)")
    parser.add_argument("--yes", action="store_true",
                        help="With --clean, skip the confirmation prompt")
    parser.add_argument("--include-downloads", action="store_true",
                        help="With --clean, also delete Downloads files "
                             "older than --older-than-days")
    parser.add_argument("--older-than-days", type=int, default=90,
                        help="Age threshold for --include-downloads "
                             "(default: 90)")
    parser.add_argument("--top", type=int, default=10,
                        help="How many largest files to list (default: 10)")
    parser.add_argument("--large-min-mb", type=int, default=LARGE_MIN_MB,
                        help="Minimum size (MB) for the largest-files list "
                             f"(default: {LARGE_MIN_MB})")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    root = Path(args.root or os.environ.get("HOME", "~")).expanduser()
    prefix = Path(args.prefix or os.environ.get(
        "PREFIX", "/data/data/com.termux/files/usr"))

    if not root.is_dir():
        print(f"Root not found: {root}", file=sys.stderr)
        return 1

    print(f"Termux cleaner v{VERSION} — scanning {root}")
    if prefix.is_dir():
        print(f"  $PREFIX: {prefix}")
    print()

    rows, safe_paths = collect(root, prefix)

    safe_total = sum(r["size"] for r in rows if r["tier"] == SAFE)
    review_total = sum(r["size"] for r in rows if r["tier"] == REVIEW)

    print("== Storage by category ==")
    for row in sorted(rows, key=lambda r: r["size"], reverse=True):
        tag = "SAFE  " if row["tier"] == SAFE else "REVIEW"
        line = f"  [{tag}] {row['label']:<38} {human(row['size']):>10}"
        if row["detail"]:
            line += f"  — {row['detail']}"
        print(line)
    print()
    print(f"Safe to reclaim (caches + bytecode): {human(safe_total)}")
    print(f"Review items (never auto-deleted):   {human(review_total)}")
    print()

    # Largest individual files — the usual suspects for 40+ GB.
    large = find_large_files(root, args.large_min_mb * 1024 * 1024,
                             args.top)
    if large:
        print(f"== Largest files (over {args.large_min_mb} MB) ==")
        for size, path in large:
            try:
                shown = "~/" + str(path.relative_to(root))
            except ValueError:
                shown = str(path)
            print(f"  {human(size):>10}  {shown}")
        print()

    if not args.clean:
        print("Dry run — nothing was deleted.")
        print("Run with --clean to delete the SAFE categories above.")
        print("Downloads and venvs are never deleted without "
              "--include-downloads / by hand.")
        return 0

    # --- --clean: delete SAFE paths, optionally old downloads ---
    to_delete = list(safe_paths)
    downloads = root / "downloads"
    old_downloads = []
    if args.include_downloads and downloads.is_dir():
        cutoff = time.time() - args.older_than_days * 86400
        for p in downloads.rglob("*"):
            if p.is_file():
                try:
                    if p.stat().st_mtime < cutoff:
                        old_downloads.append(p)
                except OSError:
                    continue
        to_delete.extend(old_downloads)

    if not to_delete:
        print("Nothing safe to delete — you're already clean.")
        return 0

    total = sum(dir_size(p) if p.is_dir() else file_size(p)
                for p in to_delete)
    print(f"About to delete {len(to_delete)} items "
          f"({human(total)} total):")
    for p in sorted(to_delete, key=str)[:50]:
        print(f"  {p}")
    if len(to_delete) > 50:
        print(f"  ... and {len(to_delete) - 50} more")
    print()

    if not args.yes:
        answer = input("Delete these? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted — nothing deleted.")
            return 0

    reclaimed = 0
    failed = 0
    for p in to_delete:
        try:
            size = dir_size(p) if p.is_dir() else file_size(p)
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            reclaimed += size
        except OSError as exc:
            failed += 1
            print(f"  Could not delete {p}: {exc}", file=sys.stderr)

    print()
    print(f"Done — reclaimed {human(reclaimed)}.")
    if failed:
        print(f"{failed} item(s) could not be deleted (see above).")
    print("Tip: run again to see the new totals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
