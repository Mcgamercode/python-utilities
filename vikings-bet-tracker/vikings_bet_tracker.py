#!/usr/bin/env python3
"""Vikings prediction + bet tracker.

Log your Vikings predictions WITH a percentage before kickoff, log friendly
bets (game winner, coin toss, first score), then record the final score and
let the tool score everything: your prediction record, how honest your
percentages are, and who owes whom.

Why this exists: Mike bets with his Detroit-fan friends off prediction data
and never watches the games. Writing the percentage down BEFORE the game is
the whole discipline — after the game, memory rewrites itself.

Usage:
    python vikings_bet_tracker.py seed            # first run: sample data
    python vikings_bet_tracker.py games           # list games
    python vikings_bet_tracker.py predict --game Bills --pick Vikings --pct 55
    python vikings_bet_tracker.py bet --game Bills --type game --pick Vikings --amount 20 --friend "Name"
    python vikings_bet_tracker.py result --game Bills --vikings-score 27 --opp-score 24 --coin-toss Vikings --first-score Bills
    python vikings_bet_tracker.py report          # standings, calibration, money

Data lives in bets.json next to this script (use --data PATH to move it).
Nothing is ever deleted — results only ever get added, never removed.
Stdlib only: argparse, json, datetime, pathlib. No pip install needed.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE / "bets.json"

def load_data(path):
    """Read the bet book. Returns {'games': [...]} (empty book if no file)."""
    if not path.exists():
        return {"games": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(path, data):
    """Write the bet book back to disk, human-readable JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def next_id(data):
    """Next free game id (1-based, keeps growing, never reused)."""
    ids = [g["id"] for g in data["games"]]
    return max(ids, default=0) + 1


def find_game(data, query):
    """Find one game by id (e.g. 2) or by opponent name fragment (e.g. Bills).

    Errors out if nothing matches or if the fragment matches two games.
    """
    query = str(query).strip()
    if query.isdigit():
        for g in data["games"]:
            if g["id"] == int(query):
                return g
        sys.exit(f"No game with id {query}. Run `games` to see the list.")
    matches = [g for g in data["games"]
               if query.lower() in g["opponent"].lower()]
    if not matches:
        sys.exit(f"No game vs anyone matching '{query}'. Run `games` to see the list.")
    if len(matches) > 1:
        names = ", ".join(f"#{g['id']} {g['opponent']} ({g['date']})" for g in matches)
        sys.exit(f"'{query}' matches more than one game: {names}. Use the id.")
    return matches[0]


def winner_of(game):
    """Who won, from the recorded score. None until a result is entered."""
    if game.get("vikings_score") is None or game.get("opp_score") is None:
        return None
    if game["vikings_score"] == game["opp_score"]:
        return "Tie"
    return "Vikings" if game["vikings_score"] > game["opp_score"] else game["opponent"]


def label(game):
    """One-line label: '#2 vs Buffalo Bills — Mon 2026-11-09'."""
    when = date.fromisoformat(game["date"]).strftime("%a %Y-%m-%d")
    place = "vs" if game["home"] else "at"
    return f"#{game['id']} {place} {game['opponent']} — {when}"


def cmd_seed(args):
    """First run: build bets.json with the Nov 1 Lions game (already scored,
    with Mike's real 51% Vikings pick) plus the next three scheduled games."""
    if args.data.exists() and not args.force:
        sys.exit(f"{args.data} already exists — use --force to re-seed it.")
    data = {"games": [
        {
            "id": 1, "date": "2026-11-01", "week": 8,
            "opponent": "Detroit Lions", "home": False,
            "vikings_score": 15, "opp_score": 19,
            "coin_toss": "Lions", "first_score": "Lions",
            "predictions": [
                {"pick": "Vikings", "pct": 51,
                 "note": "Vikings 6-0 going in; first real test",
                 "logged": "2026-11-01"},
            ],
            "bets": [],
        },
        {"id": 2, "date": "2026-11-09", "week": 9,
         "opponent": "Buffalo Bills", "home": True,
         "vikings_score": None, "opp_score": None,
         "coin_toss": None, "first_score": None,
         "predictions": [], "bets": []},
        {"id": 3, "date": "2026-11-15", "week": 10,
         "opponent": "Green Bay Packers", "home": False,
         "vikings_score": None, "opp_score": None,
         "coin_toss": None, "first_score": None,
         "predictions": [], "bets": []},
        {"id": 4, "date": "2026-11-22", "week": 11,
         "opponent": "San Francisco 49ers", "home": False,
         "vikings_score": None, "opp_score": None,
         "coin_toss": None, "first_score": None,
         "predictions": [], "bets": []},
    ]}
    save_data(args.data, data)
    print(f"Seeded {args.data} with 4 games:")
    print("  #1 at Lions Nov 1 — FINAL 15-19, your 51% Vikings pick: WRONG")
    print("  #2 vs Bills Mon Nov 9 (MNF, 7:15 PM CT) — log your pick before kickoff")
    print("  #3 at Packers Sun Nov 15")
    print("  #4 at 49ers Sun Nov 22 (Mexico City, SNF)")


def cmd_add_game(args):
    """Schedule a game you want to predict on later."""
    data = load_data(args.data)
    date.fromisoformat(args.date)  # validates YYYY-MM-DD, errors out if bad
    game = {
        "id": next_id(data), "date": args.date, "week": args.week,
        "opponent": args.opponent, "home": args.home,
        "vikings_score": None, "opp_score": None,
        "coin_toss": None, "first_score": None,
        "predictions": [], "bets": [],
    }
    data["games"].append(game)
    save_data(args.data, data)
    print(f"Added {label(game)}")


def cmd_games(args):
    """List every game: result if played, days-to-kickoff if not."""
    data = load_data(args.data)
    if not data["games"]:
        print("No games yet. Run `seed` for sample data or `add-game` to add one.")
        return
    today = date.today()
    for g in sorted(data["games"], key=lambda x: x["date"]):
        w = winner_of(g)
        if w is None:
            days = (date.fromisoformat(g["date"]) - today).days
            when = "today" if days == 0 else f"in {days} day(s)" if days > 0 else f"{-days} day(s) ago (no result yet)"
            preds = f", {len(g['predictions'])} prediction(s) logged" if g["predictions"] else " — NO PREDICTION LOGGED YET"
            print(f"{label(g)} — {when}{preds}")
        else:
            print(f"{label(g)} — FINAL Vikings {g['vikings_score']}-{g['opp_score']} "
                  f"({w} won, {len(g['predictions'])} prediction(s), {len(g['bets'])} bet(s))")


def _check_open(game):
    """Predictions and bets only count if logged BEFORE the result exists."""
    if winner_of(game) is not None:
        sys.exit(f"{label(game)} already has a result — predictions and bets "
                 f"have to be logged BEFORE the game, that's the whole point.")


def _normalise_pick(game, pick):
    """Accept 'Vikings', 'Vikes', or the opponent's name / fragment."""
    pick = pick.strip()
    if pick.lower() in ("vikings", "vikes", "min", "minnesota"):
        return "Vikings"
    if pick.lower() in game["opponent"].lower() or game["opponent"].lower() in pick.lower():
        return game["opponent"]
    sys.exit(f"Pick must be Vikings or {game['opponent']} (you gave '{pick}').")


def cmd_predict(args):
    """Log a prediction with a percentage. 50-99: below 50% means you'd pick
    the other side, and 100% is a lie nobody believes."""
    data = load_data(args.data)
    game = find_game(data, args.game)
    _check_open(game)
    if not 50 <= args.pct <= 99:
        sys.exit("pct must be 50-99. Under 50% means pick the other team.")
    game["predictions"].append({
        "pick": _normalise_pick(game, args.pick),
        "pct": args.pct, "note": args.note or "",
        "logged": str(date.today()),
    })
    save_data(args.data, data)
    print(f"Logged: {args.pct}% {game['predictions'][-1]['pick']} to win {label(game)}")


def cmd_bet(args):
    """Log a friendly bet: game winner, coin toss, or first score."""
    data = load_data(args.data)
    game = find_game(data, args.game)
    _check_open(game)
    if args.amount <= 0:
        sys.exit("amount must be more than 0.")
    game["bets"].append({
        "type": args.type, "pick": _normalise_pick(game, args.pick),
        "amount": args.amount, "friend": args.friend,
    })
    save_data(args.data, data)
    print(f"Bet logged: ${args.amount} with {args.friend} — "
          f"{game['bets'][-1]['pick']} on {args.type} ({label(game)})")


def cmd_result(args):
    """Enter the final score (plus coin toss / first score if you bet on them)
    and score every prediction and bet on that game on the spot."""
    data = load_data(args.data)
    game = find_game(data, args.game)
    if winner_of(game) is not None:
        sys.exit(f"{label(game)} already has a result recorded.")
    game["vikings_score"] = args.vikings_score
    game["opp_score"] = args.opp_score
    if args.coin_toss:
        game["coin_toss"] = _normalise_pick(game, args.coin_toss)
    if args.first_score:
        game["first_score"] = _normalise_pick(game, args.first_score)
    save_data(args.data, data)

    w = winner_of(game)
    print(f"{label(game)} — FINAL Vikings {game['vikings_score']}-{game['opp_score']}: {w} won")
    for p in game["predictions"]:
        ok = p["pick"] == w
        print(f"  Prediction {p['pct']}% {p['pick']}: {'RIGHT' if ok else 'WRONG'}")
    for b in game["bets"]:
        if b["type"] == "game":
            won = b["pick"] == w
        elif b["type"] == "coin-toss":
            won = game["coin_toss"] is not None and b["pick"] == game["coin_toss"]
        else:  # first-score
            won = game["first_score"] is not None and b["pick"] == game["first_score"]
        print(f"  Bet ${b['amount']} with {b['friend']} ({b['type']}, {b['pick']}): "
              f"{'WON +$' + str(b['amount']) if won else 'LOST -$' + str(b['amount'])}")


def _bet_won(game, bet):
    """True/False for one bet, using the recorded result. None if unscored."""
    w = winner_of(game)
    if w is None:
        return None
    if bet["type"] == "game":
        return bet["pick"] == w
    if bet["type"] == "coin-toss":
        return game.get("coin_toss") is not None and bet["pick"] == game["coin_toss"]
    return game.get("first_score") is not None and bet["pick"] == game["first_score"]


def cmd_report(args):
    """Standings: prediction record, calibration (are your % honest?),
    money won/lost overall and per friend, and what's coming up."""
    data = load_data(args.data)
    scored = [g for g in data["games"] if winner_of(g) is not None]
    upcoming = [g for g in data["games"] if winner_of(g) is None]

    print("VIKINGS PREDICTION + BET TRACKER")
    print("=" * 40)

    # --- Predictions ---
    preds = [(g, p) for g in scored for p in g["predictions"]]
    if preds:
        right = sum(1 for g, p in preds if p["pick"] == winner_of(g))
        print(f"\nPREDICTIONS: {right}-{len(preds) - right} ({right / len(preds):.0%} right)")
        # Calibration: bucket the percentages, show the hit rate in each.
        buckets = [("50-59%", 50, 59), ("60-69%", 60, 69), ("70%+", 70, 99)]
        for name, lo, hi in buckets:
            in_bucket = [(g, p) for g, p in preds if lo <= p["pct"] <= hi]
            if in_bucket:
                hits = sum(1 for g, p in in_bucket if p["pick"] == winner_of(g))
                print(f"  When you said {name}: {hits}/{len(in_bucket)} right "
                      f"({hits / len(in_bucket):.0%} — honest would be ~{lo}-{hi}%)")
        if right:
            avg_right = sum(p["pct"] for g, p in preds if p["pick"] == winner_of(g)) / right
            print(f"  Avg confidence on picks you got right: {avg_right:.0f}%")
        if len(preds) - right:
            avg_wrong = sum(p["pct"] for g, p in preds if p["pick"] != winner_of(g)) / (len(preds) - right)
            print(f"  Avg confidence on picks you got wrong: {avg_wrong:.0f}%")
    else:
        print("\nPREDICTIONS: none scored yet — log one before the next game.")

    # --- Bets / money ---
    bets = [(g, b) for g in scored for b in g["bets"]]
    if bets:
        won = [b for g, b in bets if _bet_won(g, b)]
        lost = [b for g, b in bets if _bet_won(g, b) is False]
        net = sum(b["amount"] for b in won) - sum(b["amount"] for b in lost)
        print(f"\nBETS: {len(won)} won, {len(lost)} lost — net {'+$' if net >= 0 else '-$'}{abs(net)}")
        per_friend = {}
        for g, b in bets:
            per_friend[b["friend"]] = per_friend.get(b["friend"], 0) + (
                b["amount"] if _bet_won(g, b) else -b["amount"])
        for friend, amount in sorted(per_friend.items(), key=lambda kv: -kv[1]):
            print(f"  vs {friend}: {'+$' if amount >= 0 else '-$'}{abs(amount)}")
    else:
        print("\nBETS: none scored yet.")

    # --- Upcoming ---
    if upcoming:
        print("\nUPCOMING:")
        today = date.today()
        for g in sorted(upcoming, key=lambda x: x["date"]):
            days = (date.fromisoformat(g["date"]) - today).days
            status = "PREDICTION LOGGED" if g["predictions"] else "NO PREDICTION YET — log one before kickoff"
            print(f"  {label(g)} (in {days} day(s)) — {status}")


def main():
    parser = argparse.ArgumentParser(
        description="Vikings prediction + bet tracker — log the % BEFORE the game, score it after.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA,
                        help="bet book file (default: bets.json next to this script)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("seed", help="first run: sample data (Nov 1 game + next 3)")
    p.add_argument("--force", action="store_true", help="overwrite existing bets.json")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("add-game", help="schedule a game")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--opponent", required=True)
    p.add_argument("--home", action="store_true", help="home game (default: away)")
    p.add_argument("--week", type=int, default=0)
    p.set_defaults(func=cmd_add_game)

    sub.add_parser("games", help="list all games").set_defaults(func=cmd_games)

    p = sub.add_parser("predict", help="log a prediction with a percentage (before kickoff)")
    p.add_argument("--game", required=True, help="game id or opponent name fragment")
    p.add_argument("--pick", required=True, help="Vikings or the opponent")
    p.add_argument("--pct", type=int, required=True, help="your confidence, 50-99")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("bet", help="log a friendly bet (before kickoff)")
    p.add_argument("--game", required=True, help="game id or opponent name fragment")
    p.add_argument("--type", required=True, choices=["game", "coin-toss", "first-score"])
    p.add_argument("--pick", required=True, help="Vikings or the opponent")
    p.add_argument("--amount", type=float, required=True, help="dollars")
    p.add_argument("--friend", required=True, help="who you're betting against")
    p.set_defaults(func=cmd_bet)

    p = sub.add_parser("result", help="enter the final score and score everything")
    p.add_argument("--game", required=True, help="game id or opponent name fragment")
    p.add_argument("--vikings-score", type=int, required=True)
    p.add_argument("--opp-score", type=int, required=True)
    p.add_argument("--coin-toss", help="who won the toss: Vikings or opponent")
    p.add_argument("--first-score", help="who scored first: Vikings or opponent")
    p.set_defaults(func=cmd_result)

    sub.add_parser("report", help="standings, calibration, money").set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
