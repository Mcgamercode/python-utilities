#!/usr/bin/env python3
"""
disk_analyzer.py — Disk Usage Analyzer
======================================
Point it at any folder and it tells you exactly what is eating the space:
biggest files, biggest folders, breakdown by file type, and how old the
big stuff is. Read-only — it never deletes, moves, or changes anything.

Usage:
    python disk_analyzer.py <folder> [options]

Examples:
    python disk_analyzer.py C:\\Users\\mike\\Downloads
    python disk_analyzer.py ~/Downloads --top 30 --json report.json
    python disk_analyzer.py . --exclude .git node_modules __pycache__ --csv report.csv

Standard library only — no pip install needed. Python 3.8+.
Works on Windows PowerShell, macOS, Linux, and Termux/Android.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"

# Folders that are almost never worth scanning: caches, VCS metadata,
# dependency trees. Skipped by default; use --no-default-excludes to scan them.
DEFAULT_EXCLUDES = {".git", ".svn", "__pycache__", "node_modules", ".venv", "venv"}

# Age buckets, in days. "Stale" = not modified in over a year.
AGE_BUCKETS = [
    ("last 7 days", 0, 7),
    ("8-30 days", 8, 30),
    ("1-6 months", 31, 180),
    ("6-12 months", 181, 365),
    ("over 1 year (stale)", 366, None),
]


def human_size(num_bytes):
    """Turn a byte count into a human-readable string, e.g. 1.42 GB."""
    num_bytes = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:,.1f} {unit}" if unit != "B" else f"{int(num_bytes):,} B"
        num_bytes /= 1024.0
    return f"{num_bytes:,.1f} EB"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Disk Usage Analyzer — find out what is eating a drive."
    )
    parser.add_argument(
        "path", nargs="?", default=".",
        help="Folder to scan (default: current folder).",
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="How many biggest files/folders to list (default: 20).",
    )
    parser.add_argument(
        "--depth", type=int, default=None,
        help="Max folder depth to scan (default: no limit).",
    )
    parser.add_argument(
        "--exclude", nargs="*", default=[],
        help="Extra folder names to skip, e.g. --exclude .git node_modules",
    )
    parser.add_argument(
        "--no-default-excludes", action="store_true",
        help="Also scan normally-skipped folders (.git, node_modules, ...).",
    )
    parser.add_argument(
        "--min-size", default="0",
        help="Ignore files smaller than this, e.g. 1MB, 500KB, 1024 (default: 0).",
    )
    parser.add_argument(
        "--json", metavar="FILE", default=None,
        help="Write the full report as JSON to FILE.",
    )
    parser.add_argument(
        "--csv", metavar="FILE", default=None,
        help="Write the top-files list as CSV to FILE.",
    )
    parser.add_argument(
        "--version", action="version", version=f"disk_analyzer.py {VERSION}",
    )
    return parser.parse_args(argv)


def parse_size(text):
    """Parse '1MB', '500KB', '1024' into bytes."""
    text = str(text).strip().upper()
    # Check longer suffixes first: "1MB" ends with "B" too, so "B" must come last.
    multipliers = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3,
                   "TB": 1024 ** 4, "B": 1}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[: -len(suffix)]) * mult)
            except ValueError:
                raise argparse.ArgumentTypeError(f"Bad size: {text!r}")
    try:
        return int(float(text))
    except ValueError:
        raise argparse.ArgumentTypeError(f"Bad size: {text!r}")


def scan(root, excludes, max_depth, min_size):
    """Walk the tree once and collect everything we need.

    Returns a dict with totals, biggest files, per-folder sizes,
    per-extension stats, age buckets, and error counts.
    Uses os.scandir (fast) and skips unreadable entries instead of crashing.
    """
    root = Path(root)
    biggest_files = []          # (size, path) — kept trimmed to a few hundred
    folder_sizes = defaultdict(int)
    folder_counts = Counter()
    ext_stats = defaultdict(lambda: {"count": 0, "size": 0})
    age_stats = defaultdict(lambda: {"count": 0, "size": 0})
    now = datetime.now().timestamp()

    total_size = 0
    total_files = 0
    total_folders = 0
    errors = 0
    skipped_small = 0

    def record_age(size, mtime):
        age_days = (now - mtime) / 86400
        for label, low, high in AGE_BUCKETS:
            if age_days >= low and (high is None or age_days <= high):
                age_stats[label]["count"] += 1
                age_stats[label]["size"] += size
                return

    def walk(directory, depth):
        nonlocal total_size, total_files, total_folders, errors, skipped_small
        try:
            entries = list(os.scandir(directory))
        except (PermissionError, OSError):
            errors += 1
            return
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in excludes:
                        continue
                    if max_depth is not None and depth >= max_depth:
                        continue
                    total_folders += 1
                    walk(entry.path, depth + 1)
                elif entry.is_file(follow_symlinks=False):
                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        errors += 1
                        continue
                    if stat.st_size < min_size:
                        skipped_small += 1
                        continue
                    total_files += 1
                    total_size += stat.st_size
                    biggest_files.append((stat.st_size, entry.path))
                    # Credit every ancestor folder up to the scanned root.
                    rel = Path(entry.path).relative_to(root)
                    for parent in rel.parents:
                        folder_sizes[str(root / parent)] += stat.st_size
                        folder_counts[str(root / parent)] += 1
                    ext = Path(entry.name).suffix.lower() or "(no extension)"
                    ext_stats[ext]["count"] += 1
                    ext_stats[ext]["size"] += stat.st_size
                    record_age(stat.st_size, stat.st_mtime)
            except OSError:
                errors += 1

    walk(str(root), 0)
    biggest_files.sort(key=lambda item: item[0], reverse=True)
    return {
        "total_size": total_size,
        "total_files": total_files,
        "total_folders": total_folders,
        "errors": errors,
        "skipped_small": skipped_small,
        "biggest_files": biggest_files,
        "folder_sizes": folder_sizes,
        "folder_counts": folder_counts,
        "ext_stats": ext_stats,
        "age_stats": age_stats,
    }


def bar_chart(items, max_width=40):
    """Simple text bar chart: [(label, size), ...] -> list of lines."""
    if not items:
        return []
    top_size = max(size for _, size in items)
    lines = []
    for label, size in items:
        width = int(size / top_size * max_width) if top_size else 0
        lines.append(f"  {'#' * width:<{max_width}} {human_size(size):>10}  {label}")
    return lines


def build_report(root, results, top_n):
    """Shape the scan results into a JSON-friendly report dict."""
    folder_rank = sorted(
        results["folder_sizes"].items(), key=lambda kv: kv[1], reverse=True
    )[:top_n]
    ext_rank = sorted(
        results["ext_stats"].items(), key=lambda kv: kv[1]["size"], reverse=True
    )
    return {
        "scanned": str(root),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_size_bytes": results["total_size"],
        "total_size": human_size(results["total_size"]),
        "total_files": results["total_files"],
        "total_folders": results["total_folders"],
        "unreadable_entries": results["errors"],
        "top_files": [
            {"path": path, "size_bytes": size, "size": human_size(size)}
            for size, path in results["biggest_files"][:top_n]
        ],
        "top_folders": [
            {
                "path": path,
                "size_bytes": size,
                "size": human_size(size),
                "files": results["folder_counts"][path],
            }
            for path, size in folder_rank
        ],
        "by_extension": [
            {
                "extension": ext,
                "files": data["count"],
                "size_bytes": data["size"],
                "size": human_size(data["size"]),
            }
            for ext, data in ext_rank
        ],
        "by_age": [
            {
                "bucket": label,
                "files": data["count"],
                "size_bytes": data["size"],
                "size": human_size(data["size"]),
            }
            for label, data in sorted(
                results["age_stats"].items(),
                key=lambda kv: kv[1]["size"],
                reverse=True,
            )
        ],
    }


def print_report(root, results, report, top_n):
    """Print the human-readable console report."""
    print(f"\nDisk usage: {root}")
    print("=" * 60)
    print(f"  Total size:    {human_size(results['total_size'])}")
    print(f"  Files:         {results['total_files']:,}")
    print(f"  Folders:       {results['total_folders']:,}")
    if results["errors"]:
        print(f"  Unreadable:    {results['errors']} entries skipped (permissions)")
    if results["skipped_small"]:
        print(f"  Below min-size: {results['skipped_small']} files skipped")

    # Drive free space for the scanned location (shutil.disk_usage).
    try:
        import shutil

        total, used, free = shutil.disk_usage(str(root))
        pct_free = free / total * 100 if total else 0
        print(
            f"  Drive:         {human_size(free)} free of {human_size(total)} "
            f"({pct_free:.1f}% free)"
        )
    except OSError:
        pass

    print(f"\nTop {top_n} biggest folders:")
    top_folders = [(path, size) for path, size in
                   sorted(results["folder_sizes"].items(),
                          key=lambda kv: kv[1], reverse=True)[:top_n]]
    for line in bar_chart(top_folders):
        print(line)
    if not top_folders:
        print("  (none)")

    print(f"\nTop {top_n} biggest files:")
    for size, path in results["biggest_files"][:top_n]:
        print(f"  {human_size(size):>10}  {path}")
    if not results["biggest_files"]:
        print("  (none)")

    print("\nSpace by file type:")
    for item in report["by_extension"][:10]:
        pct = item["size_bytes"] / results["total_size"] * 100 if results["total_size"] else 0
        print(f"  {item['extension']:<14} {item['files']:>6,} files  "
              f"{item['size']:>10}  ({pct:5.1f}%)")

    print("\nSpace by file age:")
    for item in report["by_age"]:
        print(f"  {item['bucket']:<20} {item['files']:>6,} files  {item['size']:>10}")

    stale = next(
        (item for item in report["by_age"] if "stale" in item["bucket"]), None
    )
    if stale and stale["size_bytes"]:
        print(
            f"\nCleanup hint: {stale['size']} sits in files untouched for over "
            f"a year — review those before deleting anything."
        )
    print()


def write_json(report, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"JSON report written to {path}")


def write_csv(results, path, top_n):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rank", "size_bytes", "size", "path"])
        for rank, (size, file_path) in enumerate(
            results["biggest_files"][:top_n], start=1
        ):
            writer.writerow([rank, size, human_size(size), file_path])
    print(f"CSV written to {path}")


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.path)

    if not root.exists():
        print(f"Error: {root} does not exist.", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"Error: {root} is not a folder.", file=sys.stderr)
        return 1

    excludes = set(args.exclude)
    if not args.no_default_excludes:
        excludes |= DEFAULT_EXCLUDES

    try:
        min_size = parse_size(args.min_size)
    except argparse.ArgumentTypeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Scanning {root} ...")
    results = scan(root, excludes, args.depth, min_size)
    report = build_report(root, results, args.top)
    print_report(root, results, report, args.top)

    if args.json:
        write_json(report, args.json)
    if args.csv:
        write_csv(results, args.csv, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
