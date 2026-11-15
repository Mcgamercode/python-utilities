#!/usr/bin/env python3
"""
url_checker.py — URL Safety Checker (tool #7 in the nightly Python series)

Paste in a link — especially a shortened one — and get a verdict before
you click it: where the link *really* goes, and every red flag in it.

What it does
------------
1. Expands short links by following the redirect chain (bit.ly, t.co,
   tinyurl, etc.) and shows every hop with its HTTP status code.
2. Scores the final destination with a set of phishing/scam heuristics:
   lookalike (typosquat) domains, IP-literal hosts, punycode, embedded
   credentials (user@host), suspicious keywords, risky TLDs, excessive
   subdomains, non-standard ports, heavy percent-encoding, and more.
3. Optionally checks DNS resolution and the TLS certificate of the
   final site (--tls).
4. Prints a 0-100 risk score and a verdict: SAFE / CAUTION /
   SUSPICIOUS / DANGEROUS, with the exact reasons listed.

Pure standard library — no pip installs, runs on Windows PowerShell
and Termux alike. Read-only and safe by design: it only ever sends
HEAD requests (a GET fallback is used only when a server refuses HEAD),
never downloads page bodies, never submits forms, and never sends
credentials. Use --no-network for a purely offline heuristic check.

Usage
-----
    python url_checker.py https://bit.ly/3xxxxxx
    python url_checker.py https://example.com --tls
    python url_checker.py --batch links.txt --json report.json
    python url_checker.py "http://paypal-secure-login.xyz/verify" --no-network
"""

import argparse
import ipaddress
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Heuristic data
# ---------------------------------------------------------------------------

# Well-known shortener hosts (checked against the *original* URL).
SHORTENERS = {
    "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "adf.ly", "shorte.st", "bc.vc", "cutt.ly", "rb.gy", "s.id", "rebrand.ly",
    "tiny.cc", "shorturl.at", "t.ly", "v.gd", "cli.re", "bl.ink", "soo.gd",
    "qoo.ly", "lnk.bio", "linktr.ee",
}

# Brands phishers impersonate most. The checker flags domains that are one
# or two typos away from these, or that smuggle a brand name into a
# subdomain of an unrelated domain (paypal.com.evil.example).
BRANDS = {
    "paypal", "google", "microsoft", "apple", "amazon", "facebook",
    "instagram", "netflix", "steam", "chase", "bankofamerica",
    "wellsfargo", "americanexpress", "amex", "binance", "coinbase",
    "whatsapp", "telegram", "linkedin", "twitter", "youtube", "gmail",
    "outlook", "adobe", "dropbox", "ebay", "walmart", "target",
    "costco", "irs", "usps", "fedex", "ups", "dhl", "spotify",
    "disney", "hulu", "venmo", "cashapp", "zelle", "coinbase",
}

# TLDs that show up disproportionately in phishing/malware campaigns.
# (A legitimate site can use any of these — this is a nudge, not proof.)
RISKY_TLDS = {
    "zip", "mov", "tk", "ml", "ga", "cf", "gq", "xyz", "top", "buzz",
    "click", "link", "work", "live", "online", "site", "fun", "cam",
    "rest", "quest", "bar", "mom", "lat", "country", "kim", "cricket",
}

# Words that show up in phishing paths/domains far more than in normal ones.
SUSPICIOUS_WORDS = {
    "login", "signin", "sign-in", "verify", "verification", "secure",
    "security", "account", "update", "confirm", "password", "wallet",
    "free", "prize", "winner", "claim", "gift", "crypto", "bitcoin",
    "invoice", "payment", "refund", "unlock", "suspended", "limited",
    "urgent", "alert",
}

# Verdict bands on the 0-100 risk score.
BANDS = ((20, "SAFE"), (40, "CAUTION"), (70, "SUSPICIOUS"), (101, "DANGEROUS"))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def levenshtein(a, b):
    """Edit distance between two short strings (classic DP, stdlib only)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def registrable_domain(host):
    """Best-effort registrable domain: last two labels (example.com).

    Good enough for heuristic work; not a full public-suffix list.
    """
    parts = host.lower().rstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host.lower()


def domain_label(host):
    """The part of the domain before the TLD, e.g. 'paypal' from paypal.com."""
    reg = registrable_domain(host)
    return reg.rsplit(".", 1)[0] if "." in reg else reg


# ---------------------------------------------------------------------------
# Redirect following
# ---------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop urllib from following redirects so we can record each hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # returning None makes urlopen raise HTTPError instead


def follow_redirects(url, timeout=10, max_hops=10):
    """Follow a URL manually, one hop at a time.

    Returns (chain, final_url, error) where chain is a list of
    (url, status_code) pairs. Uses HEAD first; falls back to GET when a
    server refuses HEAD (some shorteners do). Only response headers are
    read — the body is never downloaded.
    """
    chain = []
    current = url
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(max_hops + 1):
        req = urllib.request.Request(current, method="HEAD")
        try:
            with opener.open(req, timeout=timeout) as resp:
                chain.append((current, resp.status))
                return chain, current, None
        except urllib.error.HTTPError as exc:
            # 3xx with our no-redirect handler lands here.
            chain.append((current, exc.code))
            location = exc.headers.get("Location")
            if exc.code in (301, 302, 303, 307, 308) and location:
                current = urllib.parse.urljoin(current, location)
                continue
            if exc.code == 405:  # HEAD not allowed — retry this hop as GET
                try:
                    req = urllib.request.Request(current, method="GET")
                    with opener.open(req, timeout=timeout) as resp:
                        chain.append((current, resp.status))
                        return chain, current, None
                except urllib.error.HTTPError as exc2:
                    chain.append((current, exc2.code))
                    location = exc2.headers.get("Location")
                    if exc2.code in (301, 302, 303, 307, 308) and location:
                        current = urllib.parse.urljoin(current, location)
                        continue
                    return chain, current, f"HTTP {exc2.code} on final hop"
                except (urllib.error.URLError, TimeoutError, OSError) as err:
                    return chain, current, f"GET failed: {err}"
            return chain, current, f"HTTP {exc.code} on final hop"
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            return chain, current, f"Could not reach host: {err}"
    return chain, current, f"Too many redirects (>{max_hops} hops)"


# ---------------------------------------------------------------------------
# Heuristic scoring
# ---------------------------------------------------------------------------

def analyse_url(url, *, network=True, timeout=10, check_tls=False):
    """Score one URL. Returns a dict with score, verdict, reasons, chain."""
    reasons = []          # (points, text)
    chain = []
    error = None
    final_url = url

    if network:
        chain, final_url, error = follow_redirects(url, timeout=timeout)
        if error:
            reasons.append((10, f"Could not fully load the link: {error}"))

    parsed = urllib.parse.urlparse(final_url or url)
    host = (parsed.hostname or "").lower()
    orig_parsed = urllib.parse.urlparse(url)
    orig_host = (orig_parsed.hostname or "").lower()

    def add(points, text):
        reasons.append((points, text))

    # --- scheme ------------------------------------------------------------
    if parsed.scheme == "http":
        add(15, "Not encrypted (plain http) — anything sent can be read")
    elif parsed.scheme not in ("https",):
        add(20, f"Unusual scheme '{parsed.scheme}' (expected http/https)")

    # --- credentials embedded in the URL -----------------------------------
    if parsed.username or parsed.password:
        add(25, "Login credentials embedded in the URL (user@host trick)")

    # --- shortener ----------------------------------------------------------
    if orig_host in SHORTENERS or registrable_domain(orig_host) in SHORTENERS:
        add(5, f"Link shortener ({orig_host}) — destination was hidden")
        if registrable_domain(host) != registrable_domain(orig_host):
            add(0, f"Short link expands to {host}")

    # --- redirect chain -----------------------------------------------------
    if len(chain) > 3:
        add(10, f"Long redirect chain ({len(chain)} hops)")
    hops_domains = {urllib.parse.urlparse(u).hostname for u, _ in chain}
    if len(hops_domains) > 1:
        add(5, f"Redirects cross {len(hops_domains)} different domains")

    if not host:
        add(30, "No host in the URL at all")
        score = sum(p for p, _ in reasons)
        return _verdict(url, final_url, chain, score, reasons, error)

    # --- IP literal host -----------------------------------------------------
    try:
        ip = ipaddress.ip_address(host)
        add(40, f"Host is a raw IP address ({ip}) — real sites use names")
        if ip.is_private:
            add(10, "IP is not a public, routable address (private/reserved range)")
    except ValueError:
        pass

    # --- punycode / lookalike characters ------------------------------------
    if "xn--" in host:
        add(25, "Punycode domain (xn--) — can hide lookalike characters")
    if re.search(r"[^\x00-\x7f]", url):
        add(15, "Non-ASCII characters in the URL — possible homoglyph trick")

    # --- domain shape ---------------------------------------------------------
    labels = host.split(".")
    if len(labels) > 4:
        add(10, f"Excessive subdomains ({len(labels) - 2} levels deep)")
    if host.count("-") >= 3:
        add(10, "Domain is stuffed with hyphens — common in fake domains")
    tld = labels[-1]
    if tld in RISKY_TLDS:
        add(15, f"Risky TLD '.{tld}' — heavily used by scam sites")

    # --- brand impersonation --------------------------------------------------
    # Check the full label AND each hyphen-separated token: phishers hide the
    # lookalike inside "paypa1-secure-login.com", not just "paypa1.com".
    label = domain_label(host)
    tokens = [label] + [t for t in label.split("-") if t]
    brand_hit = None
    for token in tokens:
        for brand in sorted(BRANDS):
            if token == brand:
                continue  # exact brand token — the real thing (or its subdomain)
            if levenshtein(token, brand) <= 2 and len(brand) >= 4:
                brand_hit = (brand, "typosquat", token)
                break
            if brand in token and token != brand:
                brand_hit = (brand, "brand-in-name", token)
                break
        if brand_hit:
            break
    if brand_hit:
        brand, kind, token = brand_hit
        if kind == "typosquat":
            add(35, f"Lookalike of '{brand}' (typosquat: '{token}' vs '{brand}')")
        else:
            add(20, f"Contains brand name '{brand}' in an unrelated domain")
    # Brand hidden in a subdomain of a different domain: paypal.com.evil.com
    if not brand_hit:
        for sub in labels[:-2]:
            for brand in BRANDS:
                if brand in sub:
                    add(30, f"Brand '{brand}' smuggled into a subdomain "
                            f"of {registrable_domain(host)}")
                    brand_hit = True
                    break
            if brand_hit:
                break

    # --- suspicious words ------------------------------------------------------
    found = sorted({w for w in SUSPICIOUS_WORDS
                    if w in host or w in parsed.path.lower()})
    if found:
        add(min(10 * len(found), 20),
            "Phishing-flavoured words: " + ", ".join(found))

    # --- port / encoding / length ----------------------------------------------
    if parsed.port and parsed.port not in (80, 443):
        add(10, f"Non-standard port {parsed.port}")
    if url.count("%") >= 5:
        add(10, "Heavy percent-encoding — often used to hide the real target")
    if len(url) > 200:
        add(10, f"Very long URL ({len(url)} chars)")
    elif len(url) > 100:
        add(5, f"Long URL ({len(url)} chars)")
    if "@" in parsed.path:
        add(10, "'@' in the path — classic credential-phishing shape")

    # --- DNS + TLS (network only) ------------------------------------------------
    if network and host and not _is_ip(host):
        try:
            socket.gethostbyname(host)
        except OSError:
            add(20, "Domain does not resolve in DNS — cannot be verified")
    if network and check_tls and parsed.scheme == "https" and host:
        tls_note = check_certificate(host, timeout)
        if tls_note:
            add(*tls_note)

    score = min(sum(p for p, _ in reasons), 100)
    return _verdict(url, final_url, chain, score, reasons, error)


def _is_ip(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _connect_tls(host, port, timeout):
    """TCP connection to host:port, tunnelling through HTTPS_PROXY if set."""
    import os
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not proxy:
        return socket.create_connection((host, port), timeout=timeout)
    p = urllib.parse.urlparse(proxy)
    sock = socket.create_connection((p.hostname, p.port or 8080),
                                    timeout=timeout)
    req = (f"CONNECT {host}:{port} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n\r\n").encode()
    sock.sendall(req)
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    status = buf.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    if " 200 " not in status:
        sock.close()
        raise OSError(f"proxy CONNECT failed: {status}")
    return sock


def check_certificate(host, timeout=10):
    """Fetch the TLS cert and flag expiry/problems.

    Returns (points, text) or None. Failures are reported, not fatal.
    Proxy-aware: if HTTPS_PROXY is set, tunnels through it with CONNECT
    (the same way urllib does), so it works behind corporate proxies.
    """
    ctx = ssl.create_default_context()
    try:
        sock = _connect_tls(host, 443, timeout)
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
    except ssl.SSLCertVerificationError as err:
        return (25, f"TLS certificate FAILED verification: {err}")
    except (OSError, ssl.SSLError) as err:
        return (10, f"Could not check TLS certificate: {err}")
    import datetime as _dt
    not_after = cert.get("notAfter")
    if not_after:
        expiry = _dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        days = (expiry - _dt.datetime.now(_dt.timezone.utc)
                .replace(tzinfo=None)).days
        if days < 0:
            return (30, "TLS certificate is EXPIRED")
        if days < 30:
            return (10, f"TLS certificate expires in {days} days")
    return None


def _verdict(original, final_url, chain, score, reasons, error):
    verdict = next(v for limit, v in BANDS if score < limit)
    return {
        "url": original,
        "final_url": final_url,
        "redirect_chain": [{"url": u, "status": s} for u, s in chain],
        "score": score,
        "verdict": verdict,
        "reasons": [{"points": p, "reason": t} for p, t in reasons],
        "error": error,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(result, *, show_chain=True):
    score, verdict = result["score"], result["verdict"]
    bar = "#" * (score // 2)
    print(f"\nURL:        {result['url']}")
    if result["final_url"] != result["url"]:
        print(f"Final URL:  {result['final_url']}")
    print(f"Risk score: {score}/100  [{bar:<50}]  {verdict}")
    if show_chain and result["redirect_chain"]:
        print("Redirect chain:")
        for hop in result["redirect_chain"]:
            print(f"  {hop['status']}  {hop['url']}")
    if result["reasons"]:
        print("Why:")
        for item in result["reasons"]:
            print(f"  +{item['points']:>2}  {item['reason']}")
    else:
        print("Why:       No red flags found.")
    if result["error"]:
        print(f"Note:       {result['error']}")
    print(f"Verdict:    {verdict} "
          f"({'safe to open' if verdict == 'SAFE' else 'do NOT open' if verdict in ('SUSPICIOUS', 'DANGEROUS') else 'open with caution'})")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check a URL before you click it: expand short links, "
                    "follow redirects, and flag phishing/scam patterns.")
    parser.add_argument("url", nargs="?",
                        help="URL to check (use --batch for many at once)")
    parser.add_argument("--batch", metavar="FILE",
                        help="file with one URL per line; checks them all")
    parser.add_argument("--json", metavar="FILE",
                        help="also write the full results as JSON")
    parser.add_argument("--no-network", action="store_true",
                        help="offline heuristic check only — no requests, "
                             "no DNS, no redirect following")
    parser.add_argument("--tls", action="store_true",
                        help="also fetch and check the TLS certificate")
    parser.add_argument("--timeout", type=int, default=10,
                        help="seconds to wait per request (default 10)")
    args = parser.parse_args(argv)

    urls = []
    if args.batch:
        path = Path(args.batch)
        if not path.is_file():
            print(f"error: batch file not found: {args.batch}", file=sys.stderr)
            return 2
        urls = [line.strip() for line in path.read_text(encoding="utf-8",
                errors="ignore").splitlines()
                if line.strip() and not line.strip().startswith("#")]
        if not urls:
            print(f"error: no URLs in {args.batch}", file=sys.stderr)
            return 2
    elif args.url:
        urls = [args.url]
    else:
        parser.print_help()
        return 2

    results = []
    for url in urls:
        if not urllib.parse.urlparse(url).scheme:
            url = "https://" + url  # bare domain? assume https
        result = analyse_url(url, network=not args.no_network,
                             timeout=args.timeout, check_tls=args.tls)
        results.append(result)
        print_report(result)

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2),
                                   encoding="utf-8")
        print(f"\nJSON report written to {args.json}")

    if len(results) > 1:
        counts = {}
        for r in results:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print("\nSummary: " + ", ".join(
            f"{n} {v}" for v, n in sorted(counts.items())))

    worst = max(r["score"] for r in results)
    return 1 if worst >= 40 else 0


if __name__ == "__main__":
    raise SystemExit(main())
