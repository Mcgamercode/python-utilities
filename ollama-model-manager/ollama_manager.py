#!/usr/bin/env python3
"""ollama_manager.py — manage local Ollama models from one command.

Ollama's own CLI can do each of these things one at a time, but it only
talks to the server on the machine you're sitting at, and it makes you
do the bookkeeping yourself: which models are installed, how much disk
they eat, which ones are loaded in memory right now, and whether the
server is even up. This tool wraps Ollama's local HTTP API
(http://localhost:11434) into a single manager that works against any
host — your Windows box, your WSL Ubuntu install, or another machine on
your LAN — with one table for everything.

Commands:
    status            Is the server up, and what version is it?
    list              Installed models, sizes, last modified, total disk
    running           Models loaded in memory right now (and on CPU/GPU)
    pull <model>      Download a model, with a live progress bar
    remove <model>    Delete a model (asks first, unless --yes)
    show <model>      Full details: size, family, quantization, template
    copy <src> <dst>  Duplicate a model under a new name

Pure standard library — no pip installs. Works on Windows PowerShell
and Termux/Android with the same commands.

Usage:
    python ollama_manager.py status
    python ollama_manager.py list
    python ollama_manager.py list --sort size --json
    python ollama_manager.py running
    python ollama_manager.py pull qwen2.5-coder:7b
    python ollama_manager.py remove dolphin-phi --yes
    python ollama_manager.py show qwen3.5:4b
    python ollama_manager.py copy qwen2.5-coder:7b my-coder

    # Talk to a different server (WSL box, another PC on your LAN):
    python ollama_manager.py --host http://192.168.68.126:11434 list
    # or set the environment variable once:
    set OLLAMA_HOST=http://192.168.68.126:11434   (PowerShell: $env:OLLAMA_HOST=...)

Safety:
    * This tool only talks to the Ollama API. It never touches your
      files and never uploads anything anywhere.
    * `remove` is the only destructive command. It prints the model
      name and size and asks you to confirm, unless you pass --yes.
      If stdin is not a terminal and you didn't pass --yes, it refuses
      rather than guessing — deletes never happen silently in a script.
    * The Ollama API has no password. Anyone who can reach the host
      can pull and delete models, so only point --host at machines you
      trust, on your own network. Never expose port 11434 to the
      internet.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

DEFAULT_HOST = "http://localhost:11434"
VERSION = "1.0.0"


# ---------------------------------------------------------------- helpers

def human_size(num_bytes):
    """1_073_741_824 -> '1.0 GB'. Handles 0 and negative defensively."""
    if num_bytes is None:
        return "-"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def short_time(iso_string):
    """'2026-11-14T09:32:10.123456Z' -> '2026-11-14 09:32'."""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_string[:16]


class OllamaClient:
    """Thin wrapper over the Ollama REST API. Raises OllamaError."""

    def __init__(self, host, timeout=30):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def _request(self, method, path, payload=None, stream=False):
        url = self.host + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            raise OllamaError.from_http(exc) from exc
        except urllib.error.URLError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}\n"
                f"  Reason: {exc.reason}\n"
                f"  Is the server running? Start it with `ollama serve`\n"
                f"  (or open the Ollama app), then try again."
            ) from exc
        return resp if stream else json.loads(resp.read().decode("utf-8"))

    def version(self):
        return self._request("GET", "/api/version")

    def list_models(self):
        return self._request("GET", "/api/tags").get("models", [])

    def running_models(self):
        return self._request("GET", "/api/ps").get("models", [])

    def show_model(self, name):
        return self._request("POST", "/api/show", {"model": name})

    def pull(self, name):
        """Yield raw JSON status objects as the pull streams in."""
        resp = self._request("POST", "/api/pull", {"model": name, "stream": True},
                             stream=True)
        for line in resp:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

    def delete(self, name):
        self._request("DELETE", "/api/delete", {"model": name})

    def copy(self, source, dest):
        self._request("POST", "/api/copy", {"source": source, "destination": dest})


class OllamaError(Exception):
    @classmethod
    def from_http(cls, exc):
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", "")
        except Exception:
            detail = ""
        if exc.code == 404:
            return cls(f"Model not found on this server. {detail}".strip())
        return cls(f"Ollama server returned HTTP {exc.code}. {detail}".strip())


def print_table(headers, rows):
    """Plain-text table, column widths fitted to content."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def confirm(prompt):
    """Ask y/n on a terminal. Refuse (don't guess) when stdin isn't a tty."""
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# ---------------------------------------------------------------- commands

def cmd_status(client):
    info = client.version()
    print(f"Ollama server is UP at {client.host}")
    print(f"Version: {info.get('version', 'unknown')}")
    try:
        models = client.list_models()
        running = client.running_models()
        total = sum(m.get("size", 0) for m in models)
        print(f"Models installed: {len(models)} ({human_size(total)} on disk)")
        print(f"Models loaded in memory: {len(running)}")
    except OllamaError as exc:
        print(f"(Could not read model list: {exc})")


def cmd_list(client, args):
    models = client.list_models()
    if not models:
        print(f"No models installed on {client.host}.")
        print("Pull one with:  python ollama_manager.py pull <model>")
        return
    if args.sort == "size":
        models.sort(key=lambda m: m.get("size", 0), reverse=True)
    elif args.sort == "modified":
        models.sort(key=lambda m: m.get("modified_at", ""), reverse=True)
    else:
        models.sort(key=lambda m: m.get("name", ""))
    if args.json:
        print(json.dumps(models, indent=2))
        return
    rows = [[m.get("name", "?"),
             human_size(m.get("size")),
             short_time(m.get("modified_at"))] for m in models]
    print_table(["MODEL", "SIZE", "MODIFIED"], rows)
    total = sum(m.get("size", 0) for m in models)
    print(f"\n{len(models)} model(s), {human_size(total)} total")


def cmd_running(client, args):
    models = client.running_models()
    if not models:
        print("No models loaded in memory right now.")
        print("Loaded models appear here while a chat or API call is using them.")
        return
    if args.json:
        print(json.dumps(models, indent=2))
        return
    rows = [[m.get("name", "?"),
             human_size(m.get("size")),
             str(m.get("size_vram", 0) and human_size(m.get("size_vram")) or "-"),
             (m.get("details", {}) or {}).get("family", "-"),
             short_time(m.get("expires_at"))] for m in models]
    print_table(["MODEL", "SIZE", "VRAM", "FAMILY", "EXPIRES"], rows)
    print("\nExpires = when Ollama unloads it if nothing uses it. "
          "Unload early with:  ollama stop <model>")


def cmd_pull(client, args):
    name = args.model
    print(f"Pulling {name} from {client.host} ...")
    totals = {}      # digest -> total bytes
    done = {}        # digest -> completed bytes
    last_status = ""
    try:
        for event in client.pull(name):
            status = event.get("status", "")
            digest = event.get("digest", "")
            if "total" in event:
                totals[digest] = event["total"]
            if "completed" in event:
                done[digest] = event["completed"]
            if totals:
                total = sum(totals.values())
                completed = sum(done.get(d, 0) for d in totals)
                pct = 100.0 * completed / total if total else 0.0
                line = (f"\r{status}: {pct:5.1f}% "
                        f"({human_size(completed)} / {human_size(total)})")
                sys.stdout.write(line)
                sys.stdout.flush()
            elif status != last_status:
                sys.stdout.write(f"\r{status}...")
                sys.stdout.flush()
            last_status = status
    except OllamaError as exc:
        print(f"\nPull failed: {exc}")
        return 1
    print(f"\nDone — {name} is ready. Check it with:  "
          f"python ollama_manager.py list")
    return 0


def cmd_remove(client, args):
    name = args.model
    models = {m.get("name"): m for m in client.list_models()}
    if name not in models:
        print(f"Model '{name}' is not installed on {client.host}.")
        if models:
            print("Installed models:")
            for m in sorted(models):
                print(f"  {m}")
        return 1
    size = human_size(models[name].get("size"))
    if not args.yes:
        print(f"This will DELETE {name} ({size}) from {client.host}.")
        if not confirm("Delete it? [y/N] "):
            print("Cancelled — nothing was deleted.")
            return 0
    try:
        client.delete(name)
    except OllamaError as exc:
        print(f"Delete failed: {exc}")
        return 1
    print(f"Deleted {name} ({size} freed).")


def cmd_show(client, args):
    try:
        info = client.show_model(args.model)
    except OllamaError as exc:
        print(f"Show failed: {exc}")
        return 1
    details = info.get("details", {}) or {}
    print(f"Model:      {args.model}")
    print(f"Format:     {details.get('format', '-')}")
    print(f"Family:     {details.get('family', '-')}")
    print(f"Parameters: {details.get('parameter_size', '-')}")
    print(f"Quantized:  {details.get('quantization_level', '-')}")
    print(f"Modified:   {short_time(info.get('modified_at'))}")
    params = info.get("parameters") or ""
    if params:
        print(f"\nParameters:\n{params.strip()}")
    template = info.get("template") or ""
    if template:
        print(f"\nTemplate (first 500 chars):\n{template[:500]}")
    modelfile = info.get("modelfile") or ""
    if modelfile:
        print(f"\nModelfile (first 500 chars):\n{modelfile[:500]}")
    return 0


def cmd_copy(client, args):
    models = {m.get("name") for m in client.list_models()}
    if args.source not in models:
        print(f"Model '{args.source}' is not installed on {client.host}.")
        return 1
    if args.dest in models:
        print(f"A model named '{args.dest}' already exists. "
              f"Remove it first or pick another name.")
        return 1
    try:
        client.copy(args.source, args.dest)
    except OllamaError as exc:
        print(f"Copy failed: {exc}")
        return 1
    print(f"Copied {args.source} -> {args.dest}")


# ---------------------------------------------------------------- CLI

def build_parser():
    parser = argparse.ArgumentParser(
        prog="ollama_manager.py",
        description="Manage local Ollama models (list, pull, remove, show, "
                    "status) against any Ollama server.")
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST", DEFAULT_HOST),
                        help="Ollama server URL (default: %(default)s; "
                             "also reads OLLAMA_HOST)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("status", help="check the server is up + version")
    p.set_defaults(func=lambda c, a: cmd_status(c))

    p = sub.add_parser("list", help="installed models, sizes, total disk")
    p.add_argument("--sort", choices=["name", "size", "modified"],
                   default="name", help="sort order (default: name)")
    p.add_argument("--json", action="store_true",
                   help="print raw JSON instead of a table")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("running", aliases=["ps"],
                       help="models loaded in memory right now")
    p.add_argument("--json", action="store_true",
                   help="print raw JSON instead of a table")
    p.set_defaults(func=cmd_running)

    p = sub.add_parser("pull", help="download a model (with progress)")
    p.add_argument("model", help="model name, e.g. qwen2.5-coder:7b")
    p.set_defaults(func=cmd_pull)

    p = sub.add_parser("remove", aliases=["rm"],
                       help="delete a model (asks first)")
    p.add_argument("model", help="model name, e.g. dolphin-phi")
    p.add_argument("--yes", "-y", action="store_true",
                   help="skip the confirmation prompt")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("show", help="full details for one model")
    p.add_argument("model", help="model name, e.g. qwen3.5:4b")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("copy", help="duplicate a model under a new name")
    p.add_argument("source", help="existing model name")
    p.add_argument("dest", help="new model name")
    p.set_defaults(func=cmd_copy)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        # No subcommand: `list` is the thing you want most often.
        args.command = "list"
        args.sort = "name"
        args.json = False
        args.func = cmd_list
    client = OllamaClient(args.host, timeout=args.timeout)
    try:
        result = args.func(client, args)
    except OllamaError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
