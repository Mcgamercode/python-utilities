#!/usr/bin/env python3
"""term-dict — a local working dictionary for the terminal.

Leave it open, type a word, get back:
  - definitions (with part of speech)
  - pronunciation (IPA) + spoken audio when available
  - root words / origin (etymology)
  - example sentences
  - tech acronyms and abbreviations, explained in plain English

How it works (no AI needed by default):
  1. Free Dictionary API (dictionaryapi.dev, free, no key) for
     definitions, phonetics, audio and examples.
  2. Wiktionary for etymology (word origins / roots).
  3. A built-in map of common tech/security acronyms.
  4. NLTK WordNet as an offline fallback, when installed.

Local AI is an OPTIONAL enrichment layer, not the source of truth:
  run with --ai (or type !ai in the REPL) and, when Ollama is reachable
  on localhost:11434, the tool asks a local model for one extra example
  sentence and a plain-English origin note. That output is clearly
  labeled AI-generated. Definitions always come from the dictionary,
  because a model can invent a confident-sounding wrong definition.

Stdlib only. Runs on Termux/Android, Windows PowerShell, WSL and Linux.

Usage:
  python dict.py               # open the REPL, leave it running
  python dict.py serendipity   # one-shot lookup, then exit
  python dict.py --ai          # REPL with Ollama enrichment on
  python dict.py --ai quixotic # one-shot lookup with enrichment

REPL commands:
  !help      show this help        !history  last 20 lookups
  !play      hear the last word    !say      speak the last word (espeak)
  !ai        toggle Ollama help    !clear    clear the screen
  !quit      exit (Ctrl-D works too)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

VERSION = "1.0.0"
HISTORY_FILE = os.path.expanduser("~/.terminal_dict_history.json")
DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
WIKI_API = "https://en.wiktionary.org/w/api.php"
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ---------------------------------------------------------------- acronyms
# Common tech / security shorthand, in plain English. Checked alongside
# the dictionary so "API" or "JSON" gets a real answer instead of "not found".
ACRONYMS = {
    "2FA": ("Two-Factor Authentication",
            "Logging in with two proofs, usually a password plus a code from your phone.",
            "Turn on 2FA so a stolen password alone can't open your account."),
    "AD": ("Active Directory",
           "Microsoft's system for managing users, computers and permissions on a network.",
           "The new hire's account was created in AD this morning."),
    "AI": ("Artificial Intelligence",
           "Software that learns patterns from data instead of following only fixed rules.",
           "The spam filter uses AI to spot new scams."),
    "API": ("Application Programming Interface",
            "A set of rules that lets two programs talk to each other.",
            "The weather app pulls its forecast from an API."),
    "ASCII": ("American Standard Code for Information Interchange",
              "The old 128-character table mapping letters and symbols to numbers.",
              "Plain ASCII text has no formatting, just characters."),
    "BIOS": ("Basic Input/Output System",
             "The firmware that starts a computer before the operating system loads.",
             "I entered the BIOS to change the boot order."),
    "CDN": ("Content Delivery Network",
            "Servers spread around the world that serve copies of a site from near you.",
            "The CDN makes the site load fast everywhere."),
    "CI": ("Continuous Integration",
           "Automatically building and testing code every time it changes.",
           "CI caught the bug before it reached users."),
    "CLI": ("Command-Line Interface",
            "Typing commands in a terminal instead of clicking buttons.",
            "I manage the server over the CLI."),
    "CPU": ("Central Processing Unit",
            "The chip that runs the instructions of every program.",
            "That render is maxing out the CPU."),
    "CRUD": ("Create, Read, Update, Delete",
             "The four basic operations for stored data.",
             "The app needs full CRUD on the notes table."),
    "CSRF": ("Cross-Site Request Forgery",
             "Tricking a logged-in browser into making a request the user never meant.",
             "The form now carries a CSRF token."),
    "CSS": ("Cascading Style Sheets",
            "The language that styles how a web page looks.",
            "One CSS change recolored the whole site."),
    "CTF": ("Capture The Flag",
            "A security competition where you solve hacking challenges to score points.",
            "We spent the weekend on a beginner CTF."),
    "CVE": ("Common Vulnerabilities and Exposures",
            "A public ID for a known security flaw, like CVE-2024-1234.",
            "Check whether that CVE affects our version."),
    "CVSS": ("Common Vulnerability Scoring System",
             "The 0–10 score that rates how bad a vulnerability is.",
             "A CVSS of 9.8 means patch it now."),
    "CWE": ("Common Weakness Enumeration",
            "A catalog of the types of software mistakes that cause vulnerabilities.",
            "That bug maps to CWE-89, SQL injection."),
    "DDoS": ("Distributed Denial of Service",
             "Flooding a target with traffic from many machines until it can't respond.",
             "The site went down in a DDoS attack."),
    "DHCP": ("Dynamic Host Configuration Protocol",
             "The service that hands out IP addresses on a network automatically.",
             "The router's DHCP gave my laptop 192.168.1.42."),
    "DNS": ("Domain Name System",
            "The internet's phone book: turns names like google.com into IP addresses.",
            "The site wouldn't load because DNS was down."),
    "EDR": ("Endpoint Detection and Response",
            "Security software on each computer that watches for attacks and can stop them.",
            "EDR flagged the suspicious script instantly."),
    "FTP": ("File Transfer Protocol",
            "An old protocol for moving files between computers.",
            "We used FTP to upload the files."),
    "GPU": ("Graphics Processing Unit",
            "A chip built for parallel math, used for graphics and AI work.",
            "The model trains ten times faster on a GPU."),
    "GUI": ("Graphical User Interface",
            "Buttons, windows and menus instead of typed commands.",
            "The app has a clean GUI for beginners."),
    "HDD": ("Hard Disk Drive",
            "Storage that keeps data on spinning magnetic disks.",
            "The old HDD clicks when it spins up."),
    "HTML": ("HyperText Markup Language",
             "The language that structures a web page's content.",
             "Every page starts with HTML."),
    "HTTP": ("HyperText Transfer Protocol",
             "The protocol browsers use to fetch web pages.",
             "The request went out over HTTP."),
    "HTTPS": ("HyperText Transfer Protocol Secure",
             "HTTP wrapped in encryption, so nobody between you and the site can read it.",
             "Always look for HTTPS before logging in."),
    "IDE": ("Integrated Development Environment",
            "A code editor with building, testing and debugging built in.",
            "I write Python in my IDE."),
    "IDS": ("Intrusion Detection System",
            "A watcher that alerts when network traffic looks like an attack.",
            "The IDS caught the port scan."),
    "IP": ("Internet Protocol",
            "The addressing scheme every device on a network uses.",
            "Each device gets its own IP address."),
    "IPS": ("Intrusion Prevention System",
            "Like an IDS, but it blocks the attack instead of only alerting.",
            "The IPS dropped the malicious packets."),
    "JSON": ("JavaScript Object Notation",
             "A plain-text format for structured data, built from objects and lists.",
             "The API returns its data as JSON."),
    "JWT": ("JSON Web Token",
            "A signed token a server gives you after login to prove who you are.",
            "The app stores a JWT after you sign in."),
    "K8S": ("Kubernetes",
            "A system for running and scaling containers across many machines.",
            "The service runs on K8s."),
    "LAN": ("Local Area Network",
            "The network inside one place, like a home or office.",
            "The printer is on the LAN."),
    "LDAP": ("Lightweight Directory Access Protocol",
             "The protocol apps use to look up users in a directory like Active Directory.",
             "Login checks your account over LDAP."),
    "LFI": ("Local File Inclusion",
            "A web flaw that lets an attacker read files on the server.",
            "The LFI let them read /etc/passwd."),
    "LLM": ("Large Language Model",
            "An AI trained on huge amounts of text that predicts and generates language.",
            "An LLM drafted the first version of the report."),
    "MAC": ("Media Access Control address",
            "The permanent hardware address burned into a network card.",
            "I filtered the Wi-Fi by MAC address."),
    "MFA": ("Multi-Factor Authentication",
            "Logging in with two or more different kinds of proof.",
            "MFA is required for the admin panel."),
    "MITM": ("Man-in-the-Middle",
            "An attacker sitting between two parties, reading or altering their traffic.",
            "Public Wi-Fi without a VPN invites a MITM attack."),
    "ML": ("Machine Learning",
            "Software that improves at a task by learning from examples.",
            "ML sorts the photos into categories."),
    "NAT": ("Network Address Translation",
            "The router trick that lets many devices share one public IP address.",
            "NAT hides your home devices behind the router."),
    "NFC": ("Near-Field Communication",
            "Short-range wireless for tap-to-pay and tap-to-pair.",
            "I paid by tapping my phone with NFC."),
    "NLP": ("Natural Language Processing",
            "AI that works with human language: reading, summarizing, translating.",
            "NLP pulled the key points out of the article."),
    "OAuth": ("Open Authorization",
             "A standard that lets you sign into one service using another, without sharing your password.",
             "I signed in with Google via OAuth."),
    "ORM": ("Object-Relational Mapper",
            "A library that lets code talk to a database using objects instead of raw SQL.",
            "The ORM turns rows into Python objects."),
    "OS": ("Operating System",
           "The software that runs a computer and manages its hardware.",
           "Linux is the OS on that box."),
    "OSINT": ("Open-Source Intelligence",
             "Gathering intelligence from public sources: sites, records, social media.",
             "OSINT turned up the company's old subdomains."),
    "OTP": ("One-Time Password",
            "A code that works once and then expires, usually for login.",
            "Enter the OTP from your authenticator app."),
    "PKI": ("Public Key Infrastructure",
            "The system of certificates and authorities that makes HTTPS and signed code work.",
            "PKI is why your browser trusts the site."),
    "QR": ("Quick Response code",
           "A square barcode a phone camera can read instantly.",
           "Scan the QR to open the link."),
    "RAID": ("Redundant Array of Independent Disks",
             "Combining several drives so data survives one drive dying.",
             "RAID 1 mirrors everything to a second disk."),
    "RAM": ("Random Access Memory",
            "The fast, temporary memory programs use while running.",
            "More RAM means more apps open at once."),
    "RCE": ("Remote Code Execution",
            "A flaw that lets an attacker run their own code on your machine.",
            "That RCE was patched within hours."),
    "REST": ("Representational State Transfer",
             "The common style for web APIs: resources at URLs, standard methods like GET and POST.",
             "The client talks to a REST API."),
    "RFI": ("Remote File Inclusion",
            "A web flaw that makes the server load and run a file from elsewhere.",
            "The RFI pulled in a malicious script."),
    "ROM": ("Read-Only Memory",
            "Memory that keeps its contents without power, like firmware.",
            "The firmware lives in ROM."),
    "SAML": ("Security Assertion Markup Language",
            "A standard for single sign-on between organizations.",
            "Work login uses SAML."),
    "SDK": ("Software Development Kit",
            "The tools, libraries and docs for building on a platform.",
            "Install the SDK before building the app."),
    "SIEM": ("Security Information and Event Management",
             "A central system that collects logs and flags suspicious patterns.",
             "The SIEM alerted on the failed logins."),
    "SOC": ("Security Operations Center",
            "The team (and room) that watches for and responds to security incidents.",
            "The SOC called about the alert at 3 AM."),
    "SQL": ("Structured Query Language",
            "The language for asking a database questions and changing its data.",
            "That report is one SQL query."),
    "SQLi": ("SQL Injection",
             "Smuggling database commands in through an input field.",
             "The login form was open to SQLi."),
    "SSH": ("Secure Shell",
            "The encrypted way to log into and control another computer.",
            "I SSH into the laptop from my phone."),
    "SSL": ("Secure Sockets Layer",
            "The old name for the encryption behind HTTPS; TLS is its successor.",
            "SSL is outdated — sites use TLS now."),
    "SSD": ("Solid-State Drive",
            "Storage on flash chips, much faster than a spinning disk.",
            "The SSD boots in seconds."),
    "SSRF": ("Server-Side Request Forgery",
             "Tricking a server into making requests to places it shouldn't reach.",
             "The SSRF hit the internal metadata service."),
    "TCP": ("Transmission Control Protocol",
            "The reliable delivery layer of the internet: packets arrive in order, or not at all.",
            "Web traffic rides on TCP."),
    "TLS": ("Transport Layer Security",
            "The encryption that keeps internet traffic private.",
            "TLS is what makes HTTPS secure."),
    "TUI": ("Text User Interface",
            "An interactive interface drawn in the terminal, with menus and keys.",
            "The tool has a simple TUI."),
    "UDP": ("User Datagram Protocol",
            "The fast, fire-and-forget delivery layer: no guarantee packets arrive.",
            "Video calls and DNS use UDP."),
    "UEFI": ("Unified Extensible Firmware Interface",
             "The modern replacement for BIOS that starts a computer.",
             "UEFI replaced BIOS on new machines."),
    "URL": ("Uniform Resource Locator",
            "A web address: where a thing lives on the internet.",
            "Paste the URL into the browser."),
    "USB": ("Universal Serial Bus",
            "The standard plug for keyboards, drives and charging.",
            "The installer is on a USB stick."),
    "UTF-8": ("Unicode Transformation Format, 8-bit",
             "The standard encoding that lets text hold nearly any character on earth.",
             "Save the file as UTF-8 to keep the accents."),
    "VM": ("Virtual Machine",
            "A whole computer running as software inside another computer.",
            "Kali runs in a VM on my laptop."),
    "VPN": ("Virtual Private Network",
            "An encrypted tunnel that hides your traffic from the local network.",
            "I use a VPN on public Wi-Fi."),
    "WAN": ("Wide Area Network",
            "A network spanning cities or countries — the internet is the biggest one.",
            "The branch office links over the WAN."),
    "WLAN": ("Wireless Local Area Network",
            "A local network over Wi-Fi instead of cables.",
            "The WLAN covers the whole house."),
    "WSL": ("Windows Subsystem for Linux",
             "Real Linux running inside Windows, no dual boot needed.",
             "I run Ubuntu through WSL."),
    "XML": ("Extensible Markup Language",
            "A strict text format for structured data, with tags like HTML.",
             "The config is stored as XML."),
    "XSS": ("Cross-Site Scripting",
             "Smuggling a script into a web page so it runs in someone else's browser.",
             "The comment box was open to XSS."),
    "YAML": ("YAML Ain't Markup Language",
             "A clean, readable format for config files.",
             "The settings live in a YAML file."),
}

# ---------------------------------------------------------------- helpers

def _bold(text):
    return "\033[1m{}\033[0m".format(text) if sys.stdout.isatty() else text


def fetch_json(url, timeout=10):
    """GET a URL and parse JSON. Returns None on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "term-dict/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


def lookup_dictionaryapi(word):
    """Free Dictionary API: definitions, phonetics, audio, examples."""
    data = fetch_json(DICT_API.format(urllib.parse.quote(word)))
    if not data or not isinstance(data, list):
        return None
    entry = data[0]
    phonetic = entry.get("phonetic") or ""
    audio = ""
    for ph in entry.get("phonetics", []):
        if not phonetic and ph.get("text"):
            phonetic = ph["text"]
        if not audio and ph.get("audio"):
            audio = ph["audio"]
    meanings = []
    for m in entry.get("meanings", []):
        defs = []
        for d in m.get("definitions", [])[:5]:
            defs.append({
                "definition": d.get("definition", ""),
                "example": d.get("example", ""),
                "synonyms": d.get("synonyms", [])[:6],
                "antonyms": d.get("antonyms", [])[:6],
            })
        if defs:
            meanings.append({"pos": m.get("partOfSpeech", ""), "defs": defs})
    if not meanings:
        return None
    return {"word": entry.get("word", word), "phonetic": phonetic,
            "audio": audio, "meanings": meanings}


def _strip_templates(text):
    """Remove {{...}} markup, keeping the words inside link-like templates.

    Templates such as {{l|en|Serendip}}, {{der|en|fro|Serendip}} and
    {{compound|en|serendip|ity}} carry the actual words as pipe-separated
    arguments; deleting them wholesale (the naive approach) leaves gaps
    like "From .". So for each innermost template we keep the argument
    segments that look like words and drop language codes, key=value
    pairs, flags and IPA.
    """
    langish = re.compile(r"^[a-z]{2,3}$")
    hyphen_code = re.compile(r"^[a-z]+(-[a-z0-9]+)+$")
    dash_short = re.compile(r"^-[a-z]{1,3}$")
    # Metadata-only templates: the etymology tree, surface-analysis notes
    # and displaced-word notes add no readable words — drop them whole.
    drop_names = {"ety", "displaced", "surf"}
    flags = {"nocap", "nocat", "pos", "t", "gloss", "lit", "tr", "ts",
             "id", "alt", "sc", "g", "g2", "g3", "n", "pl", "sg"}
    while "{{" in text:
        def _replace(match):
            inner = match.group(0)[2:-2]
            parts = inner.split("|")
            if not parts:
                return ""
            if parts[0].strip() in drop_names:
                return ""
            if len(parts) < 2:
                return ""
            kept = []
            for seg in parts[1:]:
                seg = seg.strip()
                if not seg or "=" in seg or seg.startswith("/"):
                    continue
                # "enm:philosophie" -> "philosophie"; ":inh" -> "inh".
                if ":" in seg:
                    seg = seg.split(":")[-1].strip()
                    if not seg:
                        continue
                if "<" in seg or ">" in seg:
                    continue
                if seg in flags or langish.match(seg):
                    continue
                if hyphen_code.match(seg) or dash_short.match(seg):
                    continue
                kept.append(seg)
            return " ".join(kept)
        new = re.sub(r"\{\{[^{}]*\}\}", _replace, text)
        if new == text:
            break
        text = new
    return text


def _dedupe(text):
    """Collapse an immediately repeated run of 3+ words.

    Template-heavy Wiktionary text often renders a title twice
    ("The Three Princes of Serendip The Three Princes of Serendip").
    """
    words = text.split()
    # Compare punctuation-stripped tokens: "Serendip," and "Serendip"
    # are the same word for duplication purposes.
    norm = [w.strip(".,;:!?\"'()[]{}") for w in words]
    changed = True
    while changed:
        changed = False
        for k in range(min(8, len(words) // 2), 2, -1):
            for i in range(len(words) - 2 * k + 1):
                if norm[i:i + k] == norm[i + k:i + 2 * k]:
                    del words[i + k:i + 2 * k]
                    del norm[i + k:i + 2 * k]
                    changed = True
                    break
            if changed:
                break
    return " ".join(words)


def _clean_etymology_para(para):
    """Clean one candidate paragraph. None when it is not real prose."""
    para = _strip_templates(para)
    # Strip [[link|text]] -> text, [[link]] -> link, then markup/HTML.
    para = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", para)
    para = re.sub(r"\[\[([^\]]+)\]\]", r"\1", para)
    para = re.sub(r"'''?", "", para)
    para = re.sub(r"<[^>]+>", "", para)
    para = re.sub(r"^\s*[*#:;].*$", "", para, flags=re.M)
    para = re.sub(r"\s+", " ", para).strip(" ,;:")
    para = _dedupe(para)
    para = re.sub(r"\bthe\s+the\b", "the", para, flags=re.I)
    para = re.sub(r"\s*,\s*\.", ".", para)
    para = re.sub(r",\s*,", ",", para)
    # Dropped templates leave their sentence periods behind (". . .").
    para = re.sub(r"(\.\s*){2,}", ". ", para).strip()
    # Quality gate: a stub, a lone fragment, or a pointer to another
    # etymology section is worse than no origin line at all.
    if len(para) < 20 or "etymology" in para.lower():
        return None
    # Keep it to a readable length.
    if len(para) > 600:
        para = para[:600].rsplit(" ", 1)[0] + "…"
    return para or None


def lookup_etymology(word):
    """Wiktionary: the Etymology section, markup stripped. None if absent."""
    params = {"action": "parse", "page": word, "prop": "sections",
              "format": "json"}
    data = fetch_json(WIKI_API + "?" + urllib.parse.urlencode(params))
    if not data:
        return None
    sections = data.get("parse", {}).get("sections", [])
    target = None
    for s in sections:
        line = s.get("line", "")
        if line == "Etymology" or line.startswith("Etymology "):
            # Prefer the top-level Etymology section (level 2) when present.
            if s.get("level") == 2 or target is None:
                target = s.get("index")
                if s.get("level") == 2:
                    break
    if not target:
        return None
    params = {"action": "parse", "page": word, "prop": "wikitext",
              "section": target, "format": "json"}
    data = fetch_json(WIKI_API + "?" + urllib.parse.urlencode(params))
    if not data:
        return None
    raw = data.get("parse", {}).get("wikitext", {}).get("*", "")
    if not raw:
        return None
    # Drop section header lines (===Etymology===) before taking the text.
    lines = [ln for ln in raw.splitlines()
             if not re.match(r"^=+\s*.*?\s*=+\s*$", ln.strip())]
    text = "\n".join(lines)
    # First paragraph with real prose wins. Some sections open with a
    # template-only line (an etymology tree), which cleans to nothing.
    for para in text.split("\n\n"):
        bare = para
        while "{{" in bare:
            new = re.sub(r"\{\{[^{}]*\}\}", "", bare)
            if new == bare:
                break
            bare = new
        if len(bare.strip()) < 10:
            continue
        cleaned = _clean_etymology_para(para)
        if cleaned:
            return cleaned
    return None


def lookup_wordnet(word):
    """NLTK WordNet, when installed. Offline fallback. None if unavailable."""
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        return None
    try:
        synsets = wn.synsets(word)
    except Exception:
        return None
    out = []
    for s in synsets[:4]:
        out.append({
            "pos": s.pos(),
            "definition": s.definition(),
            "examples": s.examples()[:2],
        })
    return out or None


def ollama_models():
    """List local Ollama models. None when Ollama is not reachable."""
    data = fetch_json(OLLAMA_URL + "/api/tags", timeout=5)
    if not data:
        return None
    return [m.get("name") for m in data.get("models", []) if m.get("name")]


def ollama_enrich(word, model):
    """Ask a local model for one example sentence + one origin note.

    Clearly an AI extra: never used for definitions.
    """
    payload = json.dumps({
        "model": model,
        "prompt": (
            "Word: {w}\n"
            "Write exactly two short lines, nothing else:\n"
            "1. One natural example sentence using the word '{w}'.\n"
            "2. One plain-English line on where the word comes from "
            "(its roots or origin), or 'Origin unclear.' if unsure."
        ).format(w=word),
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL + "/api/generate", data=payload,
        headers={"Content-Type": "application/json",
                 "User-Agent": "term-dict/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return (data.get("response") or "").strip() or None
    except Exception:
        return None


def play_audio(url):
    """Play a pronunciation clip with mpv/ffplay/cvlc if one exists."""
    player = None
    for cand in ("mpv", "ffplay", "cvlc"):
        if shutil.which(cand):
            player = cand
            break
    if not player:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "term-dict/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            chunk = resp.read()
        suffix = ".mp3" if ".mp3" in url else ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(chunk)
            path = f.name
        cmd = [player, "--really-quiet", path] if player == "mpv" else \
              [player, "-nodisp", "-autoexit", "-loglevel", "quiet", path] if player == "ffplay" else \
              [player, "--play-and-exit", path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
        os.unlink(path)
        return True
    except Exception:
        return False


def speak_word(word):
    """Speak the word with espeak if installed."""
    if not shutil.which("espeak"):
        return False
    try:
        subprocess.run(["espeak", word], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- history

def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(word):
    hist = load_history()
    hist.append({"word": word, "at": datetime.now().isoformat(timespec="minutes")})
    hist = hist[-500:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f)
    except Exception:
        pass


# ---------------------------------------------------------------- display

def show(word, ai=False, ai_model=None, _ai_note_done=[False]):
    """Look a word up and print the result. Returns (audio_url, word)."""
    word = word.strip()
    if not word:
        return None, None
    key = word.upper()
    found = False

    # 1. Tech shorthand, when it matches.
    acro = ACRONYMS.get(key)
    if acro:
        found = True
        name, meaning, example = acro
        print("\n{}  {}".format(_bold(word), _bold("[tech shorthand]")))
        print("  {} — {}".format(name, meaning))
        if example:
            print('  e.g. "{}"'.format(example))

    # 2. Dictionary API: definitions, phonetics, examples.
    entry = lookup_dictionaryapi(word)
    audio = ""
    if entry:
        found = True
        audio = entry.get("audio", "")
        header = entry["word"]
        if entry.get("phonetic"):
            header += "  /{}/".format(entry["phonetic"])
        print("\n{}".format(_bold(header)))
        for meaning in entry["meanings"]:
            pos = meaning["pos"]
            print("  [{}]".format(pos) if pos else "  [—]")
            for i, d in enumerate(meaning["defs"], 1):
                print("  {}. {}".format(i, d["definition"]))
                if d.get("example"):
                    print('     e.g. "{}"'.format(d["example"]))
                syns = d.get("synonyms") or []
                ants = d.get("antonyms") or []
                if syns:
                    print("     synonyms: {}".format(", ".join(syns)))
                if ants:
                    print("     antonyms: {}".format(", ".join(ants)))

    # 3. Etymology / roots.
    origin = lookup_etymology(word)
    if origin:
        found = True
        print("\n  Origin: {}".format(origin))

    # 4. Offline WordNet fallback, only when nothing else hit.
    if not found:
        wn = lookup_wordnet(word)
        if wn:
            found = True
            print("\n{}  {}".format(_bold(word), _bold("[offline: WordNet]")))
            for s in wn:
                print("  [{}] {}".format(s["pos"], s["definition"]))
                for ex in s["examples"]:
                    print('     e.g. "{}"'.format(ex))

    if not found:
        print('\n  No definition found for "{}".'.format(word))
        print("  Check the spelling, or try the singular / base form.")
        return None, word

    # 5. Optional local-AI enrichment: extra example + origin note only.
    if ai and ai_model:
        extra = ollama_enrich(word, ai_model)
        if extra:
            print("\n  [AI-generated extra — local Ollama, may be imperfect]")
            for line in extra.splitlines():
                line = line.strip()
                if line:
                    print("  " + line)
        elif not _ai_note_done[0]:
            print("\n  (Ollama enrichment unavailable right now.)")
            _ai_note_done[0] = True

    if audio:
        print("\n  (Pronunciation audio available — type !play to hear it.)")
    print()
    save_history(word)
    return audio, word


# ---------------------------------------------------------------- repl

HELP = """
Commands:
  !help      show this help
  !history   show your last 20 lookups
  !play      hear the last word (needs mpv, ffplay or cvlc)
  !say       speak the last word (needs espeak)
  !ai        toggle local-AI extras (needs Ollama on localhost:11434)
  !clear     clear the screen
  !quit      exit  (Ctrl-D works too)

Just type a word and hit Enter. Try an acronym too — API, JSON, SQLi, SIEM.
"""

BANNER = """
term-dict v{ver} — your terminal dictionary.
Type a word for definitions, roots, pronunciation and an example.
{ai_line}Type !help for commands, !quit to exit.
"""


def repl(ai=False):
    ai_model = None
    if ai:
        models = ollama_models()
        if models:
            # Prefer a small model when one is installed.
            ai_model = next((m for m in models if "3b" in m or "1b" in m),
                            models[0])
            ai = True
        else:
            print("(Ollama not reachable — AI extras off. "
                  "Start Ollama and type !ai to enable.)")
            ai = False
    ai_line = ("AI extras ON (local model: {}).\n".format(ai_model)
               if ai else "AI extras off — dictionary only. Type !ai to enable.\n")
    print(BANNER.format(ver=VERSION, ai_line=ai_line))
    last_audio, last_word = None, None
    while True:
        try:
            line = input("word> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        low = line.lower()
        if low in ("!quit", "!exit", "quit", "exit"):
            print("Bye.")
            break
        if low == "!help":
            print(HELP)
            continue
        if low == "!history":
            hist = load_history()[-20:]
            if not hist:
                print("  No lookups yet.")
            for h in hist:
                print("  {}  {}".format(h.get("at", ""), h.get("word", "")))
            continue
        if low == "!clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if low == "!ai":
            if ai:
                ai, ai_model = False, None
                print("AI extras off.")
            else:
                models = ollama_models()
                if models:
                    ai_model = next((m for m in models if "3b" in m or "1b" in m),
                                    models[0])
                    ai = True
                    print("AI extras on (local model: {}).".format(ai_model))
                else:
                    print("Ollama not reachable at {} — is it running?"
                          .format(OLLAMA_URL))
            continue
        if low == "!play":
            if last_audio:
                print("Playing…" if play_audio(last_audio)
                      else "No audio player found (install mpv or ffplay).")
            else:
                print("No audio for the last word.")
            continue
        if low == "!say":
            if last_word:
                print("Speaking…" if speak_word(last_word)
                      else "espeak is not installed.")
            else:
                print("Look a word up first.")
            continue
        if line.startswith("!"):
            print("Unknown command. Type !help.")
            continue
        last_audio, last_word = show(line, ai=ai, ai_model=ai_model)


def main(argv):
    ai = "--ai" in argv
    words = [a for a in argv[1:] if not a.startswith("-")]
    if words:
        word = " ".join(words)
        ai_model = None
        if ai:
            models = ollama_models()
            if models:
                ai_model = next((m for m in models if "3b" in m or "1b" in m),
                                models[0])
            else:
                print("(Ollama not reachable — AI extras off.)")
                ai = False
        show(word, ai=ai, ai_model=ai_model)
        return 0
    repl(ai=ai)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
