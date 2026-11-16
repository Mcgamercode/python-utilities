#!/usr/bin/env python3
"""md_to_html.py — Markdown to clean standalone HTML.

Turn any .md file into a single self-contained .html file: embedded CSS,
a clickable table of contents, syntax-labelled code blocks, GFM tables,
and task lists. No dependencies, no upload, nothing leaves your machine.

Usage:
    python md_to_html.py notes.md
    python md_to_html.py notes.md -o notes.html
    python md_to_html.py notes.md --fragment      # body HTML only (paste into a CMS/blog)
    python md_to_html.py notes.md --no-toc --title "My Notes"

Supported Markdown (CommonMark-ish + GitHub flavour):
    Headings # .. ###### and Setext === / ---, bold, italic, bold+italic,
    `inline code`, fenced code blocks, links, images, autolinks,
    unordered/ordered/nested lists, task lists, blockquotes, tables,
    horizontal rules, strikethrough.

Anything the parser doesn't recognise is rendered as a plain paragraph —
it never crashes on weird input, and raw HTML in the source is escaped
(never executed) so an untrusted .md file can't inject scripts.
"""

import argparse
import html
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSS = """/* md_to_html built-in theme — clean, readable, print-friendly */
:root { --ink:#1a1a1a; --muted:#555; --line:#ddd; --accent:#2563eb;
        --code-bg:#f4f4f5; --quote-bg:#f8fafc; }
* { box-sizing:border-box; }
body { font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
       line-height:1.6; color:var(--ink); max-width:760px; margin:2rem auto;
       padding:0 1.25rem; }
h1,h2,h3,h4,h5,h6 { line-height:1.25; margin:1.4em 0 .5em; }
h1 { font-size:1.9em; border-bottom:2px solid var(--line); padding-bottom:.3em; }
h2 { font-size:1.5em; border-bottom:1px solid var(--line); padding-bottom:.25em; }
h3 { font-size:1.25em; } h4 { font-size:1.1em; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
code { background:var(--code-bg); padding:.15em .35em; border-radius:4px;
       font-family:ui-monospace,Consolas,Menlo,monospace; font-size:.9em; }
pre { background:var(--code-bg); padding:1em; border-radius:8px; overflow-x:auto; }
pre code { background:none; padding:0; font-size:.9em; }
blockquote { border-left:4px solid var(--accent); margin:1em 0; padding:.2em 1em;
             background:var(--quote-bg); color:var(--muted); }
blockquote blockquote { margin:.5em 0; }
table { border-collapse:collapse; width:100%; margin:1em 0; }
th,td { border:1px solid var(--line); padding:.5em .75em; text-align:left; }
th { background:var(--code-bg); }
img { max-width:100%; height:auto; }
hr { border:none; border-top:1px solid var(--line); margin:2em 0; }
nav.toc { background:var(--quote-bg); border:1px solid var(--line);
          border-radius:8px; padding:.75em 1.25em; margin-bottom:2em; }
nav.toc h2 { margin:.2em 0 .4em; font-size:1em; border:none; padding:0; }
nav.toc ul { margin:.2em 0; padding-left:1.25em; }
nav.toc li { margin:.15em 0; }
.task-list { list-style:none; padding-left:.2em; }
.task-list input { margin-right:.5em; }
footer { margin-top:3em; padding-top:1em; border-top:1px solid var(--line);
         color:var(--muted); font-size:.85em; }
@media print { body { max-width:none; margin:0; } nav.toc { break-inside:avoid; } }
"""


def slugify(text: str) -> str:
    """Turn heading text into a URL-safe anchor id."""
    slug = re.sub(r"<[^>]+>", "", text)          # strip any tags
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return slug or "section"


class InlineParser:
    """Inline Markdown (bold, links, code spans...) inside one block."""

    def __init__(self):
        self._code_spans = []

    def _stash_code(self, match):
        self._code_spans.append(match.group(1))
        return "\x00%d\x00" % (len(self._code_spans) - 1)

    def parse(self, text: str) -> str:
        self._code_spans = []
        # 1. Escape raw HTML first — untrusted .md must never inject markup.
        text = html.escape(text, quote=False)
        # 2. Code spans are stashed before any other formatting can touch them.
        text = re.sub(r"`([^`]+?)`", self._stash_code, text)
        # 3. Images: ![alt](src "optional title")
        text = re.sub(
            r'!\[([^\]]*)\]\((\S+?)(?:\s+"([^"]*)")?\)',
            lambda m: '<img src="%s" alt="%s"%s>' % (
                m.group(2), m.group(1),
                (' title="%s"' % m.group(3)) if m.group(3) else ""),
            text)
        # 4. Links: [text](url) and autolinks <https://...>
        text = re.sub(r"\[([^\]]+)\]\((\S+?)(?:\s+\"[^\"]*\")?\)",
                      r'<a href="\2">\1</a>', text)
        text = re.sub(r"&lt;(https?://[^&]+)&gt;",
                      r'<a href="\1">\1</a>', text)
        # 5. Bold+italic, bold, italic, strikethrough.
        text = re.sub(r"\*\*\*([^\*]+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"___([^_]+?)___", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"\*\*([^\*]+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__([^_]+?)__", r"<strong>\1</strong>", text)
        text = re.sub(r"\*([^\*]+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"(?<![\w*])_([^_]+?)_(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(r"~~([^~]+?)~~", r"<del>\1</del>", text)
        # 6. Restore code spans, escaped.
        for i, code in enumerate(self._code_spans):
            text = text.replace("\x00%d\x00" % i, "<code>%s</code>" % code)
        return text


class MarkdownConverter:
    """Block-level Markdown parser. Collects headings for the TOC."""

    def __init__(self):
        self.inline = InlineParser()
        self.headings = []          # (level, text, anchor)
        self._anchor_counts = {}

    def _anchor(self, text: str) -> str:
        base = slugify(re.sub(r"[*_`~\[\]()!]", "", text))
        n = self._anchor_counts.get(base, 0)
        self._anchor_counts[base] = n + 1
        return base if n == 0 else "%s-%d" % (base, n)

    def convert(self, source: str) -> str:
        self.headings = []
        self._anchor_counts = {}
        lines = source.splitlines()
        blocks, _ = self._parse_blocks(lines, 0, len(lines))
        return "\n".join(blocks)

    # -- block parsing -------------------------------------------------

    def _parse_blocks(self, lines, start, end):
        out = []
        i = start
        while i < end:
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            if stripped.startswith("```"):
                html_block, i = self._fenced_code(lines, i, end)
                out.append(html_block)
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                level, text = len(m.group(1)), m.group(2).strip()
                anchor = self._anchor(text)
                self.headings.append((level, text, anchor))
                out.append('<h%d id="%s">%s</h%d>' % (
                    level, anchor, self.inline.parse(text), level))
                i += 1
                continue
            # Setext heading: text line followed by === or ---
            if i + 1 < end and re.match(r"^=+\s*$", lines[i + 1].strip()):
                anchor = self._anchor(stripped)
                self.headings.append((1, stripped, anchor))
                out.append('<h1 id="%s">%s</h1>' % (anchor, self.inline.parse(stripped)))
                i += 2
                continue
            if i + 1 < end and re.match(r"^-+\s*$", lines[i + 1].strip()) \
                    and not stripped.startswith("-"):
                anchor = self._anchor(stripped)
                self.headings.append((2, stripped, anchor))
                out.append('<h2 id="%s">%s</h2>' % (anchor, self.inline.parse(stripped)))
                i += 2
                continue
            if re.match(r"^(\*\*\*|---|___)\s*$", stripped):
                out.append("<hr>")
                i += 1
                continue
            if stripped.startswith(">"):
                html_block, i = self._blockquote(lines, i, end)
                out.append(html_block)
                continue
            if self._is_table(lines, i, end):
                html_block, i = self._table(lines, i, end)
                out.append(html_block)
                continue
            if self._is_list_item(line):
                html_block, i = self._list(lines, i, end, indent_of(line))
                out.append(html_block)
                continue
            if stripped.startswith("    ") or line.startswith("\t"):
                out.append("<pre><code>%s</code></pre>" %
                           html.escape(line[4:] if line.startswith("    ") else line[1:]))
                i += 1
                continue
            # Plain paragraph: gather until a blank line or a block starter.
            para = [stripped]
            i += 1
            while i < end and lines[i].strip() \
                    and not re.match(r"^(#{1,6}\s|```|>|(\*\*\*|---|___)\s*$)", lines[i].strip()) \
                    and not self._is_list_item(lines[i]) \
                    and not self._is_table(lines, i, end):
                # A line followed by === / --- is a Setext heading, not a paragraph.
                if i + 1 < end and re.match(r"^[=-]+\s*$", lines[i + 1].strip()):
                    break
                para.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % self.inline.parse(" ".join(para)))
        return out, i

    def _fenced_code(self, lines, i, end):
        fence = lines[i].strip()
        lang = fence[3:].strip()
        i += 1
        code = []
        while i < end and not lines[i].strip().startswith("```"):
            code.append(lines[i])
            i += 1
        i += 1  # skip closing fence
        cls = ' class="language-%s"' % html.escape(lang) if lang else ""
        return "<pre><code%s>%s</code></pre>" % (
            cls, html.escape("\n".join(code))), i

    def _blockquote(self, lines, i, end):
        inner = []
        while i < end and lines[i].strip().startswith(">"):
            inner.append(re.sub(r"^>\s?", "", lines[i].strip()))
            i += 1
        # Nested quotes are handled by re-parsing the inner lines.
        sub = MarkdownConverter()
        sub.headings = self.headings  # share nothing; headings inside quotes stay out of TOC
        body = sub.convert("\n".join(inner))
        return "<blockquote>\n%s\n</blockquote>" % body, i

    def _is_table(self, lines, i, end):
        if i + 1 >= end or "|" not in lines[i]:
            return False
        sep = lines[i + 1].strip()
        return bool(re.match(r"^\|?[\s:|-]+\|?[\s:|-]*$", sep)) and "-" in sep \
            and set(sep) <= set("|: -")

    def _split_row(self, line):
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [cell.strip() for cell in line.split("|")]

    def _table(self, lines, i, end):
        header = self._split_row(lines[i])
        aligns = []
        for cell in self._split_row(lines[i + 1]):
            if cell.startswith(":") and cell.endswith(":"):
                aligns.append(' style="text-align:center"')
            elif cell.endswith(":"):
                aligns.append(' style="text-align:right"')
            else:
                aligns.append("")
        i += 2
        rows = []
        while i < end and lines[i].strip() and "|" in lines[i]:
            rows.append(self._split_row(lines[i]))
            i += 1
        parts = ["<table>", "<thead><tr>"]
        for j, cell in enumerate(header):
            parts.append("<th%s>%s</th>" % (
                aligns[j] if j < len(aligns) else "", self.inline.parse(cell)))
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>")
            for j, cell in enumerate(row):
                parts.append("<td%s>%s</td>" % (
                    aligns[j] if j < len(aligns) else "", self.inline.parse(cell)))
            parts.append("</tr>")
        parts.append("</tbody></table>")
        return "\n".join(parts), i

    @staticmethod
    def _is_list_item(line):
        return bool(re.match(r"^\s*([-*+]|\d+[.)])\s+\S", line))

    @staticmethod
    def _list_marker(line):
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        return m

    def _list(self, lines, i, end, base_indent):
        ordered = bool(re.match(r"^\s*\d+[.)]\s", lines[i]))
        tag = "ol" if ordered else "ul"
        items = []
        while i < end:
            m = self._list_marker(lines[i])
            if not m:
                break
            indent = len(m.group(1).expandtabs(4))
            if indent < base_indent:
                break
            if indent > base_indent:
                # Nested list belongs to the previous item.
                sub, i = self._list(lines, i, end, indent)
                items[-1] = items[-1][:-5] + "\n" + sub + "</li>"
                continue
            content = m.group(3)
            # Task list: - [ ] / - [x]
            task = ""
            tm = re.match(r"^\[([ xX])\]\s+(.*)$", content)
            if tm:
                checked = " checked" if tm.group(1).lower() == "x" else ""
                task = '<input type="checkbox" disabled%s> ' % checked
                content = tm.group(2)
            items.append("<li>%s%s</li>" % (task, self.inline.parse(content)))
            i += 1
            # Continuation lines indented under this item (not a new marker).
            while i < end and lines[i].strip() and not self._is_list_item(lines[i]) \
                    and indent_of(lines[i]) > base_indent:
                items[-1] = items[-1][:-5] + " " + self.inline.parse(lines[i].strip()) + "</li>"
                i += 1
        cls = ' class="task-list"' if any("<input" in it for it in items) else ""
        return "<%s%s>\n%s\n</%s>" % (tag, cls, "\n".join(items), tag), i


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def build_toc(headings):
    if not headings:
        return ""
    parts = ['<nav class="toc">', "<h2>Contents</h2>", "<ul>"]
    prev = 1
    for level, text, anchor in headings:
        while level > prev:
            parts.append("<ul>")
            prev += 1
        while level < prev:
            parts.append("</ul>")
            prev -= 1
        parts.append('<li><a href="#%s">%s</a></li>' % (
            anchor, html.escape(text)))
    while prev > 1:
        parts.append("</ul>")
        prev -= 1
    parts.append("</ul></nav>")
    return "\n".join(parts)


def wrap_document(body: str, title: str, toc: str) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>
%s</style>
</head>
<body>
%s
%s
<footer>Converted with md_to_html.py — Markdown to standalone HTML.</footer>
</body>
</html>
""" % (html.escape(title), CSS, toc, body)


def convert_file(src: Path, dst: Path | None, title: str | None,
                  no_toc: bool, fragment: bool, css_file: Path | None):
    source = src.read_text(encoding="utf-8-sig")
    conv = MarkdownConverter()
    body = conv.convert(source)
    title = title or src.stem.replace("-", " ").replace("_", " ").title()
    if fragment:
        output = body
    else:
        global CSS
        if css_file:
            CSS = css_file.read_text(encoding="utf-8")
        toc = "" if no_toc else build_toc(conv.headings)
        output = wrap_document(body, title, toc)
    if dst is None:
        sys.stdout.write(output)
    else:
        dst.write_text(output, encoding="utf-8")
    stats = {
        "headings": len(conv.headings),
        "words": len(source.split()),
        "lines": source.count("\n") + 1,
        "code_blocks": source.count("```") // 2,
        "tables": len(re.findall(r"^\|.*\|$", source, re.M)),
    }
    return output, stats


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert a Markdown file to clean standalone HTML.")
    parser.add_argument("input", type=Path, help=".md file to convert")
    parser.add_argument("-o", "--output", type=Path,
                        help="output .html file (default: same name, .html)")
    parser.add_argument("--title", help="page <title> (default: file name)")
    parser.add_argument("--no-toc", action="store_true",
                        help="skip the table of contents")
    parser.add_argument("--fragment", action="store_true",
                        help="emit just the body HTML, no <html> wrapper "
                             "(paste into a blog/CMS)")
    parser.add_argument("--css", type=Path,
                        help="use your own CSS file instead of the built-in theme")
    parser.add_argument("--stdout", action="store_true",
                        help="print HTML to the terminal instead of writing a file")
    parser.add_argument("--version", action="version",
                        version="md_to_html.py " + __version__)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print("error: no such file: %s" % args.input, file=sys.stderr)
        return 2
    if args.input.suffix.lower() not in (".md", ".markdown", ".txt"):
        print("warning: %s doesn't look like a Markdown file — converting anyway"
              % args.input.name, file=sys.stderr)

    if args.stdout:
        dst = None
    elif args.output:
        dst = args.output
    else:
        dst = args.input.with_suffix(".html")

    try:
        _, stats = convert_file(args.input, dst, args.title,
                                args.no_toc, args.fragment, args.css)
    except UnicodeDecodeError:
        print("error: %s isn't UTF-8 text" % args.input, file=sys.stderr)
        return 2

    out = sys.stderr if dst is None else sys.stdout
    print("Converted: %s" % args.input, file=out)
    if dst:
        print("Wrote:     %s (%d bytes)" % (dst, dst.stat().st_size), file=out)
    print("Stats:     %d headings, %d words, %d code blocks, %d table rows"
          % (stats["headings"], stats["words"], stats["code_blocks"],
             stats["tables"]), file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
