#!/usr/bin/env python3
"""
bulk_rename.py — Bulk file renamer with dry-run by default and an undo log.

Rename dozens of files in one shot without the fear: every run shows a
preview first, refuses to overwrite anything, and writes an undo log so a
bad rename is one command away from being reversed.

What it does
------------
Applies any combination of these transforms, in this order:

  1. Find & replace        (--find / --replace, optional --regex)
  2. Case                  (--case lower | upper | title)
  3. Spaces                (--spaces-to _  or  -)
  4. Date prefix           (--date mtime | today  ->  2026-11-12_name.ext)
  5. Numbering             (--number, optional --number-start / --number-pad)
  6. Prefix / suffix       (--prefix / --suffix)

Safety rules (these never change):
  * DRY-RUN IS THE DEFAULT. Nothing is renamed until you pass --apply.
  * A rename that would overwrite an existing file is skipped, never forced.
  * Two files landing on the same new name are both skipped.
  * Every --apply run writes a JSON undo log; --undo <log> reverses it.
  * Renames happen in two phases (temp name, then final name) so swaps
    like a.txt -> b.txt and b.txt -> a.txt work instead of clobbering.

Usage
-----
  python bulk_rename.py FOLDER [options]

Examples
--------
  # Preview: replace spaces with underscores in every .jpg in a folder
  python bulk_rename.py ~/Photos --pattern "*.jpg" --spaces-to _

  # Actually do it (same command, plus --apply)
  python bulk_rename.py ~/Photos --pattern "*.jpg" --spaces-to _ --apply

  # Number a photo set: IMG_001.jpg, IMG_002.jpg, ...
  python bulk_rename.py ~/Photos --pattern "IMG*.jpg" --find "IMG" --replace "IMG_" \\
      --number --number-start 1 --number-pad 3 --apply

  # Clean up messy downloads: lowercase everything, date-prefix by file date
  python bulk_rename.py ~/Downloads --case lower --date mtime --apply

  # Undo the last run
  python bulk_rename.py --undo .bulk-rename-undo-20261112-212000.json

  # Recursive, regex find/replace: strip " (1)", " (2)" copy suffixes
  python bulk_rename.py ~/Docs --recursive --regex \\
      --find " \\(\\d+\\)$" --replace "" --apply

Python 3.8+; standard library only — nothing to install.
Cross-platform: Windows PowerShell, macOS, Linux, Termux.
"""

import argparse
import json
import re
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

VERSION = "1.0.0"
UNDO_PREFIX = ".bulk-rename-undo-"


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        description="Bulk file renamer — dry-run by default, undo log on every real run.",
        epilog="Nothing is renamed without --apply. See README.md for the full guide.",
    )
    p.add_argument("folder", nargs="?", help="Folder containing the files to rename")
    p.add_argument("--pattern", default="*",
                   help='Filename glob to match (default: *). Example: "*.jpg"')
    p.add_argument("--recursive", action="store_true",
                   help="Also rename files in subfolders")
    p.add_argument("--include-dirs", action="store_true",
                   help="Rename directories too (default: files only)")

    p.add_argument("--find", default=None, help="Text to find in the filename")
    p.add_argument("--replace", default="", help="Replacement text (default: empty)")
    p.add_argument("--regex", action="store_true",
                   help="Treat --find as a regular expression")
    p.add_argument("--case", choices=["lower", "upper", "title"], default=None,
                   help="Change the case of the filename stem")
    p.add_argument("--spaces-to", choices=["_", "-"], default=None,
                   help="Replace every space with _ or -")
    p.add_argument("--date", choices=["mtime", "today"], default=None,
                   help="Prefix YYYY-MM-DD from the file's modified date, or today")
    p.add_argument("--number", action="store_true",
                   help="Append a counter before the extension (001, 002, ...)")
    p.add_argument("--number-start", type=int, default=1,
                   help="First counter value (default: 1)")
    p.add_argument("--number-pad", type=int, default=3,
                   help="Zero-padding width for the counter (default: 3)")
    p.add_argument("--number-sep", default="_",
                   help='Separator between name and counter (default: "_")')
    p.add_argument("--prefix", default="", help="Text to add at the start of the name")
    p.add_argument("--suffix", default="", help="Text to add at the end of the stem")

    p.add_argument("--apply", action="store_true",
                   help="Actually rename (without this, only a preview is shown)")
    p.add_argument("--undo-log", default=None,
                   help="Where to write the undo log (default: in the target folder)")
    p.add_argument("--undo", metavar="LOGFILE",
                   help="Reverse a previous run using its undo log")
    p.add_argument("--version", action="version", version=f"bulk_rename {VERSION}")
    return p


# --------------------------------------------------------------------------
# Name transforms
# --------------------------------------------------------------------------
def apply_transforms(stem, ext, args, counter):
    """Run one filename stem through every requested transform, in order."""
    name = stem

    # 1. Find & replace (plain text or regex)
    if args.find is not None:
        if args.regex:
            name = re.sub(args.find, args.replace, name)
        else:
            name = name.replace(args.find, args.replace)

    # 2. Case
    if args.case == "lower":
        name = name.lower()
    elif args.case == "upper":
        name = name.upper()
    elif args.case == "title":
        name = name.title()

    # 3. Spaces
    if args.spaces_to:
        name = name.replace(" ", args.spaces_to)

    return name


def build_new_name(path, args, counter):
    """Compute the new filename for one path, or None if it must be skipped."""
    stem, ext = path.stem, path.suffix
    name = apply_transforms(stem, ext, args, counter)

    # 4. Date prefix
    if args.date == "mtime":
        stamp = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        name = f"{stamp}_{name}"
    elif args.date == "today":
        name = f"{date.today().isoformat()}_{name}"

    # 5. Numbering (counter appended to the stem, before the extension)
    if args.number:
        name = f"{name}{args.number_sep}{counter:0{args.number_pad}d}"

    # 6. Prefix / suffix
    name = f"{args.prefix}{name}{args.suffix}"

    if not name.strip():
        return None  # A transform wiped the whole name out
    return name + ext


# --------------------------------------------------------------------------
# Collecting and planning
# --------------------------------------------------------------------------
def collect_files(folder, args):
    """Return the sorted list of paths to consider."""
    if args.recursive:
        paths = folder.rglob(args.pattern)
    else:
        paths = folder.glob(args.pattern)
    out = []
    for p in paths:
        if p.name.startswith(UNDO_PREFIX):
            continue  # Never rename our own undo logs
        if p.is_dir() and not args.include_dirs:
            continue
        if p.is_file() or (args.include_dirs and p.is_dir()):
            out.append(p)
    return sorted(out)


def plan_renames(paths, args):
    """
    Work out old -> new for every path.
    Returns (plan, skipped) where plan is a list of (old_path, new_path)
    and skipped is a list of (path, reason).
    """
    plan, skipped = [], []
    counter = args.number_start
    new_names = {}  # new filename (lowercased) -> source path, for collision checks

    for path in paths:
        new_name = build_new_name(path, args, counter)
        if args.number:
            counter += 1
        if new_name is None:
            skipped.append((path, "transform left an empty name"))
            continue
        if new_name == path.name:
            skipped.append((path, "no change"))
            continue

        key = new_name.lower()
        if key in new_names:
            # Two files would land on the same name: skip both.
            other = new_names.pop(key)
            skipped.append((other, f"collides with {path.name}"))
            skipped.append((path, f"collides with {other.name}"))
            continue
        new_names[key] = path
        plan.append((path, path.with_name(new_name)))

    # Drop plan entries that were retroactively skipped by a collision.
    skipped_paths = {p for p, _ in skipped}
    plan = [(o, n) for o, n in plan if o not in skipped_paths]

    # Existence check, run to a fixpoint: a target is only safe if it is
    # itself being renamed away in the final plan. Removing one entry can
    # make another entry unsafe (its target stops moving), so repeat until
    # nothing changes.
    changed = True
    while changed:
        changed = False
        sources = {old for old, _ in plan}
        kept = []
        for old, new in plan:
            if new.exists() and new not in sources:
                skipped.append((old, f"'{new.name}' already exists"))
                changed = True
            else:
                kept.append((old, new))
        plan = kept

    return plan, skipped


# --------------------------------------------------------------------------
# Executing (two-phase, so swaps are safe) and undo
# --------------------------------------------------------------------------
def execute_plan(plan):
    """Rename via unique temp names first, then to the final names."""
    temp_map = {}  # temp path -> (original path, final path)
    for old, new in plan:
        temp = old.with_name(f".bulkrename-tmp-{uuid.uuid4().hex}{old.suffix}")
        old.rename(temp)
        temp_map[temp] = (old, new)
    done = []
    for temp, (old, new) in temp_map.items():
        temp.rename(new)
        done.append((old, new))
    return done


def write_undo_log(folder, args, done):
    """Record old -> new pairs so the run can be reversed."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = Path(args.undo_log) if args.undo_log else \
        folder / f"{UNDO_PREFIX}{stamp}.json"
    entries = [{"old": str(old), "new": str(new)} for old, new in done]
    log_path.write_text(json.dumps({"tool": "bulk_rename", "version": VERSION,
                                    "renames": entries}, indent=2),
                        encoding="utf-8")
    return log_path


def run_undo(log_path):
    """Reverse a previous run from its undo log."""
    data = json.loads(Path(log_path).read_text(encoding="utf-8"))
    entries = data.get("renames", [])
    plan, skipped = [], []
    for entry in entries:
        new, old = Path(entry["new"]), Path(entry["old"])
        if not new.exists():
            skipped.append((new, "already gone — nothing to undo"))
        elif old.exists():
            skipped.append((new, f"'{old.name}' already exists at the old location"))
        else:
            plan.append((new, old))
    done = execute_plan(plan)
    return done, skipped, len(entries)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def show_preview(plan, skipped):
    width = max((len(o.name) for o, _ in plan), default=10)
    print(f"\n{'OLD NAME':<{width}}  ->  NEW NAME")
    print("-" * (width + 8 + 40))
    for old, new in plan:
        print(f"{old.name:<{width}}  ->  {new.name}")
    for path, reason in skipped:
        print(f"{path.name:<{width}}  --  SKIPPED: {reason}")
    print()
    print(f"{len(plan)} file(s) would be renamed, {len(skipped)} skipped.")
    if plan:
        print("Run the same command with --apply to do it for real.")


def main(argv=None):
    args = build_parser().parse_args(argv)

    # ---- Undo mode ------------------------------------------------------
    if args.undo:
        done, skipped, total = run_undo(args.undo)
        print(f"\nUndo: {len(done)} of {total} rename(s) reversed.")
        for path, reason in skipped:
            print(f"  SKIPPED {path.name}: {reason}")
        return 0

    if not args.folder:
        print("Error: give a folder, or use --undo LOGFILE to reverse a run.",
              file=sys.stderr)
        return 2
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"Error: '{folder}' is not a folder.", file=sys.stderr)
        return 2
    if args.find is None and not any([args.case, args.spaces_to, args.date,
                                      args.number, args.prefix, args.suffix]):
        print("Error: nothing to do — pick at least one transform "
              "(--find, --case, --spaces-to, --date, --number, --prefix, --suffix).",
              file=sys.stderr)
        return 2

    paths = collect_files(folder, args)
    if not paths:
        print(f"No files matching '{args.pattern}' in {folder}.")
        return 0

    plan, skipped = plan_renames(paths, args)
    if not plan and not skipped:
        print("Nothing matched.")
        return 0

    if not args.apply:
        show_preview(plan, skipped)
        return 0

    done = execute_plan(plan)
    if done:
        log_path = write_undo_log(folder, args, done)
    print(f"\nRenamed {len(done)} file(s), {len(skipped)} skipped.")
    for path, reason in skipped:
        print(f"  SKIPPED {path.name}: {reason}")
    if done:
        print(f"Undo log: {log_path}")
        print(f"To reverse this run: python bulk_rename.py --undo \"{log_path}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
