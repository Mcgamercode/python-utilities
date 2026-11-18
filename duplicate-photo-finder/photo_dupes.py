#!/usr/bin/env python3
"""Duplicate-photo finder — tool #14 of the nightly Python series.

Finds NEAR-duplicate photos: the same picture saved at a different size,
re-compressed as a JPEG, brightened, or lightly cropped. Byte-identical
matching (tool #1, duplicate-finder) misses all of those — this one looks
at what the picture *shows*, not at its bytes.

How: a perceptual hash. Each photo is shrunk to a tiny 8x8 grayscale grid
and reduced to 64 yes/no answers ("is this pixel brighter than average?").
Two versions of the same photo give nearly the same 64 answers; two
different photos don't. Photos whose hashes differ in only a few bits are
a match. That is the whole trick — about 30 lines of code below.

Safety: default mode only REPORTS. Nothing moves or deletes unless you
pass --move, and --move only moves extras into a _photo_dupes/ review
folder (plus a restore script that puts them all back). Nothing is ever
deleted.

Needs: Pillow — one install:  pip install pillow
Stdlib: argparse, csv, hashlib, json, pathlib, shutil, sys.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:  # Pillow is the one real dependency — say so plainly.
    print("This tool needs Pillow:  pip install pillow", file=sys.stderr)
    sys.exit(2)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
HASH_SIZE = 8                      # 8x8 grid -> 64-bit hash
DEFAULT_THRESHOLD = 5              # max differing bits that still counts as a match
REVIEW_DIRNAME = "_photo_dupes"    # where --move puts the extras


# ---------------------------------------------------------------- hashes
def ahash(img: Image.Image) -> int:
    """Average hash: 1 bit per cell — brighter than the image average, or not."""
    small = img.convert("L").resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
    px = list(small.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits


def dhash(img: Image.Image) -> int:
    """Difference hash: 1 bit per cell — brighter than the cell to its right, or not.

    dHash is the better default: it keys on edges/gradients instead of overall
    brightness, so a brightened or darkened copy still matches.
    """
    small = img.convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(HASH_SIZE):
        for col in range(HASH_SIZE):
            left = px[row * (HASH_SIZE + 1) + col]
            right = px[row * (HASH_SIZE + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a: int, b: int) -> int:
    """How many bits differ between two hashes (0 = identical picture)."""
    return bin(a ^ b).count("1")


def file_sha256(path: Path) -> str:
    """Full-file hash, for the exact-duplicate fast path."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- scanning
def parse_size(text: str) -> int:
    """'10KB' / '2MB' / '500' -> bytes."""
    text = text.strip().upper()
    for suffix, mult in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)):
        if text.endswith(suffix):
            return int(float(text[: -len(suffix)]) * mult)
    return int(text)


def find_images(folders: list[Path], recursive: bool, min_size: int) -> list[Path]:
    """Walk the folder(s) and collect image files, skipping review folders."""
    found: list[Path] = []
    for folder in folders:
        if not folder.is_dir():
            print(f"Skipping (not a folder): {folder}", file=sys.stderr)
            continue
        it = folder.rglob("*") if recursive else folder.glob("*")
        for p in it:
            if REVIEW_DIRNAME in p.parts:
                continue  # never scan a previous run's review folder
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.stat().st_size >= min_size:
                found.append(p)
    return sorted(found)


def hash_photo(path: Path) -> dict | None:
    """Hash one photo. Returns None (with a warning) for unreadable files."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)  # honour phone rotation tags
            width, height = img.size
            return {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "width": width,
                "height": height,
                "pixels": width * height,
                "ahash": ahash(img),
                "dhash": dhash(img),
                "sha256": None,  # filled in only for same-size candidates
            }
    except Exception as exc:  # corrupt file, truncated download, etc.
        print(f"Warning: could not read {path} ({exc})", file=sys.stderr)
        return None


def photo_distance(a: dict, b: dict, mode: str) -> int:
    """Smallest hash distance under the chosen mode ('both' = either hash may match)."""
    if mode == "ahash":
        return hamming(a["ahash"], b["ahash"])
    if mode == "dhash":
        return hamming(a["dhash"], b["dhash"])
    return min(hamming(a["ahash"], b["ahash"]), hamming(a["dhash"], b["dhash"]))


class UnionFind:
    """Groups photos that match, transitively: A~B and B~C puts all three together."""

    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def group_photos(photos: list[dict], threshold: int, mode: str) -> list[list[dict]]:
    """Exact groups first (same size + same SHA-256), then perceptual groups.

    Exact check is cheap and certain; perceptual check is O(n^2) pairwise,
    which is fine for a personal library (hundreds to a few thousand photos)
    and the honest limit of this tool — a 50k-photo archive wants a database.
    """
    n = len(photos)
    uf = UnionFind(n)

    # Exact duplicates: same byte size first (free filter), then SHA-256.
    by_size: dict[int, list[int]] = {}
    for i, p in enumerate(photos):
        by_size.setdefault(p["size_bytes"], []).append(i)
    for idxs in by_size.values():
        if len(idxs) < 2:
            continue
        by_hash: dict[str, list[int]] = {}
        for i in idxs:
            photos[i]["sha256"] = file_sha256(Path(photos[i]["path"]))
            by_hash.setdefault(photos[i]["sha256"], []).append(i)
        for group in by_hash.values():
            for j in group[1:]:
                uf.union(group[0], j)

    # Near duplicates: perceptual hash within the threshold.
    for i in range(n):
        for j in range(i + 1, n):
            if uf.find(i) == uf.find(j):
                continue
            if photo_distance(photos[i], photos[j], mode) <= threshold:
                uf.union(i, j)

    groups: dict[int, list[dict]] = {}
    for i, p in enumerate(photos):
        groups.setdefault(uf.find(i), []).append(p)
    return [g for g in groups.values() if len(g) > 1]


LOSSLESS_EXTS = {".png", ".tif", ".tiff", ".bmp"}  # preferred keepers at equal resolution


def pick_keeper(group: list[dict]) -> dict:
    """The copy to keep: most pixels, then a lossless original over a lossy
    re-save, then biggest file, then shortest path.

    Lossless-before-size matters: a low-quality JPEG re-save can be BIGGER
    than the PNG original (noisy gradients compress badly), so size alone
    would keep the worst copy.
    """
    def key(p: dict):
        lossless = 0 if Path(p["path"]).suffix.lower() in LOSSLESS_EXTS else 1
        return (-p["pixels"], lossless, -p["size_bytes"], p["path"])

    return sorted(group, key=key)[0]


# ---------------------------------------------------------------- reporting
def write_reports(photos: list[dict], groups: list[list[dict]], outdir: Path) -> tuple[Path, Path]:
    """JSON (full detail, machine-readable) + CSV (one row per extra copy)."""
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "photo_dupes_report.json"
    csv_path = outdir / "photo_dupes_report.csv"
    report = {
        "photos_scanned": len(photos),
        "groups_found": len(groups),
        "photos_in_groups": sum(len(g) for g in groups),
        "reclaimable_bytes": sum(
            p["size_bytes"] for g in groups for p in g if p is not pick_keeper(g)
        ),
        "groups": [
            {
                "keeper": pick_keeper(g)["path"],
                "extras": [p["path"] for p in g if p is not pick_keeper(g)],
                "members": [
                    {"path": p["path"], "size_bytes": p["size_bytes"],
                     "width": p["width"], "height": p["height"]} for p in g
                ],
            }
            for g in groups
        ],
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "action", "path", "size_bytes", "width", "height"])
        for gi, g in enumerate(groups, 1):
            keeper = pick_keeper(g)
            for p in g:
                w.writerow([gi, "KEEP" if p is keeper else "REVIEW",
                            p["path"], p["size_bytes"], p["width"], p["height"]])
    return json_path, csv_path


def write_restore_script(moved: list[tuple[Path, Path]], script_path: Path) -> None:
    """A tiny script that moves every reviewed file back where it came from."""
    lines = [
        "#!/usr/bin/env python3",
        '"""Restore photos moved by photo_dupes.py --move. Run:  python restore_photos.py"""',
        "import shutil",
        "from pathlib import Path",
        "",
        "MOVED = [",
    ]
    for dest, src in moved:
        lines.append(f"    ({str(dest)!r}, {str(src)!r}),")
    lines += [
        "]",
        "",
        "for dest, src in MOVED:",
        "    dest, src = Path(dest), Path(src)",
        "    src.parent.mkdir(parents=True, exist_ok=True)",
        "    shutil.move(str(dest), str(src))",
        '    print(f"Restored {src}")',
        "",
    ]
    script_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Find near-duplicate photos by perceptual hash. Report only, unless --move."
    )
    ap.add_argument("folders", nargs="+", type=Path, help="Folder(s) to scan for photos")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help=f"Max hash bits that may differ and still match (default {DEFAULT_THRESHOLD}; "
                         "0 = identical look, 5 = resize/recompress, 10 = loose, burst shots may match)")
    ap.add_argument("--hash", dest="mode", choices=["ahash", "dhash", "both"], default="dhash",
                    help="Which perceptual hash to use (default dhash — handles brightness changes)")
    ap.add_argument("--min-size", default="1KB",
                    help="Ignore files smaller than this, e.g. 10KB (default 1KB)")
    ap.add_argument("--no-recursive", action="store_true", help="Don't descend into subfolders")
    ap.add_argument("--report-dir", type=Path, default=Path("."),
                    help="Where to write photo_dupes_report.json/.csv (default: current folder)")
    ap.add_argument("--move", action="store_true",
                    help="Move extra copies into <folder>/_photo_dupes/ (never deletes). "
                         "Writes restore_photos.py next to the reports.")
    args = ap.parse_args(argv)

    min_size = parse_size(args.min_size)
    photos_found = find_images(args.folders, not args.no_recursive, min_size)
    print(f"Found {len(photos_found)} image files. Hashing...")
    photos = [p for p in (hash_photo(f) for f in photos_found) if p is not None]
    skipped = len(photos_found) - len(photos)
    if skipped:
        print(f"Skipped {skipped} unreadable file(s) — see warnings above.")

    groups = group_photos(photos, args.threshold, args.mode)
    extras = sum(len(g) - 1 for g in groups)
    reclaim = sum(p["size_bytes"] for g in groups for p in g if p is not pick_keeper(g))
    print(f"\n{len(groups)} duplicate group(s), {extras} extra copie(s), "
          f"~{reclaim / 1024 / 1024:.1f} MB reclaimable.")
    for gi, g in enumerate(groups, 1):
        keeper = pick_keeper(g)
        print(f"\nGroup {gi} ({len(g)} copies) — KEEP: {keeper['path']} "
              f"({keeper['width']}x{keeper['height']}, {keeper['size_bytes'] // 1024} KB)")
        for p in g:
            if p is not keeper:
                print(f"    review: {p['path']} ({p['width']}x{p['height']}, "
                      f"{p['size_bytes'] // 1024} KB)")

    json_path, csv_path = write_reports(photos, groups, args.report_dir)
    print(f"\nReports: {json_path}  +  {csv_path}")

    if args.move and groups:
        moved: list[tuple[Path, Path]] = []
        for g in groups:
            keeper = pick_keeper(g)
            for p in g:
                if p is keeper:
                    continue
                src = Path(p["path"])
                # Keep the folder layout inside the review folder, per source folder.
                base = next((f for f in args.folders if src.is_relative_to(f)), src.parent)
                dest = base / REVIEW_DIRNAME / src.relative_to(base)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                moved.append((dest, src))
                print(f"Moved to review: {src} -> {dest}")
        script_path = args.report_dir / "restore_photos.py"
        write_restore_script(moved, script_path)
        print(f"\nMoved {len(moved)} file(s). Nothing deleted. "
              f"Undo any time with:  python {script_path}")
    elif args.move:
        print("\nNothing to move.")
    else:
        print("\nDry run — nothing moved. Add --move to send extras to _photo_dupes/ "
              "for review (with a restore script).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
