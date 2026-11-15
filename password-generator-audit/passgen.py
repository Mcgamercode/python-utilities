#!/usr/bin/env python3
"""passgen — password & passphrase generator + strength auditor.

Tool #11 in the nightly Python tool series.

Three jobs, one file, standard library only:

  generate   make cryptographically random passwords or memorable
             passphrases (Diceware-style, from a built-in wordlist)
  check      score ONE password: entropy, crack-time estimate, and the
             patterns that actually get accounts broken into
  audit      score a WHOLE list at once (one password per line, or
             label: password lines) and flag weak, common, and reused
             entries — the same job 1Password's Watchtower does

Security rules baked in:
  * Passwords are generated with the `secrets` module — made for this,
    unlike `random`, which is predictable.
  * Nothing is ever stored, uploaded, or sent anywhere. The tool has
    no network code at all. Audit output masks passwords by default.
  * `check` reads your password with getpass, so it never echoes on
    screen and never lands in your shell history.

Usage:
  python passgen.py generate
  python passgen.py generate --passphrase --words 6
  python passgen.py check
  python passgen.py audit passwords.txt --labels
  python passgen.py --help
"""

import argparse
import getpass
import json
import math
import re
import string
import sys
from collections import Counter
from pathlib import Path
from secrets import choice as secret_choice

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Wordlist for passphrases (Diceware-style).
# 2,054 words, so each word is worth ~11 bits of entropy:
#   4 words = 44 bits, 6 words = 66 bits, 8 words = 88 bits.
# For real-world use, 6+ words is the floor; 7-8 words is comfortable.
# Pass --wordlist your-list.txt to generate to use a bigger list instead
# (the EFF large list has 7,776 words = ~12.9 bits per word).
# ---------------------------------------------------------------------------
_WORDS = """able acid actor acute adapt add adore adult advise affair affect afraid after again age agent agree ahead alarm album alert alike alive allow alone alpha also alter always amaze amber amount ancient anger angle angry animal answer antique anxiety apart apple apply april arch area argue arise armor army around arrive arrow art artist ash ask asleep aspect assign assist assume asthma athlete atlas atom attach attack attempt attend attract august aunt author autumn average avoid awake award aware awful baby back bacon badge bag bake balance ball band bank bar bare bark barn base basic basket bath battle bay beach beam bear beard beast beat beauty become bed bee beef beer before begin behave behind being belief bell belong below belt bench bend benefit berry beside best bet better beyond bicycle bid big bike bill bind bird birth bit bite black blade blame blank blast blaze blend bless blind block blood blow blue board boat body boil bold bolt bomb bond bone book boost boot border borrow boss both bottle bottom bound bowl box boy brain branch brave bread break breath breeze brick bridge brief bright bring broad broke brook broom brother brown brush bubble bucket budget build bulb bulk bullet bump bunch burden burn burst bury bus bush business busy but butter button buy buyer by cable cage cake call calm camera camp can canal cancel candle canvas cap capital captain capture car card care career careful carpet carry cart case cash cast cat catch cattle cause cease ceiling celebrate cell cent center century certain chain chair chalk chance change channel chaos chapter charge charity chart chase cheap check cheese chef cherry chess chest chicken chief child chill chip choice choose chop church circle circus cite city civil claim clap class claw clay clean clear clerk clever click client cliff climb clinic clock close cloth cloud club coach coal coast coat code coffee coin cold collapse collar collect college color column comb come comfort comic command comment common company compare compass compete complain complete complex compose compound computer concept concern concert conclude condition conduct confess confidence confirm conflict confuse congress connect consent consider consist constant consult contact contain content contest context control cook cool cope copy core corn corner correct cost cotton couch could count county couple courage course court cousin cover crack craft crash crazy cream create credit creek crew crime crisis crisp critic crop cross crowd crown crucial cruel cruise crush cry crystal culture cup cure curious current curtain curve custom cute cut cycle dad daily dairy damage dance danger dare dark data date daughter dawn day dead deal dear death debate debt decade decide deck declare decline deep deer defeat defend define degree delay deliver demand democracy deny depart depend deposit depth deputy derive describe desert design desk despite detail detect develop device devil diagram dial diamond diary dice differ difficult dig digital dignity dilemma dim dinner direct dirt dirty disagree disappear disaster discount discover discuss disease dish dismiss display distance distinct district dive divide divorce dizzy doctor dog dollar domain donate door double doubt dove down dozen draft drag drain drama draw dream dress drift drill drink drive drop drum dry duck due dull dump dust duty dynamic each eager eagle early earn earth east easy eat echo edge edit educate effort egg eight either elbow elder elect elegant element elephant elite else email embark emerge emotion employ empty enable end enemy energy engage engine enjoy enough ensure enter entire entry envelope episode equal equip era erase error escape essay essence estate estimate ethics euro even event every evidence evil exact exam example exceed exchange excite excuse exercise exhaust exhibit exist exit exotic expand expect expense expert explain explode export expose express extend extra eye fabric face fact factor fade fail fair faith fall false fame family famous fan fancy far farm fashion fast fat fate father fault favor fear feather feature february federal fee feed feel fellow fence festival fetch fever few fiber fiction field fierce fifth fifty fight figure file fill film final finance find fine finger finish fire firm first fiscal fish fit fix flag flame flash flat flavor flee fleet flesh flex flight flip float flock flood floor flour flow flower fluid flush fly focus fog fold folk follow food fool foot for force forest forget fork form formal fortune forum forward fossil foster found fox fragile frame frank free freeze french fresh friend frog from front frost fruit fuel full fun fund funny fur furnace fury future gadget gain galaxy gallery game gap garage garden garlic gas gate gather gaze gear gem general genius genre gentle gesture ghost giant gift giggle ginger girl give glad glance glass glide glimpse globe glory glove glow glue goal goat gold golf good goose gossip govern grab grace grade grain grand grape graph grasp grass grateful grave gray great green greet grid grief grill grin grip grocery ground group grow guard guess guest guide guilt guitar gun guy habit hair half hall hammer hand handle hang happy harbor hard harm harvest hat hate have hawk hazard head heal health hear heart heat heavy heel height hello helmet help hen hero hidden high hike hill hint hip hire history hobby hold hole holiday hollow home honest honey honor hook hope horizon horn horse host hotel hour house huge human humble humor hunt hurry hurt husband ice icon idea ideal ignore image impact imply import improve inch income indeed index indoor infant info injury inner input insect inside insight inspect inspire install instant instead intact intake intend intense intent invest invite iron island issue item jacket january jar jazz jeans jelly jet jewel job join joke journal journey joy judge juice july jump june jungle junior junk jury just keep kernel kettle key kick kid kind king kiss kitchen kite kitten knee knife knight knock know lab label labor ladder lady lake lamp land lane language laptop large laser last late laugh launch lava law lawn layer lazy lead leaf league lean learn leather leave lecture left leg legal lemon lend length lens lesson let letter level library license lid life lift light like limb limit line lion lip liquid list listen little live load loan local lock log logic lonely long look loose lord lose loss lot loud love low loyal luck lunch lung machine mad magic mail main major make man manage mango manner manual many map march margin marine mark market marriage mask mass master match math matter may mayor meal mean measure meat media medical medium meet melody melt member memory mental mention menu mercy merge merit merry mess message metal meter method middle mild mile milk mill mind mine mineral minor minute miracle mirror miss mistake mix mobile mode model modern modest mom moment money monkey month moon moral more morning most mother motion motor mount mouse mouth move movie much mud mug museum music must mutual mystery nail name narrow nation native natural nature near neat neck need needle neighbor neither nerve nest net network neutral never new news next nice night nine noble nod noise none noodle noon north nose note nothing notice notion novel now number nurse nut oak obey object observe obtain obvious occur ocean odd off offer officer often oil okay old olive omit once one onion online only open opera opinion oppose option orange orbit order ordinary organ original other ought ounce outcome outer output outside oven over own owner oxygen ozone pace pack page pain paint pair palace pale palm panel panic paper parade parent park parrot part party pass past patch path patient pattern pause pay peace peach peak peanut pear pebble pedal peek peel peer peg pen pencil people pepper perfect perform perhaps period permit person pet phase phone photo phrase piano pick picnic picture piece pig pile pilot pin pine pink pioneer pipe pirate pitch pizza place plain plan plane planet plant plastic plate play plaza please plenty plot plug pocket poem poet point polar police policy polite pond pool poor pop popular porch pork port pose position positive possible post potato pound powder power praise pray precise predict prefer prepare present press pretty prevent price pride priest prime print prior prison private prize problem process produce profile profit program project promise prompt proof proper proud prove provide public pull pulse pump punch pupil pure purple purpose purse push put puzzle quality quarter queen question quick quiet quit quite quiz quote rabbit race radar radio rail rain raise rally ramp ranch random range rapid rare rate rather raven raw ray reach read ready real reason rebel recall receive recent recipe record recover recycle red reduce refer reflect reform refuse regard region regret regular reject relax release reliable relief remain remark remedy remember remind remote remove render rent repair repeat replace reply report rescue research reserve reset resist resource respect respond rest result retire return reveal review reward rhythm rib rice rich ride ridge right ring rinse rise risk river road roast rock rocket role roll roof room root rope rose rough round route royal rub rude rug rule run rural rush rust sad safe sail salad sale salt salute same sample sand save say scale scan scare scene school science scope score scout scrap scream screen script sea search season seat second secret section secure see seed seek seem select sell send senior sense sentence separate series serious serve session set settle seven shade shadow shake shall shame shape share sharp shave sheep sheet shelf shell shelter shift shine ship shirt shock shoe shoot shop shore short shot should shoulder shout show shower shut shy sick side sigh sight sign signal silence silk silly silver similar simple since sing single sink sir sister sit site six size skate sketch ski skill skin skirt sky sleep slice slide slight slim slip slope slow small smart smell smile smoke smooth snake snap sneak snow soap soccer social sock soda sofa soft soil solar soldier solid solve some son song soon sorry sort soul sound soup source south space spare spark speak special speed spell spend sphere spin spirit split spoil spoke spoon sport spot spray spread spring square squeeze stable staff stage stain stair stake stamp stand star start state station stay steady steak steal steam steel steep stem step stick still sting stir stock stomach stone stop store storm story stove straight strange straw stream street stress stretch strict strike string strip strong struggle student studio study stuff style subject submit subtle suburb such sudden suffer sugar suit summer sun super supply support supreme sure surface surge surprise surround survey survive suspect sustain swallow swamp swap swear sweet swim swing switch sword symbol symptom system table tackle tail talent talk tall tank tape target task taste tattoo taxi tea teach team tear tell temple tend tennis tent term terrible test text thank that theater their theme then theory therapy there these thing think third thought thread threat three throat through throw thumb thunder ticket tide tiger tight time tin tiny tip tired title toast today toe together toilet token tomato tomorrow tone tongue tonight tool tooth top topic torch total touch tough tour towel tower town toy trace track trade traffic trail train trait transfer trap travel tray treat tree trend trial tribe trick trim trip trophy trouble truck true trust truth try tube tune tunnel turkey turn turtle tutor twice twin twist type typical ugly ultimate unable uncle under unfair uniform union unique unit united universe unknown unless until update upon upper upset urban urge urgent usage use useful usual utility vacant vacuum vague valid valley value van vapor variety various vast vegetable vehicle vendor venture verb verify version very vessel veteran via victim victory video view village vine vintage violin virtual virus visa vision visit visual vital vivid vocal voice volume vote voyage wage wait wake walk wall wander want war warm warn wash waste watch water wave way weak wealth weapon wear weather weave web wedding weekend weird welcome well west wet whale what wheat wheel when where which while whisper white whole why wide wife wild will win wind window wine wing winner winter wipe wire wisdom wise wish with witness wolf woman wonder wood wool word work world worry worth would wound wrap wrist write wrong yard year yellow yes yesterday yet yield yoga young youth zero zone zoo"""
WORDS = _WORDS.split()
WORDS_SET = set(WORDS)

# ---------------------------------------------------------------------------
# Most-common-passwords list (top ~120 from public breach data, e.g. the
# RockYou top list). Used ONLY to flag passwords that are already in every
# attacker's dictionary. This list contains no real user data.
# ---------------------------------------------------------------------------
COMMON_PASSWORDS = {
    "123456", "12345", "123456789", "password", "iloveyou", "princess",
    "1234567", "rockyou", "12345678", "abc123", "nicole", "daniel",
    "babygirl", "monkey", "lovely", "jessica", "654321", "michael",
    "ashley", "qwerty", "111111", "iloveu", "000000", "michelle",
    "tigger", "sunshine", "chocolate", "password1", "soccer", "anthony",
    "friends", "butterfly", "purple", "angel", "jordan", "liverpool",
    "justin", "loveme", "fuckyou", "123123", "football", "secret",
    "andrea", "carlos", "jennifer", "joshua", "bubbles", "1234567890",
    "superman", "hannah", "amanda", "loveyou", "pretty", "basketball",
    "andrew", "angels", "tweety", "flower", "playboy", "elizabeth",
    "hottie", "tinkerbell", "charlie", "samantha", "barbie", "chelsea",
    "lovers", "team", "jasmine", "brandon", "666666", "shadow",
    "melissa", "eminem", "matthew", "robert", "danielle", "forever",
    "family", "jonathan", "987654321", "computer", "whatever", "dragon",
    "vanessa", "cookie", "naruto", "summer", "sweety", "spongebob",
    "joseph", "junior", "softball", "taylor", "yellow", "daniela",
    "lauren", "mickey", "princesa", "alexandra", "alexis", "jesus",
    "hunter", "master", "hello", "freedom", "charlie", "qwertyuiop",
    "admin", "welcome", "login", "passw0rd", "letmein", "trustno1",
    "starwars", "whatever1", "baseball", "superman1", "michael1",
    "password123", "qwerty123", "1qaz2wsx", "aa123456", "abcd1234",
    "1234", "12345678910", "11111111", "00000000", "121212",
    "pass", "test", "guest", "root", "admin123", "changeme",
}

AMBIGUOUS = set("0O1lI|")  # characters people misread

# Keyboard rows — a 4+ character run along one row is a "walk", and
# attackers try every walk before they try anything clever.
KEYBOARD_ROWS = [
    "1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "0987654321", "poiuytrewq", "lkjhgfdsa", "mnbvcxz",
]

# ---------------------------------------------------------------------------
# Entropy, crack-time, and verdicts
# ---------------------------------------------------------------------------
def charset_size(password):
    """Size of the character set this password draws from."""
    size = 0
    if any(c.islower() for c in password):
        size += 26
    if any(c.isupper() for c in password):
        size += 26
    if any(c.isdigit() for c in password):
        size += 10
    if any(c in string.punctuation for c in password):
        size += len(string.punctuation)  # 32 printable symbols
    if any(not c.isascii() for c in password):
        size += 100  # rough credit for non-ASCII characters
    return size


def human_time(seconds):
    """Turn a number of seconds into something a human can picture."""
    if seconds < 1:
        return "instant"
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f} minutes"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} hours"
    days = hours / 24
    if days < 365:
        return f"{days:.1f} days"
    years = days / 365.25
    if years < 1000:
        return f"{years:,.1f} years"
    if years < 1_000_000:
        return f"{years:,.0f} years"
    if years < 1_000_000_000:
        return f"{years / 1_000_000:,.1f} million years"
    if years < 1_000_000_000_000:
        return f"{years / 1_000_000_000:,.1f} billion years"
    return f"{years / 1_000_000_000_000:,.1f} trillion years"


def crack_time(bits, guesses_per_second=10_000_000_000):
    """How long a brute-force attack takes, on average (half the keyspace).

    10 billion guesses/second is a realistic offline rate for a single
    modern GPU rig against a fast hash. Against a slow hash (bcrypt,
    Argon2) or an online login form, the real time is far longer — so
    this is the pessimistic, honest number to plan around.
    """
    guesses = 2 ** (bits - 1) if bits > 1 else 1
    return human_time(guesses / guesses_per_second)


def verdict_for(bits, flags):
    """Plain-English verdict from estimated entropy and found patterns."""
    if "common password" in flags:
        return "VERY WEAK"
    if bits < 28:
        return "VERY WEAK"
    if bits < 40:
        return "WEAK"
    if bits < 60:
        return "FAIR"
    if bits < 80:
        return "STRONG"
    return "VERY STRONG"


def detect_patterns(password):
    """Find the patterns attackers actually try first. Returns a list of
    short human-readable findings (empty list = no patterns found)."""
    findings = []
    lowered = password.lower()

    if lowered in COMMON_PASSWORDS:
        findings.append("common password — in every attacker's dictionary")

    # Keyboard walk: 4+ characters in a row along one keyboard row.
    for row in KEYBOARD_ROWS:
        for i in range(len(row) - 3):
            if row[i:i + 4] in lowered:
                findings.append(f"keyboard walk '{row[i:i + 4]}...'")
                break

    # Straight sequences: abc, 123, xyz, 987...
    for i in range(len(password) - 2):
        a, b, c = (ord(ch) for ch in password[i:i + 3])
        if (b == a + 1 and c == b + 1) or (b == a - 1 and c == b - 1):
            findings.append(f"sequence '{password[i:i + 3]}'")
            break

    # One character repeated 3+ times in a row.
    if re.search(r"(.)\1\1", password):
        findings.append("repeated character (aaa, 111, ...)")

    # Date-like chunks: 4 digits that look like a year, or 6-8 digit runs.
    if re.search(r"(19|20)\d\d", password):
        findings.append("looks like it contains a year (19xx/20xx)")
    if re.search(r"\d{6,}", password):
        findings.append("long run of digits")

    # Whole password is one case, or letters-only / digits-only.
    if password.isalpha():
        findings.append("letters only — no digits or symbols")
    elif password.isdigit():
        findings.append("digits only")
    elif password.islower() or password.isupper():
        findings.append("single case only — no mixed case")

    return findings


def analyze(password):
    """Score one password. Returns a dict with everything check/audit need."""
    size = charset_size(password)
    raw_bits = len(password) * math.log2(size) if size > 1 else 0.0
    flags = detect_patterns(password)
    # Each detected pattern is a shortcut an attacker can use, so it costs
    # entropy. A common password is worth ~0 bits no matter how long it is.
    if "common password — in every attacker's dictionary" in flags:
        bits = 0.0
    else:
        bits = max(0.0, raw_bits - 8 * len(flags))

    # Passphrase detection: 3+ lowercase words joined by "-" or " ".
    # Charset math wildly overestimates these — it assumes every character
    # is random, so "correct-horse-battery-staple" scores like a 31-char
    # random string. The honest number is words x bits-per-word.
    sep = "-" if "-" in password else (" " if " " in password else None)
    if sep:
        parts = password.split(sep)
        digit_bonus = 0.0
        if parts and re.fullmatch(r"\d", parts[-1]):
            parts = parts[:-1]
            digit_bonus = math.log2(10)
        if len(parts) >= 3 and all(p.isalpha() and p.islower() for p in parts):
            if all(p in WORDS_SET for p in parts):
                bits = round(len(parts) * math.log2(len(WORDS)) + digit_bonus, 1)
            else:
                # Words from some other list — ~11 bits/word is the honest
                # ballpark for a 2,000-word list; say so, don't pretend
                # it's exact.
                bits = round(len(parts) * 11 + digit_bonus, 1)
                flags.append("word-based — entropy is a rough estimate")
            raw_bits = bits
            # Single-case and letter-sequence flags are noise here: a word
            # passphrase is single-case by design, and "abc" inside a word
            # is not a pattern an attacker can exploit.
            drop = ("letters only — no digits or symbols",
                    "single case only — no mixed case")
            flags = [f for f in flags if f not in drop
                     and not f.startswith("sequence '")
                     and not f.startswith("keyboard walk")]

    classes = []
    if any(c.islower() for c in password):
        classes.append("lower")
    if any(c.isupper() for c in password):
        classes.append("upper")
    if any(c.isdigit() for c in password):
        classes.append("digit")
    if any(c in string.punctuation for c in password):
        classes.append("symbol")
    return {
        "length": len(password),
        "classes": classes,
        "charset_size": size,
        "raw_bits": round(raw_bits, 1),
        "bits": round(bits, 1),
        "flags": flags,
        "verdict": verdict_for(bits, flags),
        "crack_time": crack_time(bits),
    }


def mask(password):
    """Show just enough to identify a password, never the password itself."""
    if len(password) <= 4:
        return "*" * len(password)
    return password[:1] + "*" * (len(password) - 2) + password[-1:]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def build_charset(no_lower=False, no_upper=False, no_digits=False,
                  no_symbols=False, readable=False):
    """Assemble the character pool for a random password."""
    pool = ""
    if not no_lower:
        pool += string.ascii_lowercase
    if not no_upper:
        pool += string.ascii_uppercase
    if not no_digits:
        pool += string.digits
    if not no_symbols:
        pool += string.punctuation
    if readable:
        pool = "".join(c for c in pool if c not in AMBIGUOUS)
    if not pool:
        raise ValueError("every character class was excluded — nothing left to generate from")
    return pool


def generate_password(length, pool):
    """One cryptographically random password. `secrets` (not `random`):
    random is seeded and predictable; secrets draws from the OS, and
    that is the whole point of a password generator."""
    return "".join(secret_choice(pool) for _ in range(length))


def generate_passphrase(words, count=6, separator="-", capitalize=False,
                        append_digit=False):
    """Diceware-style passphrase: `count` random words from the list.
    Words are picked with `secrets`, so each word is a full, independent
    random choice — the entropy is count * log2(len(wordlist))."""
    picked = [secret_choice(words) for _ in range(count)]
    if capitalize:
        picked = [w.capitalize() for w in picked]
    phrase = separator.join(picked)
    if append_digit:
        phrase += secret_choice(string.digits)
    return phrase


def passphrase_bits(wordlist_size, count):
    return round(count * math.log2(wordlist_size), 1)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_wordlist(path):
    """Load a custom wordlist (one word per line, like the EFF lists).
    Falls back to the built-in list if the file can't be read."""
    try:
        words = [w.strip() for w in Path(path).read_text(
            encoding="utf-8").splitlines()]
        words = [w for w in words if w and not w.startswith("#")]
    except OSError as exc:
        print(f"! could not read wordlist {path}: {exc}", file=sys.stderr)
        print("  using the built-in list instead", file=sys.stderr)
        return WORDS
    if len(words) < 100:
        print(f"! wordlist {path} has only {len(words)} words — too small, "
              "using the built-in list", file=sys.stderr)
        return WORDS
    return words


def cmd_generate(args):
    if args.wordlist:
        words = load_wordlist(args.wordlist)
    else:
        words = WORDS

    results = []
    if args.passphrase:
        for _ in range(args.count):
            phrase = generate_passphrase(words, count=args.words,
                                         separator=args.separator,
                                         capitalize=args.capitalize,
                                         append_digit=args.append_digit)
            bits = passphrase_bits(len(words), args.words)
            if args.append_digit:
                bits = round(bits + math.log2(10), 1)
            results.append({
                "password": phrase,
                "type": "passphrase",
                "bits": bits,
                "crack_time": crack_time(bits),
            })
    else:
        pool = build_charset(args.no_lower, args.no_upper, args.no_digits,
                             args.no_symbols, args.readable)
        for _ in range(args.count):
            pw = generate_password(args.length, pool)
            bits = analyze(pw)["bits"]
            results.append({
                "password": pw,
                "type": "password",
                "bits": bits,
                "crack_time": crack_time(bits),
            })

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for r in results:
        print(r["password"])
        print(f"  {r['type']}: ~{r['bits']} bits of entropy — "
              f"offline brute-force ≈ {r['crack_time']}")
    if args.passphrase:
        print(f"\n  ({args.words} words from a {len(words):,}-word list — "
              f"memorize it, don't write it on a sticky note)")
    return 0


def read_password_for_check(args):
    """Get the password to check without leaving it in shell history:
    getpass prompt first, piped stdin second, --password only if forced."""
    if args.password is not None:
        print("! --password puts the password in your shell history; "
              "prefer the hidden prompt next time", file=sys.stderr)
        return args.password
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    return getpass.getpass("Password to check (hidden as you type): ")


def print_analysis(password, result):
    print(f"\nPassword: {mask(password)}  (length {result['length']})")
    print(f"Classes:  {', '.join(result['classes']) or 'none'}"
          f"  (charset size {result['charset_size']})")
    print(f"Entropy:  ~{result['bits']} bits"
          f"  (raw {result['raw_bits']}, minus pattern penalties)")
    print(f"Crack time (offline, 10B guesses/sec): {result['crack_time']}")
    print(f"Verdict:  {result['verdict']}")
    if result["flags"]:
        print("Flags:")
        for flag in result["flags"]:
            print(f"  - {flag}")
    else:
        print("Flags:    none — no common patterns found")


def cmd_check(args):
    password = read_password_for_check(args)
    if not password:
        print("no password given", file=sys.stderr)
        return 2
    result = analyze(password)
    if args.json:
        result["masked"] = mask(password)
        print(json.dumps(result, indent=2))
        return 0
    print_analysis(password, result)
    return 0


def cmd_audit(args):
    path = Path(args.file)
    if not path.is_file():
        print(f"no such file: {path}", file=sys.stderr)
        return 2

    # The banner goes to stderr in JSON mode so stdout stays parseable.
    banner = ("AUDIT — passwords are masked in this report; delete the source\n"
              "file when you're done. This tool never stores or sends anything.\n")
    if args.json:
        print(banner, file=sys.stderr)
    else:
        print(banner)

    entries = []  # (label, password)
    for lineno, raw in enumerate(path.read_text(
            encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if args.labels:
            if ":" not in line:
                print(f"! line {lineno}: no ':' found, skipping: {line[:40]}",
                      file=sys.stderr)
                continue
            label, password = line.split(":", 1)
            entries.append((label.strip(), password.strip()))
        else:
            entries.append((f"line {lineno}", line))

    if not entries:
        print("nothing to audit — file was empty or all comments", file=sys.stderr)
        return 2

    counts = Counter()
    seen = {}          # password -> first label that used it
    reuse = Counter()  # password -> number of labels using it
    rows = []
    for label, password in entries:
        result = analyze(password)
        counts[result["verdict"]] += 1
        reuse[password] += 1
        if password in seen and seen[password] != label:
            result["flags"] = result["flags"] + [
                f"REUSED — also used by '{seen[password]}'"]
        else:
            seen.setdefault(password, label)
        rows.append((label, password, result))

    if args.json:
        out = [{
            "label": label,
            "masked": mask(pw),
            "verdict": r["verdict"],
            "bits": r["bits"],
            "crack_time": r["crack_time"],
            "flags": r["flags"],
        } for label, pw, r in rows]
        print(json.dumps({
            "entries": len(rows),
            "summary": dict(counts),
            "reused_passwords": sum(1 for n in reuse.values() if n > 1),
            "results": out,
        }, indent=2))
        return 0 if not args.strict or counts["VERY WEAK"] + counts["WEAK"] == 0 else 1

    print(f"{'LABEL':<28} {'PASSWORD':<22} {'VERDICT':<12} {'ENTROPY':>8}  FLAGS")
    print("-" * 110)
    for label, password, result in rows:
        flags = "; ".join(result["flags"]) if result["flags"] else "—"
        print(f"{label[:28]:<28} {mask(password):<22} "
              f"{result['verdict']:<12} {result['bits']:>7}b  {flags}")

    print()
    print(f"Audited {len(rows)} passwords.")
    for verdict in ("VERY WEAK", "WEAK", "FAIR", "STRONG", "VERY STRONG"):
        if counts[verdict]:
            print(f"  {verdict:<12} {counts[verdict]}")
    reused = sum(1 for n in reuse.values() if n > 1)
    if reused:
        print(f"  {reused} password(s) reused across multiple accounts — "
              "change those first: one breach breaks every account sharing it")
    weak = counts["VERY WEAK"] + counts["WEAK"]
    if weak:
        print(f"  {weak} weak password(s) — regenerate with "
              "`python passgen.py generate`")
    if args.strict and weak:
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="passgen",
        description="Generate strong passwords/passphrases and audit "
                    "password lists for weakness and reuse. Offline, "
                    "stdlib-only, nothing is ever stored or sent.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="make passwords or passphrases")
    g.add_argument("--count", type=int, default=1,
                   help="how many to make (default 1, max 50)")
    g.add_argument("--length", type=int, default=20,
                   help="password length (default 20)")
    g.add_argument("--no-lower", action="store_true")
    g.add_argument("--no-upper", action="store_true")
    g.add_argument("--no-digits", action="store_true")
    g.add_argument("--no-symbols", action="store_true")
    g.add_argument("--readable", action="store_true",
                   help="leave out look-alikes: 0 O 1 l I |")
    g.add_argument("--passphrase", action="store_true",
                   help="make a memorable word passphrase instead")
    g.add_argument("--words", type=int, default=6,
                   help="words per passphrase (default 6)")
    g.add_argument("--separator", default="-",
                   help="word separator (default '-')")
    g.add_argument("--capitalize", action="store_true",
                   help="capitalize each word")
    g.add_argument("--append-digit", action="store_true",
                   help="add one random digit at the end")
    g.add_argument("--wordlist",
                   help="custom wordlist file (one word per line)")
    g.add_argument("--json", action="store_true",
                   help="machine-readable output")
    g.set_defaults(func=cmd_generate)

    c = sub.add_parser("check", help="score a single password")
    c.add_argument("--password",
                   help="password on the command line (NOT recommended — "
                        "it lands in shell history; use the hidden prompt)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    a = sub.add_parser("audit", help="score a whole password list")
    a.add_argument("file", help="text file: one password per line, or "
                   "'label: password' lines with --labels")
    a.add_argument("--labels", action="store_true",
                   help="each line is 'label: password'")
    a.add_argument("--strict", action="store_true",
                   help="exit 1 if any password is WEAK or VERY WEAK")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_audit)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "count", 1) < 1 or getattr(args, "count", 1) > 50:
        parser.error("--count must be between 1 and 50")
    if getattr(args, "length", 20) < 4:
        parser.error("--length must be at least 4")
    if getattr(args, "words", 6) < 3:
        parser.error("--words must be at least 3")
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
