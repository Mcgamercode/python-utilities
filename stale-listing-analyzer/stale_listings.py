#!/usr/bin/env python3
"""Stale Listing Analyzer — Tool #2 of the Nightly Python Series.

Reads Mike's Marketplace inventory.db and answers the three questions that
matter in a volume/numbers-game flipping business:

  1. Which listings are stale (sitting too long with no sale)?
  2. What should I do about each one — renew, cut the price, or pull it?
  3. What is actually selling, and how fast?

Read-only by default: it never changes the database. The only write is
`--pull`, which marks 60+ day "dead" listings as pulled — and only after
you type PULL to confirm. Nothing is ever deleted.

Usage:
    python3 stale_listings.py
    python3 stale_listings.py --db ~/workspace/marketplace/inventory.db
    python3 stale_listings.py --markdown report.md
    python3 stale_listings.py --json report.json
    python3 stale_listings.py --stale-days 21 --pull
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

DEFAULT_DB = Path.home() / "workspace" / "marketplace" / "inventory.db"

# Age buckets, in days since the listing went live.
FRESH_DAYS = 14    # under this: leave it alone, it's still new
STALE_DAYS = 30    # at this age: renew it or cut the price
DEAD_DAYS = 60     # at this age: pull it or take a real cut

# Suggested price cuts (fractions of the current list price).
STALE_CUT = 0.10   # 10% off a stale listing
DEAD_CUT = 0.15    # 15% off a dead one — never below the floor price


def parse_date(value):
    """Parse the mixed date formats in the DB: 'YYYY-MM-DD',
    'YYYY-MM-DDTHH:MM:SS.ffffff', 'YYYY-MM-DD HH:MM:SS'. Returns a date
    or None if the value is empty/unparseable."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Last resort: first 10 chars if they look like a date.
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def money(value):
    return f"${value:,.2f}" if value is not None else "—"


def whole_dollars(value):
    """Round a suggested price to whole dollars — Marketplace buyers
    read $27 as a real price and $27.43 as a calculator accident."""
    return int(round(value))


def floor_from_notes(notes):
    """Pull a 'Floor $X' out of the notes field, e.g. 'Floor $100.'.
    Returns the floor as a float, or None."""
    if not notes:
        return None
    match = re.search(r"[Ff]loor\s*\$?\s*(\d+(?:\.\d+)?)", notes)
    return float(match.group(1)) if match else None


def suggest_cut(list_price, floor, fraction):
    """Suggested new price after a cut, never below the floor (if any).
    Returns (new_price, was_limited_by_floor)."""
    if list_price is None:
        return None, False
    new_price = whole_dollars(list_price * (1 - fraction))
    if floor is not None and new_price < floor:
        return whole_dollars(floor), True
    return new_price, False


def load_items(db_path):
    """Open the DB read-only (mode=ro — we cannot write by accident)
    and return all rows as dicts."""
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, name, category, list_price, target_price, status,"
        " date_added, date_listed, date_sold, sold_price, notes"
        " FROM items ORDER BY date_listed"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def analyze(items, today, stale_days, dead_days):
    """Split active listings into buckets and compute the sales stats."""
    active = [i for i in items if i["status"] == "active"]
    sold = [i for i in items if i["status"] in ("sold", "traded")]
    inventory = [i for i in items if i["status"] == "inventory"]

    buckets = {"fresh": [], "warming": [], "stale": [], "dead": [], "nodate": []}
    for item in active:
        listed = parse_date(item["date_listed"])
        if listed is None:
            item["age_days"] = None
            buckets["nodate"].append(item)
            continue
        age = (today - listed).days
        item["age_days"] = age
        item["listed_date"] = listed
        if age < FRESH_DAYS:
            buckets["fresh"].append(item)
        elif age < stale_days:
            buckets["warming"].append(item)
        elif age < dead_days:
            buckets["stale"].append(item)
        else:
            buckets["dead"].append(item)

    # Days-to-sell for sold items that have both dates.
    sell_times = []
    for item in sold:
        listed = parse_date(item["date_listed"])
        sold_on = parse_date(item["date_sold"])
        if listed and sold_on:
            sell_times.append(((sold_on - listed).days, item["name"]))

    # What sells, by category (case-normalized — the DB has 'Audio'
    # and 'audio' as separate categories).
    sold_by_cat = Counter()
    for item in sold:
        cat = (item["category"] or "uncategorized").strip().lower()
        sold_by_cat[cat] += 1

    return {
        "active": active, "sold": sold, "inventory": inventory,
        "buckets": buckets, "sell_times": sorted(sell_times),
        "sold_by_cat": sold_by_cat,
    }


def recommend(item, dead_days):
    """One-line action for a stale/dead listing. Returns
    (action, detail)."""
    age = item["age_days"]
    price = item["list_price"]
    target = item["target_price"]
    floor = floor_from_notes(item["notes"])

    if age >= dead_days:
        new_price, limited = suggest_cut(price, floor, DEAD_CUT)
        if new_price is None:
            return "PULL", "no price on file — decide keep or pull"
        if limited:
            return "PULL or CUT to floor", \
                f"15% cut would go below your ${floor:,.0f} floor — cut to floor or pull it"
        return "PULL or CUT 15%", \
            f"try {money(new_price)} (was {money(price)}) before pulling it"
    # Stale: 30–59 days.
    if target is not None and price is not None and price < target:
        return "RENEW + RESTORE PRICE", \
            f"listed at {money(price)} but your target was {money(target)} — renew it at the target"
    new_price, limited = suggest_cut(price, floor, STALE_CUT)
    if new_price is None:
        return "RENEW", "relist it to bump it back to the top of search"
    if limited:
        return "RENEW", \
            f"a 10% cut would break your ${floor:,.0f} floor — renew at {money(price)} instead"
    return "RENEW or CUT 10%", \
        f"try {money(new_price)} (was {money(price)})"


def build_report(data, today, dead_days):
    """Build the report as plain text lines and a JSON-able dict."""
    buckets = data["buckets"]
    active, sold = data["active"], data["sold"]
    lines = []
    lines.append("Marketplace Stale-Listing Report")
    lines.append(f"As of {today:%b %d, %Y} — {len(active)} active, "
                 f"{len(sold)} sold, {len(data['inventory'])} not listed yet")
    lines.append("")

    total_asking = sum(i["list_price"] or 0 for i in active)
    stale_value = sum(i["list_price"] or 0
                      for i in buckets["stale"] + buckets["dead"])
    lines.append(f"Total asking value live right now: {money(total_asking)}")
    lines.append(f"  of which stale/dead (30+ days): {money(stale_value)}")
    revenue = sum(i["sold_price"] or 0 for i in sold)
    lines.append(f"Revenue so far: {money(revenue)}")
    lines.append("")

    # --- Buckets ---
    lines.append(f"DEAD (60+ days, {len(buckets['dead'])} listings) — pull or deep-cut:")
    if buckets["dead"]:
        for item in sorted(buckets["dead"], key=lambda i: -i["age_days"]):
            action, detail = recommend(item, dead_days)
            lines.append(f"  - {item['name']} — {money(item['list_price'])}, "
                         f"{item['age_days']} days — {action}: {detail}")
    else:
        lines.append("  (none — good)")
    lines.append("")

    lines.append(f"STALE (30–59 days, {len(buckets['stale'])} listings) — renew or cut:")
    if buckets["stale"]:
        for item in sorted(buckets["stale"], key=lambda i: -i["age_days"]):
            action, detail = recommend(item, dead_days)
            lines.append(f"  - {item['name']} — {money(item['list_price'])}, "
                         f"{item['age_days']} days — {action}: {detail}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"WARMING (14–29 days, {len(buckets['warming'])} listings) — watch next week:")
    for item in sorted(buckets["warming"], key=lambda i: -i["age_days"]):
        lines.append(f"  - {item['name']} — {money(item['list_price'])}, "
                     f"{item['age_days']} days")
    if not buckets["warming"]:
        lines.append("  (none)")
    lines.append("")

    # Price flags: listed below target, or at/below floor.
    flags = []
    for item in active:
        if (item["target_price"] is not None and item["list_price"] is not None
                and item["list_price"] < item["target_price"]):
            flags.append(f"  - {item['name']}: listed {money(item['list_price'])} "
                         f"but target was {money(item['target_price'])}")
        floor = floor_from_notes(item["notes"])
        if (floor is not None and item["list_price"] is not None
                and item["list_price"] < floor):
            flags.append(f"  - {item['name']}: listed {money(item['list_price'])} "
                         f"BELOW your ${floor:,.0f} floor!")
    lines.append("PRICE FLAGS (asking less than you planned):")
    lines.extend(flags if flags else ["  (none)"])
    lines.append("")

    if buckets["nodate"]:
        lines.append("NO LIST DATE (can't age these — check them by hand):")
        for item in buckets["nodate"]:
            lines.append(f"  - {item['name']} — {money(item['list_price'])}")
        lines.append("")

    # --- What's selling ---
    lines.append("WHAT'S SELLING:")
    if data["sell_times"]:
        days = [d for d, _ in data["sell_times"]]
        days_sorted = sorted(days)
        median = days_sorted[len(days_sorted) // 2]
        lines.append(f"  Median days from listed to sold: {median} "
                     f"(across {len(days)} sold items with dates)")
        fastest = data["sell_times"][0]
        lines.append(f"  Fastest sale: {fastest[1]} — {fastest[0]} days")
        slowest = data["sell_times"][-1]
        lines.append(f"  Slowest sale: {slowest[1]} — {slowest[0]} days")
    else:
        lines.append("  Not enough sold items with dates to measure yet.")
    if data["sold_by_cat"]:
        lines.append("  Sold by category:")
        for cat, count in data["sold_by_cat"].most_common():
            lines.append(f"    - {cat}: {count}")
    lines.append("")

    if data["inventory"]:
        lines.append("SITTING IN INVENTORY, NEVER LISTED:")
        for item in data["inventory"]:
            lines.append(f"  - {item['name']}"
                         + (f" — target {money(item['target_price'])}"
                            if item["target_price"] else ""))
        lines.append("")

    def bucket_json(bucket):
        out = []
        for i in bucket:
            action, detail = recommend(i, dead_days)
            out.append({"name": i["name"], "price": i["list_price"],
                        "age_days": i["age_days"],
                        "action": action, "detail": detail})
        return out

    report_json = {
        "as_of": str(today),
        "counts": {
            "active": len(active), "sold": len(sold),
            "inventory": len(data["inventory"]),
            "fresh": len(buckets["fresh"]),
            "warming": len(buckets["warming"]),
            "stale": len(buckets["stale"]),
            "dead": len(buckets["dead"]),
            "no_date": len(buckets["nodate"]),
        },
        "total_asking": total_asking,
        "stale_dead_value": stale_value,
        "revenue": revenue,
        "dead": bucket_json(buckets["dead"]),
        "stale": bucket_json(buckets["stale"]),
        "sold_by_category": dict(data["sold_by_cat"]),
        "median_days_to_sell": (
            sorted(d for d, _ in data["sell_times"])[len(data["sell_times"]) // 2]
            if data["sell_times"] else None),
    }
    return "\n".join(lines), report_json


def mark_pulled(db_path, dead_items):
    """--pull: set status='pulled' on dead listings, after typed
    confirmation. Never runs without --pull AND typing PULL."""
    if not dead_items:
        print("Nothing dead to pull.")
        return
    print("\nAbout to mark these as PULLED in the database:")
    for item in dead_items:
        print(f"  - {item['name']} ({item['age_days']} days, "
              f"{money(item['list_price'])})")
    print("This only changes their status in inventory.db — it does NOT")
    print("delete the Facebook listing. You still pull that in the app.")
    confirm = input("Type PULL to confirm, anything else to cancel: ").strip()
    if confirm != "PULL":
        print("Cancelled — nothing changed.")
        return
    con = sqlite3.connect(db_path)
    ids = [item["id"] for item in dead_items]
    con.execute(
        f"UPDATE items SET status='pulled' WHERE id IN "
        f"({','.join('?' * len(ids))})", ids)
    con.commit()
    print(f"Marked {con.total_changes} listing(s) as pulled.")
    con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stale-listing analyzer for Mike's Marketplace inventory.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="path to inventory.db "
                             "(default: ~/workspace/marketplace/inventory.db)")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS,
                        help="days old before a listing counts as stale "
                             "(default 30)")
    parser.add_argument("--dead-days", type=int, default=DEAD_DAYS,
                        help="days old before a listing counts as dead "
                             "(default 60)")
    parser.add_argument("--as-of", type=str, default=None,
                        help="report date as YYYY-MM-DD (default: today)")
    parser.add_argument("--markdown", type=Path, default=None,
                        help="also write the report as a Markdown file")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the report data as JSON")
    parser.add_argument("--pull", action="store_true",
                        help="mark 60+ day dead listings as 'pulled' "
                             "in the DB (asks you to type PULL first)")
    args = parser.parse_args(argv)

    today = parse_date(args.as_of) if args.as_of else date.today()
    if today is None:
        print(f"Bad --as-of date: {args.as_of!r} (use YYYY-MM-DD)",
              file=sys.stderr)
        return 2
    if not args.db.exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        print("Point --db at your inventory.db, or copy the sample DB "
              "from the README.", file=sys.stderr)
        return 2

    items = load_items(args.db)
    data = analyze(items, today, args.stale_days, args.dead_days)
    text, report_json = build_report(data, today, args.dead_days)
    print(text)

    if args.markdown:
        # First line becomes the Markdown H1.
        args.markdown.write_text("# " + text + "\n", encoding="utf-8")
        print(f"\nWrote Markdown report: {args.markdown}")
    if args.json:
        args.json.write_text(json.dumps(report_json, indent=2),
                             encoding="utf-8")
        print(f"Wrote JSON report: {args.json}")
    if args.pull:
        mark_pulled(args.db, data["buckets"]["dead"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
