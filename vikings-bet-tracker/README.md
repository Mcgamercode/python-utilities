# Vikings Prediction + Bet Tracker

Log your Vikings prediction **with a percentage before kickoff**, log the
friendly bets (game winner, coin toss, first score), then enter the final
score and let it score everything: your prediction record, whether your
percentages are honest, and who owes whom.

**Where it came from:** Mike bets with his Detroit-fan friends off
prediction data and never watches the games — and after every game his
memory rewrites what he "knew". Writing the % down *before* kickoff is the
whole discipline. This is tool #3 in the nightly series.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## First run — seed the sample data

The seed loads the Nov 1 Lions game (already scored, with your real 51%
Vikings pick) plus the next three scheduled games, so the Bills game is
ready for your prediction before Monday night.

**Windows PowerShell:**

```powershell
cd ~\python-tools\vikings-bet-tracker
python vikings_bet_tracker.py seed
```

**Termux (Android):**

```bash
cd ~/python-tools/vikings-bet-tracker
python vikings_bet_tracker.py seed
```

## The weekly loop — three commands

**1. Before the game — log your prediction (with the %):**

```bash
python vikings_bet_tracker.py predict --game Bills --pick Vikings --pct 55 --note "home, both teams 6-1"
```

**2. Before the game — log the friendly bet:**

```bash
python vikings_bet_tracker.py bet --game Bills --type game --pick Vikings --amount 20 --friend "Name"
```

Bet types: `game` (who wins), `coin-toss`, `first-score` — the three bets
you run every week. `--game` takes the game number or part of the
opponent's name (`Bills`, `Packers`, `2` all work).

**3. After the game — enter the score, it grades everything:**

```bash
python vikings_bet_tracker.py result --game Bills --vikings-score 27 --opp-score 24 --coin-toss Vikings --first-score Bills
```

**Anytime — the standings:**

```bash
python vikings_bet_tracker.py report
```

```text
PREDICTIONS: 1-1 (50% right)
  When you said 50-59%: 1/2 right (50% — honest would be ~50-59%)
BETS: 2 won, 0 lost — net +$25
  vs Test Friend: +$25
UPCOMING:
  #3 at Green Bay Packers — Sun 2026-11-15 — NO PREDICTION YET
```

**Other commands:** `games` lists everything, `add-game --date 2026-11-29
--opponent "Atlanta Falcons" --home --week 12` schedules a new one.

## The rules baked in

- **No predictions or bets after a result exists.** If you could log it
  after the game, the percentage would mean nothing. The tool refuses.
- **`--pct` must be 50–99.** Under 50% means you'd pick the other team,
  and 100% is a lie nobody believes.
- **Nothing is ever deleted.** Results only get added. Your record is your
  record — including the 51% Lions pick that missed.

## Your data

Everything lives in `bets.json` next to the script — plain JSON you can
open in any text editor. Back it up by copying the file. Use
`--data PATH` to keep the book somewhere else.

## The libraries lesson — 4 from the standard library, 0 to install

| Library | What it does here |
|---|---|
| `argparse` | Turns the commands (`predict`, `bet`, `result`, `report`) into a real CLI with `--flags` and help text — no manual string-splitting. |
| `json` | Saves and loads the whole bet book (`bets.json`) — predictions, bets, scores — in a file you can read yourself. |
| `datetime` | Parses game dates, works out "Bills game is in 2 days", and stamps when you logged each prediction. |
| `pathlib` | Finds `bets.json` next to the script on Windows *and* Android with the same code — no hardcoded `C:\` or `/home/` paths. |

That's the point of the series: Python ships with a huge toolbox already
installed. Four libraries, zero downloads, and it does a job people pay a
subscription for.

## What it replaces — and the savings

**Action Network PRO** — the bet-tracking app with pick logging and
results tracking. Verified price: **$119.99/year** (or $24.99/month) on
Action Network's own subscribe page, confirmed by reviews checked
Nov 5, 2026 (betsmart.co, betting50.com, askthebookie.com).

| | Paid | This tool |
|---|---|---|
| Price | $119.99/yr | $0 |
| Bet + prediction tracking | yes | yes |
| Works offline, your data stays yours | no | yes |

**Savings: $119.99/year.** It won't give you expert picks or live odds —
that's the part you're paying for there — but for logging *your* picks,
scoring them honestly, and settling bets with friends, it does the job.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$40–55 one-time +
~$299.87/year in subscriptions avoided.
