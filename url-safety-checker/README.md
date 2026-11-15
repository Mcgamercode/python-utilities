# URL Safety Checker

Paste in a link — especially a shortened one — and get a verdict
*before* you click it: where the link really goes, and every red flag
in it.

This is tool #7 in the nightly series — and the fourth of the
**professional** tools. Shortened links and lookalike domains are the
delivery mechanism for nearly every phishing email, fake invoice, and
"your account is locked" text. A security analyst's first move with a
suspicious link is always the same: expand it, look at the real
destination, and check it against the patterns phishers reuse. This
does that in one command, offline or online.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\url-safety-checker
python url_checker.py https://bit.ly/3xxxxxx
```

**Termux (Android):**

```bash
cd ~/python-tools/url-safety-checker
python url_checker.py https://bit.ly/3xxxxxx
```

That's it. One file, one command.

## What you get

```text
URL:        https://paypa1-secure-login.xyz/verify-account
Risk score: 70/100  [###################################               ]  DANGEROUS
Why:
  +15  Risky TLD '.xyz' — heavily used by scam sites
  +35  Lookalike of 'paypal' (typosquat: 'paypa1' vs 'paypal')
  +20  Phishing-flavoured words: account, login, secure, verify
Verdict:    DANGEROUS (do NOT open)
```

A clean link looks like this instead:

```text
URL:        https://example.com
Risk score: 0/100  [                                                  ]  SAFE
Redirect chain:
  200  https://example.com
Why:       No red flags found.
Verdict:    SAFE (safe to open)
```

Verdicts: **SAFE** (0–19), **CAUTION** (20–39), **SUSPICIOUS** (40–69),
**DANGEROUS** (70–100). The exit code is 1 when any checked URL scores
SUSPICIOUS or worse, so you can use it in a script or a CI step.

## What it checks

| Check | Why it matters |
|---|---|
| Redirect chain | Short links hide the destination — every hop is shown with its status code, so a `bit.ly` that lands on a lookalike domain can't hide |
| Typosquat / lookalike domains | `paypa1.com` is one character from `paypal.com` — edit-distance check against 35 commonly impersonated brands, including hyphen-smuggled ones like `paypa1-secure-login.com` |
| Brand in a subdomain | `paypal.com.evil.example` — the real domain is `evil.example`, the brand is just bait |
| Raw IP host | Real sites use names; `http://93.184.216.34/login` is a classic phishing shape |
| Punycode / non-ASCII | `xn--` domains and homoglyphs hide lookalike characters |
| Credentials in the URL | `http://user:pass@evil.example` — the `user@` trick |
| Risky TLDs | `.zip`, `.mov`, `.tk`, `.xyz` and friends show up in scam campaigns far out of proportion |
| Phishing words | `verify`, `secure`, `suspended`, `free-prize` in the domain or path |
| Plain http, odd ports, heavy encoding | Unencrypted, non-standard ports, and `%`-stuffed URLs are all evasion tells |
| DNS resolution | A domain that doesn't resolve can't be verified |
| TLS certificate (`--tls`) | Flags certificates expiring within 30 days (a fetch already fails outright on an expired or invalid cert) |

## Useful flags

```bash
# Check a whole list at once (one URL per line, # lines are comments)
python url_checker.py --batch links.txt

# Machine-readable copy for a report or a follow-up script
python url_checker.py --batch links.txt --json report.json

# No network at all — pure heuristic check, works fully offline
python url_checker.py "http://paypal-secure-login.xyz/verify" --no-network

# Also check the TLS certificate (expiry warning)
python url_checker.py https://example.com --tls

# Bare domain? It assumes https
python url_checker.py paypal.com
```

## The rules baked in

- **It never downloads a page body.** Only HEAD requests are sent (a
  GET fallback is used only when a server refuses HEAD), and only
  response headers are read — the tool can't accidentally run
  anything, and it can't leak anything to a malicious page.
- **It never sends credentials or submits anything.** No forms, no
  cookies, no logins. It only *looks* at links.
- **A score is a warning, not proof.** A heuristic check can't query
  live blocklists (VirusTotal, Google Safe Browsing) without an API
  key, and a legitimate site can trip a flag or two. Treat CAUTION as
  "look closer", SUSPICIOUS and DANGEROUS as "don't open it".
- **Safe exit codes.** Exit 0 means nothing scored SUSPICIOUS or
  worse; exit 1 means at least one link did — pipe a batch file
  through it in a script and act on the code.
- **Proxy-aware.** The `--tls` check tunnels through `HTTPS_PROXY`
  with a CONNECT request, so it works behind corporate proxies —
  plain socket connections to port 443 fail in those environments.
- **No dependencies.** One `.py` file, standard library only — it
  runs anywhere Python runs, including a phone.

## The libraries lesson — 7 from the standard library, 0 to install

| Library | What it does here |
|---|---|
| `urllib.request` / `urllib.parse` | Fetches the link and follows redirects hop by hop (with a custom handler that *stops* auto-redirect so each hop can be recorded); parses every URL into scheme, host, port, and path |
| `urllib.error` | Tells a 404 or a refused connection apart from a redirect, so the report can say *why* a link failed instead of just crashing |
| `re` | Spots non-ASCII/homoglyph tricks in the URL |
| `ipaddress` | Knows `93.184.216.34` is a raw IP, and whether it's a private/reserved range — no regex guessing |
| `ssl` + `socket` | Fetches the real TLS certificate and reads its expiry date; the CONNECT tunnel makes it work behind proxies |
| `argparse` | Turns the flags (`--batch`, `--json`, `--no-network`, `--tls`, `--timeout`) into a real CLI with `--help` |
| `json` | Writes the full batch results as `report.json`, so another script or a dashboard can consume the same scores |
| `pathlib` | Finds the batch file and writes the JSON report on Windows *and* Android with the same code |

That's the point of the series: Python ships with a huge toolbox
already installed. Eight libraries, zero downloads, and it does a job
people pay a subscription for.

## What it replaces — and the savings

**URLCheck** (urlcheck.app) — a paid browser extension whose whole job
is revealing the real destination of a link before you click it.
Verified price: **$19.99/year** (or $1.99/month). Source:
urlcheck.app/pricing, checked Nov 10, 2026 ("Annual $19.99/year...
Monthly $1.99/month"). That's **$19.99/year**.

| | Paid | This tool |
|---|---|---|
| Price | $19.99/yr | $0 |
| Shows the real destination of a short link | yes | yes |
| Flags lookalikes, risky TLDs, IP hosts, phishing words | no | yes |
| Batch-check a whole list, JSON report, exit codes for scripts | no | yes |
| Live blocklist verdicts (VirusTotal-style) | no | no — heuristic only, no API key needed |
| Works fully offline | no — browser extension | yes, with `--no-network` |

**Savings: $19.99/year.** It won't query live malware blocklists —
that's what a VirusTotal API key is for — but for the core job, *where
does this link actually go, and does it smell like a phish*, it does
the job, offline, in bulk, and scriptable.

## Series savings so far

See `../SAVINGS_LOG.md` — running total after tonight: ~$90–105
one-time + ~$523.74/year in subscriptions avoided.
