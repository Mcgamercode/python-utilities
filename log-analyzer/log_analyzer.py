#!/usr/bin/env python3
"""
log_analyzer.py — Log File Analyzer (tool #5, nightly Python tool series)

Point it at a server or app log file and get a plain-English summary:
total lines, time range, requests by status-code class, errors by type,
top IPs, top requested paths, busiest hours, and a per-hour timeline.

Formats handled (auto-detected, or forced with --format):
  apache  — Apache/Nginx combined or common log format, e.g.
            203.0.113.7 - - [08/Nov/2026:14:02:11 +0000] "GET /index.html HTTP/1.1" 200 5123
  generic — app/syslog-style lines with a severity word, e.g.
            2026-11-08 14:02:11 ERROR db.py: failed to connect (timeout after 5s)

Read-only: it never writes to, moves, or deletes the log file.
Standard library only — no pip installs. Python 3.8+.

Usage:
    python log_analyzer.py access.log
    python log_analyzer.py app.log --format generic
    python log_analyzer.py access.log --json report.json
    python log_analyzer.py access.log --top 20 --errors-only
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Apache/Nginx combined log format (also matches common log format: the
# referrer and user-agent fields are simply optional).
APACHE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+)(?: \S+)?" '
    r'(?P<status>\d{3}) (?P<size>\S+)'
    r'(?: "(?P<referrer>[^"]*)" "(?P<agent>[^"]*)")?'
)

# "08/Nov/2026:14:02:11 +0000" — the timestamp inside Apache brackets.
APACHE_TIME = "%d/%b/%Y:%H:%M:%S %z"

# Generic app log: an ISO-ish timestamp, then a severity word somewhere
# near the front. Matches "2026-11-08 14:02:11 ERROR ..." and
# "2026-11-08T14:02:11Z [WARN] ...".
GENERIC_RE = re.compile(
    r'^(?P<time>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
    r'[^A-Za-z0-9]{0,4}(?:\[)?(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)(?:\])?'
    r'[:\s-]*(?P<message>.*)$',
    re.IGNORECASE,
)

# Syslog-style: "Nov  8 14:02:11 hostname sshd[1234]: Failed password ..."
SYSLOG_RE = re.compile(
    r'^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2}) (?P<clock>\d{2}:\d{2}:\d{2}) '
    r'(?P<host>\S+) (?P<app>[^\s:]+)(?:\[\d+\])?: (?P<message>.*)$'
)

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

LEVELS = ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL")


def norm_level(raw):
    """Collapse WARNING -> WARN, FATAL -> CRITICAL for counting."""
    level = raw.upper()
    if level == "WARNING":
        return "WARN"
    if level == "FATAL":
        return "CRITICAL"
    return level


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_apache_time(text):
    try:
        return datetime.strptime(text, APACHE_TIME)
    except ValueError:
        return None


def parse_generic_time(text):
    text = text.replace("Z", "+0000")
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # Fractional seconds: trim them and retry.
    base = re.sub(r"\.\d+", "", text)
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(base, fmt)
        except ValueError:
            continue
    return None


def detect_format(sample_lines):
    """Sniff the first non-blank lines and guess the format."""
    apache_hits = generic_hits = 0
    for line in sample_lines:
        if not line.strip():
            continue
        if APACHE_RE.match(line):
            apache_hits += 1
        elif GENERIC_RE.match(line) or SYSLOG_RE.match(line):
            generic_hits += 1
    if apache_hits and apache_hits >= generic_hits:
        return "apache"
    if generic_hits:
        return "generic"
    return "unknown"


def parse_line(line, fmt):
    """Return a dict of extracted fields, or None if the line doesn't fit."""
    if fmt == "apache":
        m = APACHE_RE.match(line)
        if not m:
            return None
        when = parse_apache_time(m.group("time"))
        size = m.group("size")
        return {
            "kind": "apache",
            "ip": m.group("ip"),
            "time": when,
            "method": m.group("method"),
            "path": m.group("path").split("?")[0],  # strip query strings
            "status": int(m.group("status")),
            "size": int(size) if size.isdigit() else None,
            "agent": m.group("agent"),
        }

    # generic: ISO-timestamp + severity word first, syslog second.
    m = GENERIC_RE.match(line)
    if m:
        return {
            "kind": "generic",
            "time": parse_generic_time(m.group("time")),
            "level": norm_level(m.group("level")),
            "message": m.group("message").strip(),
        }
    m = SYSLOG_RE.match(line)
    if m:
        message = m.group("message")
        level = "INFO"
        for word in ("ERROR", "CRITICAL", "FATAL", "WARNING", "WARN", "DEBUG"):
            if re.search(rf"\b{word}\b", message, re.IGNORECASE):
                level = norm_level(word)
                break
        return {
            "kind": "generic",
            "time": None,  # syslog lines carry no year; hour is still usable
            "hour": int(m.group("clock").split(":")[0]),
            "level": level,
            "message": message.strip(),
            "app": re.sub(r"\[\d+\]$", "", m.group("app")),  # drop "[pid]"
        }
    return None


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def status_class(status):
    return f"{status // 100}xx"


def summarize_error_message(message):
    """Collapse a message to a countable 'error type': strip numbers, IPs,
    quoted strings, and hex so the same failure groups together."""
    text = message.strip()
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<IP>", text)   # IPs
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", text)           # hex ids
    text = re.sub(r"'[^']*'", "'...'", text)                     # quoted bits
    text = re.sub(r'"[^"]*"', '"..."', text)
    text = re.sub(r"\d+(?:\.\d+)?", "#", text)                    # numbers,
    # incl. "5s" / "1.2s" style units, so the same failure groups together
    return text[:120] if text else "(empty message)"


def analyze(path, fmt, top_n):
    stats = {
        "file": str(path),
        "format": fmt,
        "total_lines": 0,
        "parsed": 0,
        "unparsed": 0,
        "first_seen": None,
        "last_seen": None,
        "status_codes": Counter(),
        "status_classes": Counter(),
        "methods": Counter(),
        "ips": Counter(),
        "paths": Counter(),
        "agents": Counter(),
        "bytes_total": 0,
        "levels": Counter(),
        "error_messages": Counter(),
        "apps": Counter(),
        "per_hour": Counter(),
        "per_day": Counter(),
    }

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            stats["total_lines"] += 1
            rec = parse_line(line, fmt)
            if rec is None:
                stats["unparsed"] += 1
                continue
            stats["parsed"] += 1

            when = rec.get("time")
            if when is not None:
                if stats["first_seen"] is None or when < stats["first_seen"]:
                    stats["first_seen"] = when
                if stats["last_seen"] is None or when > stats["last_seen"]:
                    stats["last_seen"] = when
                stats["per_hour"][when.hour] += 1
                stats["per_day"][when.date().isoformat()] += 1
            elif "hour" in rec:  # syslog: hour known, year unknown
                stats["per_hour"][rec["hour"]] += 1

            if rec["kind"] == "apache":
                status = rec["status"]
                stats["status_codes"][status] += 1
                stats["status_classes"][status_class(status)] += 1
                stats["methods"][rec["method"]] += 1
                stats["ips"][rec["ip"]] += 1
                stats["paths"][rec["path"]] += 1
                if rec.get("agent"):
                    stats["agents"][rec["agent"]] += 1
                if rec["size"] is not None:
                    stats["bytes_total"] += rec["size"]
                if status >= 400:
                    stats["error_messages"][
                        f"{status} {rec['method']} "
                        f"{summarize_error_message(rec['path'])}"
                    ] += 1
            else:
                stats["levels"][rec["level"]] += 1
                if rec.get("app"):
                    stats["apps"][rec["app"]] += 1
                if rec["level"] in ("ERROR", "CRITICAL"):
                    stats["error_messages"][
                        summarize_error_message(rec["message"])] += 1
    return stats


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def bar(count, peak, width=30):
    filled = int(round(width * count / peak)) if peak else 0
    return "#" * filled


def report(stats, top_n, errors_only):
    lines = []
    lines.append(f"FILE: {stats['file']}  ({stats['format']} format)")
    lines.append(
        f"Lines: {stats['total_lines']:,}  parsed: {stats['parsed']:,}  "
        f"unparsed: {stats['unparsed']:,}")
    if stats["first_seen"] and stats["last_seen"]:
        lines.append(
            f"Time range: {stats['first_seen']}  to  {stats['last_seen']}")
    lines.append("")

    if stats["format"] == "apache":
        total = stats["parsed"] or 1
        lines.append("== Status codes ==")
        for cls in ("2xx", "3xx", "4xx", "5xx"):
            count = stats["status_classes"].get(cls, 0)
            pct = 100 * count / total
            lines.append(
                f"  {cls}: {count:,} ({pct:.1f}%) "
                f"{bar(count, max(stats['status_classes'].values(), default=1))}")
        if stats["status_codes"]:
            top_codes = ", ".join(
                f"{c} x{n}" for c, n in stats["status_codes"].most_common(5))
            lines.append(f"  most common codes: {top_codes}")
        if stats["bytes_total"]:
            lines.append(
                f"  total bytes served: {human_bytes(stats['bytes_total'])}")
        lines.append("")

        if stats["methods"]:
            lines.append("== Methods ==")
            for method, n in stats["methods"].most_common(top_n):
                lines.append(f"  {method}: {n:,}")
            lines.append("")

        if not errors_only:
            lines.append(f"== Top {top_n} IPs ==")
            for ip, n in stats["ips"].most_common(top_n):
                lines.append(f"  {ip}: {n:,}")
            lines.append("")
            lines.append(f"== Top {top_n} paths ==")
            for path, n in stats["paths"].most_common(top_n):
                lines.append(f"  {path}: {n:,}")
            lines.append("")

    else:  # generic
        if stats["levels"]:
            lines.append("== Severity levels ==")
            for level in ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"):
                n = stats["levels"].get(level, 0)
                if n:
                    lines.append(f"  {level}: {n:,}")
            lines.append("")
        if stats["apps"]:
            lines.append(f"== Top {top_n} sources ==")
            for app, n in stats["apps"].most_common(top_n):
                lines.append(f"  {app}: {n:,}")
            lines.append("")

    if stats["error_messages"]:
        lines.append(f"== Top {top_n} errors ==")
        for msg, n in stats["error_messages"].most_common(top_n):
            lines.append(f"  {n:,}x  {msg}")
        lines.append("")

    if not errors_only and stats["per_hour"]:
        peak = max(stats["per_hour"].values())
        lines.append("== Busiest hours (all parsed lines) ==")
        for hour in sorted(stats["per_hour"]):
            n = stats["per_hour"][hour]
            lines.append(
                f"  {hour:02d}:00  {n:>7,}  {bar(n, peak)}")
        lines.append("")

    if not errors_only and len(stats["per_day"]) > 1:
        lines.append("== Per-day timeline ==")
        for day in sorted(stats["per_day"]):
            lines.append(f"  {day}: {stats['per_day'][day]:,}")
        lines.append("")

    if stats["unparsed"]:
        lines.append(
            f"Note: {stats['unparsed']:,} line(s) didn't match the "
            f"{stats['format']} format — try --format to force the other one.")
    return "\n".join(lines)


def to_jsonable(stats):
    out = {
        "file": stats["file"],
        "format": stats["format"],
        "total_lines": stats["total_lines"],
        "parsed": stats["parsed"],
        "unparsed": stats["unparsed"],
        "first_seen": stats["first_seen"].isoformat() if stats["first_seen"] else None,
        "last_seen": stats["last_seen"].isoformat() if stats["last_seen"] else None,
        "status_codes": {str(k): v for k, v in stats["status_codes"].items()},
        "status_classes": dict(stats["status_classes"]),
        "methods": dict(stats["methods"]),
        "top_ips": stats["ips"].most_common(20),
        "top_paths": stats["paths"].most_common(20),
        "top_agents": stats["agents"].most_common(10),
        "bytes_total": stats["bytes_total"],
        "levels": dict(stats["levels"]),
        "top_errors": stats["error_messages"].most_common(20),
        "per_hour": {str(k): v for k, v in sorted(stats["per_hour"].items())},
        "per_day": dict(sorted(stats["per_day"].items())),
    }
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Summarize a server or app log: errors, top IPs, "
                    "busiest hours, timeline.")
    parser.add_argument("logfile", help="path to the log file")
    parser.add_argument(
        "--format", choices=["auto", "apache", "generic"], default="auto",
        help="log format (default: auto-detect from the first lines)")
    parser.add_argument(
        "--top", type=int, default=10,
        help="how many entries to show in top-N lists (default: 10)")
    parser.add_argument(
        "--errors-only", action="store_true",
        help="show only the error summary, skip IPs/paths/timeline")
    parser.add_argument(
        "--json", dest="json_out", metavar="FILE",
        help="also write the full summary as JSON to FILE")
    args = parser.parse_args(argv)

    path = Path(args.logfile)
    if not path.is_file():
        print(f"Error: no such file: {path}", file=sys.stderr)
        return 2

    fmt = args.format
    if fmt == "auto":
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            sample = [next(fh, "") for _ in range(50)]
        fmt = detect_format(sample)
        if fmt == "unknown":
            print("Error: could not detect the log format. "
                  "Try --format apache or --format generic.",
                  file=sys.stderr)
            return 2

    stats = analyze(path, fmt, args.top)
    print(report(stats, args.top, args.errors_only))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(to_jsonable(stats), fh, indent=2)
        print(f"JSON report written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
