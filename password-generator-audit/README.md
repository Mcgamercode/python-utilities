# Password Generator + Strength Auditor

Generate cryptographically strong passwords and memorable passphrases,
score any single password, and audit a whole password list for weak,
common, and reused entries — the same three jobs a password manager's
generator and vault-health check do, in one offline file.

This is tool #11 in the nightly series. Password hygiene is the first
thing any IT pro, developer, or security-minded analyst gets asked
about — "is this password actually strong, and am I reusing it
anywhere?" — and the answer is usually a guess. This tool replaces the
guess with a number: entropy in bits, a crack-time estimate, and the
specific patterns (keyboard walks, sequences, dictionary words) that
make a password breakable.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\password-generator-audit
python passgen.py generate
python passgen.py generate --passphrase --words 6
python passgen.py check
python passgen.py audit passwords.txt --labels
```

**Termux (Android):**

```bash
cd ~/python-tools/password-generator-audit
python passgen.py generate
python passgen.py generate --passphrase --words 6
python passgen.py check
python passgen.py audit passwords.txt --labels
```

That's it. One file, three commands.

## What you get

```text
$ python passgen.py generate
]G"ocIVr*L|03.w5Fs`S
  password: ~131.1 bits of entropy — offline brute-force ≈ 4,622,729,366.4 trillion years

$ python passgen.py generate --passphrase --words 6
belong-tower-grateful-read-lava-peach
  passphrase: ~66.0 bits of entropy — offline brute-force ≈ 116.9 years

$ echo 'password123' | python passgen.py check
Password: p*********3  (length 11)
Classes:  lower, digit  (charset size 36)
Entropy:  ~0.0 bits  (raw 56.9, minus pattern penalties)
Crack time (offline, 10B guesses/sec): instant
Verdict:  VERY WEAK
Flags:
  - common password — in every attacker's dictionary
  - sequence '123'
  - single case only — no mixed case

$ python passgen.py audit passwords.txt --labels
LABEL        PASSWORD              VERDICT       ENTROPY  FLAGS
email        h*****2               WEAK            28.2b  single case only
bank         T***************9     VERY STRONG    111.4b  —
social       q*******3             VERY WEAK        0.0b  common password; keyboard walk; sequence
old-forum    h*****2               WEAK            28.2b  single case only; REUSED — also used by 'email'

Audited 6 passwords.
  VERY WEAK    1
  WEAK         2
  STRONG       1
  VERY STRONG  2
  1 password(s) reused across multiple accounts
  3 weak password(s) — regenerate with `python passgen.py generate`
```

## Useful flags

```bash
# 3 readable passwords (no look-alikes: 0 O 1 l I |), 16 characters
python passgen.py generate --count 3 --length 16 --readable

# Letters and digits only — for sites that reject symbols
python passgen.py generate --no-symbols

# Memorable passphrase, capitalized words, one digit on the end
python passgen.py generate --passphrase --words 5 --capitalize --append-digit

# Machine-readable output, for scripts
python passgen.py generate --count 5 --json
python passgen.py audit passwords.txt --labels --json

# Audit exits 1 if anything is WEAK or VERY WEAK — handy in a script
python passgen.py audit passwords.txt --labels --strict

# Use your own wordlist (one word per line, e.g. the EFF large list)
python passgen.py generate --passphrase --wordlist eff-large.txt
```

The audit file is one password per line, or `label: password` lines
with `--labels`. Lines starting with `#` are ignored.

## How the scoring works (the honest version)

- **Entropy** is `length × log2(charset size)`, where the charset is
  built from the character classes actually present (lower 26, upper
  26, digits 10, symbols 32). A 20-character password from all four
  classes is ~131 bits.
- **Pattern penalties.** Each detected shortcut — common password,
  keyboard walk (`qwerty`), sequence (`abc`, `123`), repeated
  character, a year, letters-only — costs 8 bits, because an attacker
  tries those patterns before brute force. A password on the
  most-common list scores **0 bits no matter how long it is** — length
  doesn't save a password that's already in the dictionary.
- **Passphrases are scored by words, not characters.** Charset math
  would call `correct-horse-battery-staple` a 174-bit password. It
  isn't — it's 4 words from a ~2,000-word list, about 44 bits. The
  tool detects word passphrases and scores them as
  `words × log2(wordlist size)` instead, and says so in the flags.
- **Crack time** assumes 10 billion guesses/second — a realistic
  offline rate for one modern GPU rig against a fast hash. Against a
  slow hash (bcrypt, Argon2) or an online login form the real time is
  far longer, so this is the pessimistic number to plan around.

Verdicts: under 28 bits VERY WEAK, under 40 WEAK, under 60 FAIR,
under 80 STRONG, 80+ VERY STRONG. As a rule of thumb: random
passwords want 16+ characters from all four classes, passphrases want
6+ words.

## The rules baked in

- **Never stores or transmits anything.** The tool has no network
  code at all. Nothing leaves your machine, ever.
- **Generated with `secrets`, not `random`.** `random` is seeded and
  predictable — fine for games, useless for passwords. `secrets`
  draws from the operating system's cryptographic randomness.
- **`check` never echoes your password.** It reads through `getpass`,
  so nothing shows on screen and nothing lands in shell history.
  (`--password` exists but warns you: the command line is logged.)
- **Audit output is masked by default.** Reports show the label, the
  verdict, and the first/last character only — never the password
  itself. Delete the audit source file when you're done; the report
  header says so every run.
- **One file, one command, no dependencies** — it runs anywhere
  Python runs, including a phone.

## The libraries lesson — 9 from the standard library, 0 to install

| Library | What it does here |
|---|---|
| `secrets` | `secrets.choice()` — the cryptographically secure random pick behind every generated password and word. The single most important import in this tool. |
| `getpass` | Reads a password for `check` without echoing it — no shoulder-surfing, no shell history. |
| `argparse` | Three subcommands (`generate`, `check`, `audit`) with `--help` for each — a real CLI, no manual string-splitting. |
| `string` | `ascii_lowercase`, `ascii_uppercase`, `digits`, `punctuation` — the character pools, built in. |
| `math` | `log2` — the entire entropy calculation is one line of math. |
| `re` | Spots repeated characters, year-like chunks, and long digit runs. |
| `collections` | `Counter` tallies verdicts and counts reused passwords in the audit summary. |
| `json` | `--json` output for every command, so a script (or your next tool) can consume the results. |
| `pathlib` | Finds and reads the audit file and wordlists on Windows *and* Android with the same code — no hardcoded paths. |

That's the point of the series: Python ships with a huge toolbox already
installed. Nine libraries, zero downloads, and it does a job people pay
a subscription for.

## What it replaces — and the savings

**1Password Individual** — password generator plus Watchtower, which
flags weak, reused, and compromised passwords in your vault. Verified
price: **$3.99/month billed annually ($47.88/year)**; new customers
see $2.99/month ($35.88) for the first year. Sources: 1Password's own
pricing as reported by reviews checked Oct–Nov 2026
(antivirusprotection.org, david alex.com, toolgpa.com — all confirm
$3.99/mo standard rate, $2.99/mo first-year promo). Checked Nov 14,
2026.

| | Paid | This tool |
|---|---|---|
| Price | $3.99/mo ($47.88/yr) | $0 |
| Random password generator | yes | yes |
| Memorable passphrase generator | yes | yes |
| Strength score + crack-time estimate | yes (Watchtower) | yes |
| Weak / common / reused audit | yes (Watchtower) | yes |
| Breach-database lookup (Have I Been Pwned) | yes | no — offline by design |
| Sync, autofill, vault storage | yes | no — generation + audit only |

**Savings: $47.88/year.** It won't store your passwords, sync them,
or check them against breach databases — that's what the subscription
buys. But for the two questions that matter most — *make me a strong
one* and *tell me which of mine are weak* — it does the job, offline,
for free.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$321–336
one-time + ~$571.62/year in subscriptions avoided.
