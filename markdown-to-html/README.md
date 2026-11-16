# Markdown-to-HTML Converter

Turn any `.md` file into a single self-contained `.html` file — embedded
CSS, a clickable table of contents, labelled code blocks, GFM tables, and
task lists. No account, no upload, nothing leaves your machine. Handy for
turning READMEs and notes into pages you can email, print, or drop on a
static host.

This is tool #12 in the nightly series — a professional utility. A
developer, tech writer, or analyst converts Markdown to HTML constantly:
documentation, changelogs, meeting notes, blog drafts. This does it
offline, in one command, with output you can paste straight into a CMS.

## Install — nothing to install

Pure Python standard library. No `pip` anything. Python 3.8+ works.

## Run it

**Windows PowerShell:**

```powershell
cd ~\python-tools\markdown-to-html
python md_to_html.py notes.md
```

**Termux (Android):**

```bash
cd ~/python-tools/markdown-to-html
python md_to_html.py notes.md
```

That writes `notes.html` next to `notes.md`. Open it in any browser.

## Useful flags

```bash
python md_to_html.py notes.md -o report.html   # pick the output name
python md_to_html.py notes.md --no-toc         # skip the table of contents
python md_to_html.py notes.md --title "Q3 Notes"
python md_to_html.py notes.md --fragment       # body HTML only — paste into a blog/CMS
python md_to_html.py notes.md --stdout         # print HTML to the terminal (pipe it)
python md_to_html.py notes.md --css theme.css  # use your own stylesheet
```

## What it handles

- Headings `#`–`######` and Setext `===` / `---`, each with a linkable
  anchor id (duplicate headings get `-1`, `-2` suffixes)
- **Bold**, *italic*, ***both***, `inline code`, ~~strikethrough~~
- Links, images, and autolinks `<https://…>`
- Fenced code blocks with a language label (`` ```python ``)
- Unordered, ordered, and nested lists; task lists `- [ ]` / `- [x]`
- Blockquotes (including nested `>`), horizontal rules, GFM tables
  with left/center/right alignment
- A table of contents built from your headings, with anchor links

## What it does NOT do (on purpose)

- It never runs raw HTML found in the source — a `<script>` tag in an
  untrusted `.md` file is escaped and shown as text, not executed. So
  it's safe to run on Markdown you didn't write.
- It never deletes or overwrites your source file. It only writes the
  `.html` you asked for.
- No live preview, no editor — it's a converter, not a word processor.

## The libraries lesson

Three standard-library modules do all the work — no third-party
packages to install or keep updated:

- **`re` (regular expressions)** — the pattern-matching engine. Every
  Markdown rule (a heading line, a `**bold**` span, a table separator
  row) is one regex. If you can read these patterns, you can write
  parsers for logs, configs, and data files.
- **`html`** — `html.escape()` is the safety net: it turns `<`, `>`,
  and `&` into harmless text so untrusted input can't become markup.
  Any tool that turns user text into a web page needs this.
- **`pathlib` + `argparse`** — `pathlib` handles file paths the same
  way on Windows and Android (no string-slicing filenames), and
  `argparse` turns the `--flags` into a real CLI with `--help` for free.

## Paid equivalent — verified

**Typora** — $14.99 one-time (before tax), per its official store
(store.typora.io). A Markdown editor that exports to HTML; the price
was confirmed against Typora's store and multiple reviews checked
Oct–Nov 2026. You pay $0 here, and the output is a standalone file
with no app to install.

## Savings

| Tool | Replaces | Price | You pay |
|---|---|---|---|
| Markdown-to-HTML converter | Typora | $14.99 one-time | $0 |

Running series total after this tool: **~$336–351 one-time** +
**~$571.62/year** avoided (see `../SAVINGS_LOG.md`).
