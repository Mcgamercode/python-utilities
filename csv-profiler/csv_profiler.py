#!/usr/bin/env python3
"""csv_profiler.py — instant stats on any CSV file.

Point it at a CSV and get, in seconds: row/column counts, per-column
detected types, null counts, unique counts, numeric distributions
(min / max / mean / median / stdev), top values for text columns, and
duplicate-row counts. The first thing a data analyst does with a new
dataset, before a single chart or SQL query.

Pure standard library — no pip installs. Works on Windows PowerShell
and Termux/Android with the same commands.

Usage:
    python csv_profiler.py data.csv
    python csv_profiler.py data.csv --json report.json
    python csv_profiler.py data.csv --top 10 --sample 5
    python csv_profiler.py data.csv --delimiter ";" --no-header

The tool only READS the file you point it at. It never writes to it,
never deletes anything, and never uploads anything.
"""

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"

# Values that count as "missing" (case-insensitive, after stripping).
NULL_TOKENS = {"", "null", "none", "na", "n/a", "nan", "nil", "-"}
BOOL_TOKENS = {"true", "false", "yes", "no", "y", "n", "1", "0", "t", "f"}
DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m-%d-%Y", "%d.%m.%Y",
    "%b %d, %Y", "%d %b %Y",
)

INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(
    r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$"
)


def is_int(value):
    """True if the string looks like a plain integer ('42', '-7')."""
    return bool(INT_RE.match(value.strip()))


def is_float(value):
    """True if the string looks like a number ('3.14', '1e6', '42')."""
    return bool(FLOAT_RE.match(value.strip()))


def is_bool(value):
    """True if the string is a yes/no style boolean token."""
    return value.strip().lower() in BOOL_TOKENS


def is_date(value):
    """True if the string parses as a date in a common format."""
    text = value.strip()
    if len(text) < 8 or len(text) > 20:
        return False
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def classify(value):
    """Classify one non-null cell: 'integer', 'float', 'boolean',
    'date', or 'text'."""
    if is_int(value):
        return "integer"
    if is_float(value):
        return "float"
    if is_bool(value):
        return "boolean"
    if is_date(value):
        return "date"
    return "text"


def read_csv(path, delimiter, has_header, encoding):
    """Read the file and return (header, rows, ragged_count, dialect).

    Rows are lists of strings. Short rows are padded with '' and long
    rows are truncated so every row matches the header width; ragged
    rows are counted, not silently dropped.
    """
    with open(path, "r", newline="", encoding=encoding) as handle:
        sample = handle.read(65536)
        handle.seek(0)
        if delimiter is None:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.reader(handle, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        return [], [], 0, delimiter

    if has_header:
        header = [name.strip() or f"column_{i + 1}"
                  for i, name in enumerate(rows[0])]
        data = rows[1:]
    else:
        width = max(len(row) for row in rows)
        header = [f"column_{i + 1}" for i in range(width)]
        data = rows

    # Make duplicate column names unique: name, name_2, name_3 ...
    seen = Counter()
    unique_header = []
    for name in header:
        seen[name] += 1
        unique_header.append(name if seen[name] == 1
                             else f"{name}_{seen[name]}")
    header = unique_header

    width = len(header)
    ragged = 0
    cleaned = []
    for row in data:
        if len(row) != width:
            ragged += 1
            row = (row + [""] * width)[:width]
        cleaned.append(row)
    return header, cleaned, ragged, delimiter


def profile_column(values):
    """Profile one column (list of raw strings) and return a dict."""
    total = len(values)
    nulls = sum(1 for v in values if v.strip().lower() in NULL_TOKENS)
    present = [v for v in values if v.strip().lower() not in NULL_TOKENS]
    present_count = len(present)

    profile = {
        "non_null": present_count,
        "nulls": nulls,
        "null_pct": round(100 * nulls / total, 1) if total else 0.0,
        "unique": len(set(present)),
    }
    profile["unique_pct"] = (
        round(100 * profile["unique"] / present_count, 1)
        if present_count else 0.0
    )

    if present_count == 0:
        profile["type"] = "empty"
        return profile

    kinds = Counter(classify(v) for v in present)
    dominant, dominant_count = kinds.most_common(1)[0]
    # A column is its dominant type only if >= 90% of values agree;
    # otherwise it's mixed, which is itself a useful warning.
    if dominant_count / present_count >= 0.9:
        profile["type"] = dominant
    else:
        profile["type"] = "mixed"
        profile["type_breakdown"] = dict(kinds)

    if profile["type"] in ("integer", "float"):
        numbers = [float(v) for v in present
                   if classify(v) in ("integer", "float")]
        if numbers:
            profile["min"] = min(numbers)
            profile["max"] = max(numbers)
            profile["mean"] = round(statistics.fmean(numbers), 4)
            profile["median"] = statistics.median(numbers)
            profile["stdev"] = (round(statistics.stdev(numbers), 4)
                                if len(numbers) > 1 else 0.0)
            profile["sum"] = round(sum(numbers), 4)
            # Values that aren't numbers in a mostly-numeric column.
            profile["non_numeric"] = present_count - len(numbers)

    if profile["type"] == "date":
        dates = []
        for v in present:
            for fmt in DATE_FORMATS:
                try:
                    dates.append(datetime.strptime(v.strip(), fmt))
                    break
                except ValueError:
                    continue
        if dates:
            profile["min"] = min(dates).isoformat()
            profile["max"] = max(dates).isoformat()

    if profile["type"] in ("text", "boolean", "mixed"):
        lengths = [len(v) for v in present]
        profile["min_length"] = min(lengths)
        profile["max_length"] = max(lengths)

    # Top values: useful for text/low-cardinality columns, and a quick
    # sanity check for any column with few distinct values.
    counts = Counter(present)
    if profile["unique"] <= 50:
        profile["top_values"] = [
            {"value": value, "count": count}
            for value, count in counts.most_common(10)
        ]
    return profile


def profile_file(path, delimiter=None, has_header=True, top=5):
    """Run the full profile and return one big dict."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {path}")

    # Try encodings in order; fall back to latin-1 which never fails.
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            header, rows, ragged, used_delim = read_csv(
                path, delimiter, has_header, encoding)
            break
        except UnicodeDecodeError as exc:  # pragma: no cover
            last_error = exc
    else:  # pragma: no cover
        raise last_error

    total_rows = len(rows)
    report = {
        "file": str(path),
        "size_bytes": path.stat().st_size,
        "delimiter": used_delim,
        "encoding": encoding,
        "rows": total_rows,
        "columns": len(header),
        "ragged_rows": ragged,
        "empty_rows": sum(1 for row in rows
                          if all(cell.strip() == "" for cell in row)),
        "duplicate_rows": 0,
        "columns_profile": {},
    }
    if total_rows:
        report["duplicate_rows"] = total_rows - len({tuple(r) for r in rows})

    for idx, name in enumerate(header):
        values = [row[idx] for row in rows]
        report["columns_profile"][name] = profile_column(values)
    report["top_n"] = top
    return report


def format_report(report, top=5, sample_rows=None):
    """Render the profile dict as readable plain text."""
    lines = []
    lines.append(f"FILE: {report['file']}  ({report['size_bytes']:,} bytes)")
    lines.append(f"Delimiter: {report['delimiter']!r}   "
                 f"Encoding: {report['encoding']}")
    lines.append(f"Rows: {report['rows']:,}   Columns: {report['columns']}")
    if report["ragged_rows"]:
        lines.append(f"! {report['ragged_rows']} ragged rows "
                     "(wrong number of fields — padded/truncated)")
    if report["empty_rows"]:
        lines.append(f"! {report['empty_rows']} completely empty rows")
    if report["duplicate_rows"]:
        lines.append(f"! {report['duplicate_rows']} exact duplicate rows")
    lines.append("")

    for name, col in report["columns_profile"].items():
        pct = col["null_pct"]
        lines.append(
            f"{name}  [{col['type']}]  "
            f"non-null {col['non_null']:,}/{report['rows']:,}  "
            f"nulls {col['nulls']:,} ({pct}%)  "
            f"unique {col['unique']:,} ({col['unique_pct']}%)"
        )
        if "type_breakdown" in col:
            breakdown = ", ".join(f"{k}: {v}"
                                  for k, v in col["type_breakdown"].items())
            lines.append(f"    mixed types — {breakdown}")
        if "min" in col and col["type"] in ("integer", "float"):
            lines.append(
                f"    min {col['min']:g}  max {col['max']:g}  "
                f"mean {col['mean']:g}  median {col['median']:g}  "
                f"stdev {col['stdev']:g}  sum {col['sum']:g}"
            )
            if col.get("non_numeric"):
                lines.append(f"    ! {col['non_numeric']} non-numeric "
                             "values hiding in this column")
        elif "min" in col and col["type"] == "date":
            lines.append(f"    earliest {col['min']}  latest {col['max']}")
        if "min_length" in col:
            lines.append(f"    shortest {col['min_length']} chars  "
                         f"longest {col['max_length']} chars")
        if "top_values" in col:
            shown = col["top_values"][:top]
            top_text = ", ".join(
                f"{item['value']!r} x{item['count']}" for item in shown)
            lines.append(f"    top: {top_text}")
        lines.append("")

    if sample_rows:
        lines.append("SAMPLE ROWS:")
        for row in sample_rows:
            lines.append("  " + " | ".join(row))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Instant stats on any CSV: types, nulls, uniques, "
                    "numeric distributions, top values, duplicates.")
    parser.add_argument("file", help="path to the CSV file")
    parser.add_argument("--delimiter", "-d", default=None,
                        help="field delimiter (auto-detected by default: "
                             "comma, semicolon, tab, pipe)")
    parser.add_argument("--no-header", action="store_true",
                        help="the file has no header row (columns become "
                             "column_1, column_2, ...)")
    parser.add_argument("--top", type=int, default=5,
                        help="how many top values to show per column "
                             "(default 5)")
    parser.add_argument("--sample", type=int, default=0,
                        help="print N sample data rows after the report")
    parser.add_argument("--json", metavar="OUT.json",
                        help="also write the full profile as JSON to OUT")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    try:
        report = profile_file(args.file, delimiter=args.delimiter,
                              has_header=not args.no_header, top=args.top)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read {args.file}: {exc}", file=sys.stderr)
        return 1

    sample_rows = None
    if args.sample > 0 and report["rows"]:
        # Re-read just the first rows for the sample; cheap and simple.
        try:
            _, rows, _, _ = read_csv(
                Path(args.file), args.delimiter or report["delimiter"],
                not args.no_header, report["encoding"])
            sample_rows = rows[: args.sample]
        except OSError:
            sample_rows = None

    print(format_report(report, top=args.top, sample_rows=sample_rows))

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(report, indent=2, default=str),
                       encoding="utf-8")
        print(f"\nJSON report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
