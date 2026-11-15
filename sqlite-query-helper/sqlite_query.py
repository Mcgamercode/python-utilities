#!/usr/bin/env python3
"""
sqlite_query.py — SQLite Query Helper (tool #10 in the nightly series)

Inspect any SQLite database, run SQL, and export the results — from the
terminal, with no GUI and no install. Read-only by default, so you can poke
around a production or app database without any risk of changing it.

What it does
------------
  * --schema      : full schema summary — tables, views, columns, types,
                    primary keys, row counts, indexes, file size
  * --tables      : quick list of tables with row counts
  * --describe T  : columns of one table (type, NOT NULL, default, PK)
  * --query SQL   : run a query and print a neat table
  * --sql-file F  : run the SQL in a file
  * --csv OUT     : export query results to CSV (pairs with --query/--sql-file)
  * --json        : print query results as JSON instead of a table
  * --interactive : tiny REPL — type SQL, .tables, .schema, .quit
  * --write       : allow writes (INSERT/UPDATE/DELETE). Off by default:
                    the database is opened read-only, so a typo can't
                    corrupt anything. Destructive statements (DROP, or
                    DELETE/UPDATE with no WHERE) ask first unless --force.

Usage
-----
  python sqlite_query.py app.db --schema
  python sqlite_query.py app.db --query "SELECT * FROM users LIMIT 5"
  python sqlite_query.py app.db --query "SELECT ..." --csv results.csv
  python sqlite_query.py app.db --sql-file report.sql --csv out.csv
  python sqlite_query.py app.db --interactive
  python sqlite_query.py app.db --write --query "INSERT INTO users ..."

Standard library only — sqlite3, argparse, csv, json, pathlib.
Python 3.8+ on Windows PowerShell, macOS, Linux, or Termux/Android.
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_LIMIT = 100

# Statements that change data. Anything not starting with one of the
# read-only keywords is treated as a write and refused in read-only mode.
READ_KEYWORDS = ("SELECT", "WITH", "EXPLAIN", "PRAGMA")
WRITE_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "REPLACE",
    "VACUUM", "ATTACH", "DETACH", "REINDEX", "ANALYZE", "TRUNCATE",
)
DESTRUCTIVE_KEYWORDS = ("DROP", "TRUNCATE", "VACUUM", "DETACH")


def looks_destructive(sql: str) -> bool:
    """True for DROP/TRUNCATE, or DELETE/UPDATE with no WHERE clause."""
    s = sql.strip().upper()
    if s.startswith(DESTRUCTIVE_KEYWORDS):
        return True
    if s.startswith(("DELETE", "UPDATE")) and " WHERE " not in f" {s} ":
        return True
    return False


def connect(db_path: Path, read_only: bool) -> sqlite3.Connection:
    """Open the database. Read-only mode uses a URI so SQLite itself
    enforces it — even a bug in this script can't write to the file."""
    if not db_path.exists():
        raise SystemExit(f"error: no such file: {db_path}")
    if read_only:
        uri = "file:" + str(db_path.resolve()) + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def is_valid_db(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        return True
    except sqlite3.DatabaseError:
        return False


def get_tables(conn: sqlite3.Connection):
    """(name, type, row_count) for every table and view."""
    rows = conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    ).fetchall()
    out = []
    for r in rows:
        count = None
        if r["type"] == "table":
            try:
                count = conn.execute(
                    f'SELECT COUNT(*) FROM "{r["name"]}"'
                ).fetchone()[0]
            except sqlite3.Error:
                count = None
        out.append((r["name"], r["type"], count))
    return out


def table_columns(conn: sqlite3.Connection, table: str):
    """PRAGMA table_info rows for one table."""
    return conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()


def print_schema(conn: sqlite3.Connection, db_path: Path) -> None:
    tables = get_tables(conn)
    n_tables = sum(1 for _, t, _ in tables if t == "table")
    n_views = sum(1 for _, t, _ in tables if t == "view")
    total_rows = sum(c or 0 for _, t, c in tables if t == "table")
    print(f"Database: {db_path}  ({db_path.stat().st_size:,} bytes)")
    print(f"Tables: {n_tables}   Views: {n_views}   Total rows: {total_rows:,}")
    print()
    for name, kind, count in tables:
        label = "TABLE" if kind == "table" else "VIEW "
        count_txt = f"{count:,} rows" if count is not None else ""
        print(f"  {label}  {name}  {count_txt}")
        for col in table_columns(conn, name) if kind == "table" else []:
            pk = " PK" if col["pk"] else ""
            nn = " NOT NULL" if col["notnull"] else ""
            default = f" DEFAULT {col['dflt_value']}" if col["dflt_value"] is not None else ""
            print(f"           {col['name']}  {col['type'] or '—'}{pk}{nn}{default}")
        indexes = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
            (name,),
        ).fetchall()
        for idx in indexes:
            print(f"           INDEX {idx['name']}")
    print()


def print_tables(conn: sqlite3.Connection) -> None:
    tables = get_tables(conn)
    if not tables:
        print("No tables or views found.")
        return
    width = max(len(name) for name, _, _ in tables)
    for name, kind, count in tables:
        count_txt = f"{count:,} rows" if count is not None else ""
        print(f"  {name:<{width}}  {kind:<5}  {count_txt}")


def print_describe(conn: sqlite3.Connection, table: str) -> None:
    cols = table_columns(conn, table)
    if not cols:
        raise SystemExit(f"error: no such table: {table}")
    print(f"Table: {table}")
    print(f"  {'column':<20} {'type':<16} {'null':<6} {'default':<14} {'key'}")
    print("  " + "-" * 70)
    for c in cols:
        print(
            f"  {c['name']:<20} {c['type'] or '—':<16} "
            f"{'NO' if c['notnull'] else 'YES':<6} "
            f"{str(c['dflt_value'] or ''):<14} "
            f"{'PK' if c['pk'] else ''}"
        )


def format_table(columns, rows) -> str:
    """Render rows as an aligned plain-text table."""
    widths = [len(str(c)) for c in columns]
    str_rows = [[str(v) if v is not None else "NULL" for v in row] for row in rows]
    for r in str_rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(v))
    sep = "  ".join("-" * w for w in widths)
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(columns, widths)), sep]
    lines += ["  ".join(v.ljust(w) for v, w in zip(r, widths)) for r in str_rows]
    return "\n".join(lines)


def run_query(conn: sqlite3.Connection, sql: str, limit: int):
    """Run one statement. Returns (columns, rows) for queries, or
    (None, affected) for writes. Raises SystemExit with a clear message
    on bad SQL instead of a raw traceback."""
    try:
        cur = conn.execute(sql)
    except sqlite3.Error as exc:
        raise SystemExit(f"error: {exc}\n  SQL: {sql.strip()[:200]}")
    if cur.description is None:
        conn.commit()
        return None, cur.rowcount
    columns = [d[0] for d in cur.description]
    rows = cur.fetchall()
    truncated = False
    if limit and len(rows) > limit:
        rows, truncated = rows[:limit], True
    return (columns, rows), truncated


def export_csv(path: Path, columns, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows([[v if v is not None else "" for v in row] for row in rows])
    print(f"Exported {len(rows):,} row(s) to {path}")


def run_interactive(conn: sqlite3.Connection, read_only: bool) -> None:
    print("SQLite Query Helper — interactive mode")
    print("Type SQL and press Enter. Commands: .tables  .schema  .quit")
    print("End a statement with ; — multi-line statements are supported.")
    print(f"Mode: {'READ-ONLY (use --write to allow changes)' if read_only else 'WRITE'}")
    buffer = ""
    while True:
        try:
            line = input("sql> " if not buffer else " ...> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        stripped = line.strip()
        if not buffer and stripped == ".quit":
            print("Bye.")
            return
        if not buffer and stripped == ".tables":
            print_tables(conn)
            continue
        if not buffer and stripped == ".schema":
            print_schema(conn, Path(conn.execute("PRAGMA database_list").fetchone()[2]))
            continue
        buffer += line + "\n"
        if not stripped.endswith(";"):
            continue
        sql, buffer = buffer, ""
        if read_only and sql.strip().upper().startswith(WRITE_KEYWORDS):
            print("Refused: read-only mode. Restart with --write to change data.")
            continue
        if not read_only and looks_destructive(sql):
            answer = input("This looks destructive. Type YES to run it: ").strip()
            if answer != "YES":
                print("Skipped.")
                continue
        result, truncated = run_query(conn, sql, DEFAULT_LIMIT)
        if result is None:
            print("OK.")
            continue
        columns, rows = result
        print(format_table(columns, rows))
        print(f"({len(rows):,} row(s){' — first 100 shown' if truncated else ''})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="SQLite Query Helper — inspect any SQLite database, "
                    "run SQL, export results. Read-only by default."
    )
    parser.add_argument("db", type=Path, help="path to the .sqlite/.db file")
    parser.add_argument("--schema", action="store_true",
                        help="show full schema summary (tables, columns, row counts)")
    parser.add_argument("--tables", action="store_true",
                        help="list tables and views with row counts")
    parser.add_argument("--describe", metavar="TABLE",
                        help="show columns of one table")
    parser.add_argument("--query", metavar="SQL",
                        help="run one SQL statement")
    parser.add_argument("--sql-file", type=Path, metavar="FILE",
                        help="run the SQL statements in a file")
    parser.add_argument("--csv", type=Path, metavar="OUT.csv",
                        help="export query results to CSV")
    parser.add_argument("--json", action="store_true",
                        help="print query results as JSON instead of a table")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"max rows to show/export (default {DEFAULT_LIMIT}, 0 = all)")
    parser.add_argument("--write", action="store_true",
                        help="allow writes (INSERT/UPDATE/DELETE). "
                             "Without it the database is opened read-only.")
    parser.add_argument("--force", action="store_true",
                        help="skip the confirmation prompt for destructive "
                             "statements in --write mode")
    parser.add_argument("--interactive", action="store_true",
                        help="open a small SQL prompt for this database")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    read_only = not args.write
    try:
        conn = connect(args.db, read_only)
    except sqlite3.Error as exc:
        raise SystemExit(f"error: cannot open {args.db}: {exc}")
    if not is_valid_db(conn):
        raise SystemExit(f"error: {args.db} is not a SQLite database")

    if args.interactive:
        run_interactive(conn, read_only)
        return 0
    if args.schema:
        print_schema(conn, args.db)
        return 0
    if args.tables:
        print_tables(conn)
        return 0
    if args.describe:
        print_describe(conn, args.describe)
        return 0

    sql = None
    if args.query:
        sql = args.query
    elif args.sql_file:
        if not args.sql_file.exists():
            raise SystemExit(f"error: no such file: {args.sql_file}")
        sql = args.sql_file.read_text(encoding="utf-8")

    if sql is None:
        parser.error("nothing to do — give --schema, --tables, --describe, "
                     "--query, --sql-file, or --interactive")

    statements = [s for s in (s.strip() for s in sql.split(";")) if s]
    if read_only:
        # Refuse statements that are clearly writes, with a friendly
        # message. Anything else is attempted and SQLite itself enforces
        # read-only — so a typo'd SELECT still reports its real syntax
        # error instead of a misleading "this writes data" message.
        bad = [s for s in statements
               if s.upper().startswith(WRITE_KEYWORDS)]
        if bad:
            raise SystemExit(
                "error: read-only mode — this SQL writes data:\n"
                f"  {bad[0][:120]}\n"
                "Re-run with --write to allow changes."
            )
    elif not args.force:
        bad = [s for s in statements if looks_destructive(s)]
        if bad:
            print("This SQL looks destructive:")
            for s in bad:
                print(f"  {s[:120]}")
            answer = input("Type YES to run it anyway: ").strip()
            if answer != "YES":
                print("Aborted — nothing was changed.")
                return 1

    for i, stmt in enumerate(statements):
        result, truncated = run_query(conn, stmt, args.limit)
        if result is None:
            print(f"Statement {i + 1}: OK")
            continue
        columns, rows = result
        if args.csv and i == len(statements) - 1:
            export_csv(args.csv, columns, rows)
        elif args.json:
            print(json.dumps([dict(zip(columns, r)) for r in rows],
                             indent=2, default=str))
        else:
            print(format_table(columns, rows))
            print(f"({len(rows):,} row(s)"
                  f"{' — showing first ' + str(args.limit) if truncated else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
