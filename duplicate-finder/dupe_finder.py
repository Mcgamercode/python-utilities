#!/usr/bin/env python3
"""
dupe_finder.py — find true duplicate files by content and quarantine the extras.

Why this exists
---------------
Mike's 256 GB flash drive had piles of duplicate videos exported from his
old computer. Paid duplicate finders (Duplicate Cleaner Pro, ~$40-55 for a
lifetime license) do exactly this: compare files by CONTENT, not by name.

How it works
------------
1. Walk the folder and group files by SIZE first (cheap — nothing is read).
2. For files with the same size, hash the first 64 KB (fast filter).
3. Only if the first chunk matches, hash the whole file with SHA-256.
   SHA-256 comes from hashlib — two files with the same SHA-256 are the
   same file, for all practical purposes.
4. Report the duplicate groups. NOTHING moves or deletes by default.
   With --quarantine, all but one copy of each group moves into a
   _duplicates/ review folder (same relative layout), so you can check
   before you delete anything. A JSON report and a restore script are
   written next to it, so the whole thing is reversible.

Usage
-----
  python dupe_finder.py D:\\FlashDrive
  python dupe_finder.py ~/storage --min-size 10MB
  python dupe_finder.py ~/storage --quarantine

Safety: never deletes. Quarantine only moves files; the report lists
exactly what moved and where it came from, so you can undo it.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

CHUNK = 64 * 1024          # 64 KB first-chunk hash
FULL_READ = 1024 * 1024    # 1 MB reads for the full hash


def parse_size(text):
    """'10MB', '500KB', '1024' -> bytes."""
    text = text.strip().upper()
    mult = {"GB": 1024 ** 3, "MB": 1024 ** 2, "KB": 1024, "B": 1}
    # longest suffix first — "1MB" must match "MB", not "B"
    for suffix in sorted(mult, key=len, reverse=True):
        if text.endswith(suffix):
            return int(float(text[: -len(suffix)]) * mult[suffix])
    return int(text)


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def iter_files(root, skip_dir):
    """Yield every regular file under root, skipping the quarantine dir."""
    for dirpath, dirnames, filenames in os.walk(root):
        # don't descend into the quarantine folder itself
        dirnames[:] = [d for d in dirnames
                       if (Path(dirpath) / d).resolve() != skip_dir.resolve()]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            try:
                if p.is_file():
                    yield p
            except OSError:
                continue


def hash_prefix(path, n=CHUNK):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(n))
    return h.hexdigest()


def hash_full(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(FULL_READ)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def find_duplicates(root, min_size):
    """Return a list of duplicate groups (each a list of Paths, sorted)."""
    by_size = defaultdict(list)
    scanned = 0
    for p in iter_files(root, root / "_duplicates"):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        scanned += 1
        if size >= min_size:
            by_size[size].append(p)

    groups = []
    for size, files in by_size.items():
        if len(files) < 2:
            continue
        # stage 2: first-64KB hash
        by_prefix = defaultdict(list)
        for p in files:
            try:
                by_prefix[hash_prefix(p)].append(p)
            except OSError:
                continue
        for same_prefix in by_prefix.values():
            if len(same_prefix) < 2:
                continue
            # stage 3: full SHA-256 — only for real candidates
            by_full = defaultdict(list)
            for p in same_prefix:
                try:
                    by_full[hash_full(p)].append(p)
                except OSError:
                    continue
            for same_full in by_full.values():
                if len(same_full) > 1:
                    groups.append(sorted(same_full))
    return scanned, groups


def quarantine(groups, root):
    """Move all but the first file of each group into _duplicates/.

    Returns a list of (moved_from, moved_to) pairs.
    """
    qdir = root / "_duplicates"
    qdir.mkdir(exist_ok=True)
    moved = []
    for group in groups:
        keep = group[0]  # deterministic: alphabetically first path stays
        for extra in group[1:]:
            rel = extra.relative_to(root)
            dest = qdir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():  # same relative path already quarantined
                stem, suffix = dest.stem, dest.suffix
                i = 2
                while True:
                    alt = dest.parent / f"{stem} ({i}){suffix}"
                    if not alt.exists():
                        dest = alt
                        break
                    i += 1
            shutil.move(str(extra), str(dest))
            moved.append((str(extra), str(dest)))
    return moved


def write_restore_script(qdir, moved):
    """Write a small script that moves everything back. Reversible by design."""
    lines = [
        "#!/usr/bin/env python3",
        '"""Restore files moved by dupe_finder.py --quarantine."""',
        "import shutil",
        "from pathlib import Path",
        "",
        "MOVED = [",
    ]
    for src, dst in moved:
        lines.append(f"    ({src!r}, {dst!r}),")
    lines += [
        "]",
        "",
        "for src, dst in MOVED:",
        "    Path(src).parent.mkdir(parents=True, exist_ok=True)",
        "    shutil.move(dst, src)",
        'print(f"Restored {len(MOVED)} files.")',
        "",
    ]
    script = qdir / "restore_duplicates.py"
    script.write_text("\n".join(lines))
    return script


def main():
    ap = argparse.ArgumentParser(
        description="Find duplicate files by content; quarantine extras (never deletes).")
    ap.add_argument("folder", help="folder to scan (e.g. D:\\FlashDrive or ~/storage)")
    ap.add_argument("--min-size", default="1MB",
                    help="ignore files smaller than this (default: 1MB)")
    ap.add_argument("--quarantine", action="store_true",
                    help="move extras into <folder>/_duplicates/ (default: report only)")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a folder: {root}", file=sys.stderr)
        return 2

    min_size = parse_size(args.min_size)
    print(f"Scanning {root} (files >= {fmt_bytes(min_size)}) ...")
    scanned, groups = find_duplicates(root, min_size)

    dup_files = sum(len(g) - 1 for g in groups)
    dup_bytes = sum(g[0].stat().st_size * (len(g) - 1) for g in groups)

    print(f"\nScanned {scanned} files. Found {len(groups)} duplicate "
          f"{'group' if len(groups) == 1 else 'groups'} "
          f"({dup_files} extra copies, {fmt_bytes(dup_bytes)} reclaimable).")

    for i, g in enumerate(groups, 1):
        print(f"\nGroup {i} — {len(g)} copies, {fmt_bytes(g[0].stat().st_size)} each:")
        for p in g:
            mark = "KEEP" if p == g[0] else "    "
            print(f"  [{mark}] {p}")

    report = {
        "folder": str(root),
        "min_size_bytes": min_size,
        "scanned_files": scanned,
        "groups": [[str(p) for p in g] for g in groups],
        "extra_copies": dup_files,
        "reclaimable_bytes": dup_bytes,
        "moved": [],
    }

    if args.quarantine and groups:
        moved = quarantine(groups, root)
        report["moved"] = [{"from": s, "to": d} for s, d in moved]
        script = write_restore_script(root / "_duplicates", moved)
        print(f"\nMoved {len(moved)} files to {root / '_duplicates'}")
        print(f"Restore anytime with:  python {script}")
    elif groups:
        print("\nDry run — nothing moved. Add --quarantine to move the extras "
              "into _duplicates/ for review.")

    report_path = root / "dupe_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
