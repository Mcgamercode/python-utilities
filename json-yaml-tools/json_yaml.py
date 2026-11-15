#!/usr/bin/env python3
"""
json_yaml.py — JSON / YAML validator, formatter, and converter.

Validate a JSON or YAML file and get the EXACT error location (line,
column, and a snippet with a caret pointing at the problem) instead of
a bare "invalid" message. Pretty-print or minify JSON, convert between
JSON and YAML, and check a whole folder of config files in one pass
(CI-friendly: exits non-zero when anything fails).

    python json_yaml.py config.json            # validate + pretty-print
    python json_yaml.py config.yaml --to json  # convert YAML -> JSON
    python json_yaml.py app.json --to yaml     # convert JSON -> YAML
    python json_yaml.py configs/ --check       # validate every file in a folder
    cat data.json | python json_yaml.py -       # read from stdin

Safety rules (same as the rest of this series):
  * Read-only by default. Nothing is ever overwritten unless you pass
    --in-place explicitly.
  * YAML is parsed with yaml.safe_load only — never yaml.load() —
    so a config file can't execute code.
  * --check mode only reads; it never writes anything.

Requires: PyYAML (one install, see README). Everything else is stdlib.
Python 3.8+. Works on Windows PowerShell and Termux/Android.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - handled with a friendly message
    yaml = None

VERSION = "1.0.0"
JSON_EXTS = {".json", ".jsonc", ".json5"}
YAML_EXTS = {".yaml", ".yml"}
ALL_EXTS = JSON_EXTS | YAML_EXTS


# ---------------------------------------------------------------------------
# Error reporting helpers
# ---------------------------------------------------------------------------

def _snippet(text, line_no, col_no, width=60):
    """Return the offending line plus a caret line pointing at col_no."""
    lines = text.splitlines()
    if not (1 <= line_no <= len(lines)):
        return ""
    line = lines[line_no - 1]
    start = max(0, col_no - width // 2)
    shown = line[start:start + width]
    caret_pos = col_no - 1 - start
    return f"    {shown}\n    {' ' * max(caret_pos, 0)}^"


def _json_error_detail(text, err):
    """Turn a json.JSONDecodeError into a human-readable report."""
    detail = f"{err.msg} (line {err.lineno}, column {err.colno})"
    return detail, _snippet(text, err.lineno, err.colno)


def _yaml_error_detail(text, err):
    """Turn a yaml.YAMLError into a human-readable report."""
    mark = getattr(err, "problem_mark", None)
    problem = getattr(err, "problem", None) or str(err).splitlines()[0]
    if mark is not None:
        detail = f"{problem} (line {mark.line + 1}, column {mark.column + 1})"
        return detail, _snippet(text, mark.line + 1, mark.column + 1)
    return problem, ""


# ---------------------------------------------------------------------------
# Duplicate-key detection
# ---------------------------------------------------------------------------

def _no_dup_object(pairs):
    """json object hook that refuses duplicate keys instead of silently
    keeping the last one — a duplicate key in a config is almost always
    a copy/paste bug."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key: {key!r}")
        obj[key] = value
    return obj


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that also refuses duplicate mapping keys in YAML."""

    def construct_mapping(self, node, deep=False):
        # flatten_mapping resolves '<<' merge keys before we iterate,
        # so merged keys still get duplicate-checked like normal keys.
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                # MarkedYAMLError (not plain YAMLError) so the message
                # carries a proper line/column instead of a tuple repr.
                raise yaml.MarkedYAMLError(
                    problem=f"duplicate key: {key!r}",
                    problem_mark=key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def detect_format(path, text):
    """Guess JSON vs YAML from the extension, falling back to content."""
    suffix = path.suffix.lower() if path else ""
    if suffix in JSON_EXTS:
        return "json"
    if suffix in YAML_EXTS:
        return "yaml"
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return "json"
    return "yaml"


def parse_json(text):
    """Parse JSON. Returns (data, error_report or None)."""
    try:
        data = json.loads(text, object_pairs_hook=_no_dup_object)
        return data, None
    except json.JSONDecodeError as err:
        detail, snippet = _json_error_detail(text, err)
        return None, f"Invalid JSON — {detail}\n{snippet}" if snippet else \
            f"Invalid JSON — {detail}"
    except ValueError as err:  # duplicate key from the object hook
        return None, f"Invalid JSON — {err}"


def parse_yaml(text):
    """Parse YAML (single or multi-document).
    Returns (data, error or None, multi_doc flag)."""
    try:
        docs = list(yaml.load_all(text, Loader=_StrictLoader))
        multi = len(docs) > 1
        return (docs[0] if len(docs) == 1 else docs), None, multi
    except yaml.YAMLError as err:
        detail, snippet = _yaml_error_detail(text, err)
        return None, (f"Invalid YAML — {detail}\n{snippet}" if snippet else
                      f"Invalid YAML — {detail}"), False


def parse(text, fmt):
    if fmt == "json":
        data, error = parse_json(text)
        return data, error, False
    return parse_yaml(text)


# ---------------------------------------------------------------------------
# Formatting / conversion
# ---------------------------------------------------------------------------

def to_json(data, indent=2, sort_keys=False, minify=False):
    if minify:
        return json.dumps(data, ensure_ascii=False, sort_keys=sort_keys,
                          separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=indent,
                      sort_keys=sort_keys)


def to_yaml(data, multi=False):
    # sort_keys=False keeps the original key order, which is what you
    # want when converting a config you wrote by hand.
    if multi:
        return yaml.safe_dump_all(data, default_flow_style=False,
                                  sort_keys=False, allow_unicode=True)
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False,
                          allow_unicode=True)


def summarize(data, label):
    """One-line shape summary: what kind of value is this, and how big?"""
    if isinstance(data, dict):
        keys = ", ".join(repr(k) for k in list(data)[:5])
        more = f" (+{len(data) - 5} more)" if len(data) > 5 else ""
        return f"{label}: valid object, {len(data)} top-level keys [{keys}{more}]"
    if isinstance(data, list):
        types = sorted({type(v).__name__ for v in data[:50]})
        return (f"{label}: valid array, {len(data)} items "
                f"(item types: {', '.join(types) or 'empty'})")
    return f"{label}: valid {type(data).__name__} ({data!r})"


# ---------------------------------------------------------------------------
# Single-file flow
# ---------------------------------------------------------------------------

def process_text(text, source_name, args):
    """Validate (and optionally convert/format) one document's text.
    Returns (ok, output_text or None, report_lines)."""
    fmt = args.format or detect_format(
        Path(source_name) if source_name != "<stdin>" else None, text)
    if fmt == "yaml" and yaml is None:
        return False, None, [
            f"{source_name}: PyYAML is not installed — run: pip install pyyaml"]
    data, error, multi = parse(text, fmt)
    if error is not None:
        return False, None, [f"{source_name}: {error}"]

    target = args.to or fmt
    report = [summarize(data, source_name)]

    if args.check:
        # --check only validates; no output document is produced.
        return True, None, report

    if target == "json":
        out = to_json(data, indent=args.indent, sort_keys=args.sort_keys,
                      minify=args.minify)
    else:
        if yaml is None:
            return False, None, [
                f"{source_name}: PyYAML is not installed — "
                "run: pip install pyyaml"]
        out = to_yaml(data, multi=multi)
    return True, out, report


def read_input(path_arg):
    """Read a file (UTF-8, BOM-tolerant) or stdin. Returns (text, name)."""
    if path_arg == "-":
        return sys.stdin.read(), "<stdin>"
    path = Path(path_arg)
    if not path.exists():
        return None, f"file not found: {path_arg}"
    try:
        return path.read_text(encoding="utf-8-sig"), str(path)
    except UnicodeDecodeError:
        return None, f"not valid UTF-8 text: {path_arg}"


# ---------------------------------------------------------------------------
# Folder (--check) flow
# ---------------------------------------------------------------------------

def check_folder(folder, args, recursive):
    """Validate every JSON/YAML file under a folder. Returns exit code."""
    root = Path(folder)
    if not root.is_dir():
        print(f"error: not a folder: {folder}", file=sys.stderr)
        return 2
    pattern = "**/*" if recursive else "*"
    files = sorted(p for p in root.glob(pattern)
                   if p.is_file() and p.suffix.lower() in ALL_EXTS)
    if not files:
        print(f"no .json/.yaml/.yml files found in {folder}")
        return 0

    ok_count, bad_count = 0, 0
    for path in files:
        text, name = read_input(str(path))
        if text is None:
            print(f"FAIL  {path} — {name}")
            bad_count += 1
            continue
        fmt = detect_format(path, text)
        _, error, _ = parse(text, fmt)
        if error:
            print(f"FAIL  {path}")
            print(f"      {error.splitlines()[0]}")
            bad_count += 1
        else:
            print(f"OK    {path}")
            ok_count += 1

    print(f"\n{ok_count} valid, {bad_count} invalid, "
          f"{ok_count + bad_count} files checked")
    return 1 if bad_count else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="json_yaml.py",
        description="Validate, pretty-print, minify, and convert JSON/YAML "
                    "files — with exact error locations.")
    p.add_argument("input", help="file to process, a folder (with --check), "
                                 "or '-' to read from stdin")
    p.add_argument("--to", choices=["json", "yaml"],
                   help="convert output to this format (default: same as input)")
    p.add_argument("--indent", type=int, default=2,
                   help="spaces per indent level for JSON output (default: 2)")
    p.add_argument("--minify", action="store_true",
                   help="compact JSON output with no extra whitespace")
    p.add_argument("--sort-keys", action="store_true",
                   help="sort object keys alphabetically in the output")
    p.add_argument("--check", action="store_true",
                   help="validate only — print OK/FAIL, write no output. "
                        "With a folder, checks every JSON/YAML file in it.")
    p.add_argument("--recursive", "-r", action="store_true",
                   help="with --check on a folder, recurse into subfolders")
    p.add_argument("--format", choices=["json", "yaml"],
                   help="force input format instead of guessing from the "
                        "extension/content (handy for extensionless files)")
    p.add_argument("--output", "-o",
                   help="write the result to this file instead of stdout")
    p.add_argument("--in-place", action="store_true",
                   help="overwrite the input file with the result "
                        "(never the default — use deliberately)")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if yaml is None and (args.to == "yaml" or
                         (args.format == "yaml") or
                         (not args.to and args.input.endswith(
                             (".yaml", ".yml")))):
        print("error: PyYAML is not installed. Install it once with:",
              file=sys.stderr)
        print("    pip install pyyaml", file=sys.stderr)
        return 2

    # Folder mode: --check on a directory.
    if args.input != "-" and Path(args.input).is_dir():
        if not args.check:
            print("error: input is a folder — use --check to validate it "
                  "(add -r to recurse)", file=sys.stderr)
            return 2
        return check_folder(args.input, args, args.recursive)

    text, name = read_input(args.input)
    if text is None:
        print(f"error: {name}", file=sys.stderr)
        return 2

    ok, output, report = process_text(text, name, args)
    # Reports always go to stderr so stdout stays a clean document —
    # `python json_yaml.py config.json > out.json` must contain only JSON.
    for line in report:
        print(line, file=sys.stderr)
    if not ok:
        return 1
    if output is None:  # --check passed, nothing to emit
        return 0

    if args.in_place:
        if args.input == "-":
            print("error: --in-place needs a real file, not stdin",
                  file=sys.stderr)
            return 2
        Path(args.input).write_text(output + "\n", encoding="utf-8")
        print(f"rewrote {args.input} in place", file=sys.stderr)
    elif args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
