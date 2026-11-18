# Duplicate-Photo Finder — Tool #14 of the Nightly Python Series

Finds **near-duplicate photos** — the same picture saved at a different
size, re-compressed as a JPEG, or brightened. (Light crops match too, at a
looser threshold — see "Honest limits".) Byte-identical
matching (tool #1, duplicate-finder) misses all of those, because the files
are different even though the picture is the same. This one looks at what
the picture *shows*, not at its bytes.

## What it replaces

**Duplicate Photo Cleaner** (WebMinds) — **$39.95 for a 1-computer,
1-year license** (list $49.95), verified Nov 17, 2026 from the
lapphotos.com comparison roundup ("prices checked on each vendor's official
page in November 2026") and the cisdem.com review of the same product.
Your version: $0, and you own the code.

## Run it

Install the one library first (once):

```bash
pip install pillow
```

Windows PowerShell:

```powershell
python photo_dupes.py D:\Photos
python photo_dupes.py D:\Photos --threshold 8 --move
```

Termux / Linux:

```bash
python3 photo_dupes.py ~/storage/DCIM
python3 photo_dupes.py ~/storage/DCIM --threshold 8 --move
```

Default mode is a **dry run**: it prints the groups and writes
`photo_dupes_report.json` + `photo_dupes_report.csv`, and moves nothing.
Add `--move` to send the extra copies into a `_photo_dupes/` review
folder (your folder layout kept intact) plus a `restore_photos.py`
that puts them all back. **Nothing is ever deleted.**

## How it works (the Python lesson)

- **Pillow (`PIL`)** — opens every image format (JPEG, PNG, WebP, BMP,
  GIF, TIFF), honours phone rotation tags (`ImageOps.exif_transpose`),
  and shrinks each photo to a tiny 8×8 grayscale grid. One library,
  all the image work.
- **Perceptual hashing, written by hand (~30 lines)** — two classic
  hashes, no extra package needed:
  - **dHash (default):** each bit answers "is this cell brighter than
    the cell to its right?" It keys on edges and gradients, so a
    brightened or darkened copy still matches.
  - **aHash:** each bit answers "is this cell brighter than the image
    average?" Simpler; use `--hash ahash` to compare.
  - Two versions of the same photo differ in only a few of the 64 bits;
    two different photos differ in about half. `--threshold` sets how
    many bits may differ and still count (default 5).
- **`hashlib.sha256`** — exact duplicates are caught first, the cheap
  way: same byte size, then same full-file hash. Certain, and free.
- **Union-Find** — groups matches transitively, so if A matches B and
  B matches C, all three land in one group even if A and C are just
  over the threshold apart.
- **Quarantine, don't delete** — same rule as tool #1. The keeper in
  each group is the highest-resolution copy (then the biggest file);
  everything else goes to review, never to the trash.

## Options

| Flag | What it does |
|---|---|
| `folders` | One or more folders to scan (required) |
| `--threshold N` | Max hash bits that may differ (default 5; 0 = identical look, 10 = loose — burst shots may match) |
| `--hash ahash\|dhash\|both` | Which hash to use (default dhash; `both` matches if either hash is close) |
| `--min-size 10KB` | Ignore files smaller than this (default 1KB) |
| `--no-recursive` | Don't descend into subfolders |
| `--report-dir DIR` | Where the JSON/CSV reports go (default: current folder) |
| `--move` | Move extra copies into `<folder>/_photo_dupes/` + write `restore_photos.py` |

## Honest limits

- **Not rotation-proof, and crops are threshold-dependent.** A photo
  rotated 90° is a different picture to a hash. Resizes, recompressions,
  and brightness changes match at the default threshold; a light crop
  needs a looser one (`--hash both --threshold 8`).
- **Pairwise comparison is O(n²).** Fine for a personal library (hundreds
  to a few thousand photos); a 50,000-photo archive wants a database, not
  this script.
- **Close isn't identical.** Burst shots of the same scene can land under
  a loose threshold — that's why the default only reports, and `--move`
  only ever quarantines. Check the review folder before emptying it.

## Verified test

Tested Nov 17, 2026 on generated sample photos: a base image, the same
image resized to 50%, re-saved as low-quality JPEG, and brightened 15% —
all four grouped together at the default threshold, with a full-resolution
lossless PNG picked as keeper over the bigger low-quality JPEG (size alone
would have kept the worst copy — the keeper rule prefers lossless first); a
different image stayed separate; a byte-identical copy was caught by the
exact-hash path. A light crop joined the group with
`--hash both --threshold 8`. `--move` moved the extras into
`_photo_dupes/` and `restore_photos.py` put them all back.
