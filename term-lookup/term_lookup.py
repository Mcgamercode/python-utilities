#!/usr/bin/env python3
"""term_lookup.py -- plain-English tech glossary for self-taught builders.

Look up a term, get a card written in plain English: what it means, one real
example from code/logs/terminal, and one thing to watch out for. Every card
you look at is saved to a local JSON glossary, so your collection grows as
you learn -- no account, no internet, no cost.

New in this version (v2):
  * 90 built-in terms across 9 topics, each linked to 2-3 related terms,
    so one lookup leads to the next idea (that is how the connections form).
  * Pretty boxed cards with colour (turn off with --no-color / --ascii).
  * --quiz: flashcards that drill your weakest terms first and remember
    your score, so you can watch yourself get better.
  * --learn: walk through a whole topic card by card, at your own pace.
  * --today: one new term a day, same term for everyone that day.
  * --search / --categories / --all: browse the deck instead of guessing.
  * --add: save your own terms in your own words.
  * --export md|html: turn the glossary into a study sheet you can read
    on your phone.
  * --ollama: when a term has no built-in card, ask your LOCAL Ollama
    model to write one on the spot (offline, nothing leaves your machine).
    Needs Ollama running; if it is not, you get the normal "no card yet"
    note instead of an error.

Stdlib only. Works on Windows PowerShell, Linux/WSL, and Termux.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

VERSION = "2.0.2"

DEFAULT_GLOSSARY = Path.home() / ".local" / "share" / "term_lookup" / "glossary.json"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")

CATEGORIES: dict[str, str] = {
    "python": "Python",
    "terminal": "Terminal & CLI",
    "logs": "Logs",
    "networking": "Networking",
    "git": "Git & GitHub",
    "security": "Security",
    "data": "Data",
    "dev": "Dev concepts",
    "files": "Files",
}

# ---------------------------------------------------------------------------
# The deck: term -> plain meaning, real example, watch-out, topic, related.
# Related terms are the "neural connections": after reading a card, follow
# one of them and the next idea clicks into place.
# ---------------------------------------------------------------------------
TERMS: dict[str, dict] = {
    # ---- Python ----
    "variable": {
        "plain": "A named box that holds one value so you can use it later by name instead of retyping it.",
        "example": "count = 0, then count = count + 1 each time a log line matches -- the name 'count' remembers the number for you.",
        "watch_out": "A variable only lives where it was created; one made inside a function does not exist outside it.",
        "category": "python",
        "related": ["string", "boolean", "function"],
    },
    "function": {
        "plain": "A named block of code that does one job. You call it by name and it runs, so you write the job once and reuse it everywhere.",
        "example": "def load_glossary(path): ... -- afterwards you just write load_glossary(my_file) instead of repeating the whole block.",
        "watch_out": "A function that does five jobs is five functions hiding in a trench coat. One job per function keeps bugs small.",
        "category": "python",
        "related": ["argument", "parameter", "return value"],
    },
    "argument": {
        "plain": "The actual value you hand to a function when you call it.",
        "example": "In load_glossary(my_file), my_file is the argument -- the real file you want loaded right now.",
        "watch_out": "Arguments go in the order the function expects. Swapping two of them is a classic silent bug.",
        "category": "python",
        "related": ["parameter", "function"],
    },
    "parameter": {
        "plain": "The placeholder name a function declares for a value it will receive later. The argument is the real value; the parameter is the label for it.",
        "example": "In def load_glossary(path):, 'path' is the parameter. When you call it, your argument fills that slot.",
        "watch_out": "Mixing up 'parameter' (the label in the definition) and 'argument' (the value in the call) is normal -- even experienced devs swap the words.",
        "category": "python",
        "related": ["argument", "function"],
    },
    "return value": {
        "plain": "The answer a function hands back to whoever called it.",
        "example": "load_glossary() returns a dictionary of your saved terms, so you can write glossary = load_glossary(path) and use it.",
        "watch_out": "If a function forgets to return anything, Python quietly returns None -- and None breaks the next line that tries to use it.",
        "category": "python",
        "related": ["function", "variable"],
    },
    "loop": {
        "plain": "Code that repeats a job once for every item in a list, or until a condition changes.",
        "example": "for line in open('access.log'): checks every single line in the file, one at a time, without you writing it 10,000 times.",
        "watch_out": "A loop whose condition never becomes false runs forever. Always know what makes it stop.",
        "category": "python",
        "related": ["list", "variable"],
    },
    "list": {
        "plain": "An ordered collection of values, kept in square brackets, where each item has a numbered position starting at 0.",
        "example": "errors = ['timeout', 'denied', 'not found'] -- errors[0] is 'timeout', errors[2] is 'not found'.",
        "watch_out": "Positions start at 0, not 1. Asking for item 3 in a 3-item list is an error, because the last one is item 2.",
        "category": "python",
        "related": ["dictionary", "loop", "string"],
    },
    "dictionary": {
        "plain": "A collection of labeled drawers: each value is stored under a name (a key) instead of a number, so you look things up by name.",
        "example": "glossary['regex'] pulls the whole card for 'regex' straight out, no counting positions like a list.",
        "watch_out": "Asking for a key that was never stored raises a KeyError. Use .get('key') when the key might be missing.",
        "category": "python",
        "related": ["list", "JSON", "string"],
    },
    "string": {
        "plain": "Text. A sequence of characters wrapped in quotes, treated as data instead of code.",
        "example": "'timeout after 5s' is a string -- your code can search it, slice it, and compare it, but it will not run it as a command.",
        "watch_out": "Quotes matter: 'it's' breaks a single-quoted string. Use double quotes or escape it: 'it\\'s'.",
        "category": "python",
        "related": ["variable", "regex", "parse"],
    },
    "boolean": {
        "plain": "A value that is only ever True or False. The yes/no answer your code makes decisions with.",
        "example": "found = False, then found = True the moment a matching log line appears -- later code just checks 'if found:'.",
        "watch_out": "In Python, an empty list, empty string, 0, and None all count as False in an if-check, which surprises people.",
        "category": "python",
        "related": ["variable", "loop", "exception"],
    },
    "class": {
        "plain": "A blueprint for making objects. It describes what data an object holds and what it can do.",
        "example": "class Card: with a term, a plain meaning, and a show() method -- every card you make from it has the same shape.",
        "watch_out": "Do not reach for a class when a plain function and a dictionary would do. Simple first, fancy later.",
        "category": "python",
        "related": ["object", "method"],
    },
    "object": {
        "plain": "One real thing built from a class blueprint, holding its own data and able to run the class's methods.",
        "example": "card = Card('regex', ...) makes one object. card.term is 'regex'; another object made from the same class holds different data.",
        "watch_out": "Two objects from the same class are not the same object. Changing one does not change the other.",
        "category": "python",
        "related": ["class", "method"],
    },
    "method": {
        "plain": "A function that belongs to a class and works on that class's objects.",
        "example": "card.show() is a method: it knows which card it belongs to and prints that card, not some other one.",
        "watch_out": "A method's first parameter is always self -- the object itself. Forgetting it is the most common first error with classes.",
        "category": "python",
        "related": ["class", "object", "function"],
    },
    "module": {
        "plain": "One .py file of reusable code. You import it and use what is inside instead of copying it.",
        "example": "import json gives you json.loads() and json.dumps() -- a whole module written by someone else, ready to use.",
        "watch_out": "Two modules with the same file name in different folders can shadow each other. Names matter.",
        "category": "python",
        "related": ["import", "library", "pip"],
    },
    "import": {
        "plain": "The line that loads a module (or a piece of one) so your code can use it.",
        "example": "import re loads the regex module; from pathlib import Path loads just the Path class out of pathlib.",
        "watch_out": "Imports run at the top of the file. An import that fails stops your whole program before it starts.",
        "category": "python",
        "related": ["module", "library"],
    },
    "exception": {
        "plain": "An error that interrupts your program at the exact line where something went wrong, instead of letting it carry on with bad data.",
        "example": "Opening a file that does not exist raises FileNotFoundError -- Python stops and tells you the file, the line, and the reason.",
        "watch_out": "Catching every exception with a bare 'except:' hides real bugs. Catch the specific error you expect.",
        "category": "python",
        "related": ["stack trace", "debug", "log level"],
    },
    "virtual environment": {
        "plain": "A private folder of Python packages for one project, so its tools and versions never fight with another project's.",
        "example": "python -m venv .venv, then activate it -- pip install inside it touches only this project, never your whole system.",
        "watch_out": "Forgetting to activate it means you install packages into the wrong Python and wonder why the import fails.",
        "category": "python",
        "related": ["pip", "module", "PATH"],
    },
    "pip": {
        "plain": "Python's package installer. It downloads libraries from the internet and puts them where your Python can import them.",
        "example": "pip install pillow adds the Pillow image library so the duplicate-photo finder can read pictures.",
        "watch_out": "Always know which Python you are installing into -- pip and python3 can point at different installs on the same machine.",
        "category": "python",
        "related": ["virtual environment", "module", "dependency"],
    },
    # ---- Terminal & CLI ----
    "cli": {
        "plain": "A text-based command-line interface where you run tools with words and flags instead of clicking buttons.",
        "example": "Running 'python log_analyzer.py access.log --errors-only' in your terminal.",
        "watch_out": "Watch spelling and spaces around flags and file paths.",
        "category": "terminal",
        "related": ["flag", "shell", "stdin"],
    },
    "flag": {
        "plain": "An optional switch you pass on a command line to change how a tool behaves.",
        "example": "Adding '--top 20' to show 20 items instead of the default 10.",
        "watch_out": "Check '--help' if a flag expects a value after it, like '--format apache'.",
        "category": "terminal",
        "related": ["cli", "argument", "exit code"],
    },
    "stdin": {
        "plain": "The input stream: where a program reads what you type, or what another program pipes into it.",
        "example": "Typing a term at the '>' prompt in interactive mode -- your keystrokes arrive through stdin.",
        "watch_out": "A program waiting on stdin looks frozen. It is usually just waiting for you to type something (or press Ctrl+C).",
        "category": "terminal",
        "related": ["stdout", "stderr", "pipe"],
    },
    "stdout": {
        "plain": "The normal output stream where a program prints its main results.",
        "example": "Printing a summary report to your terminal or saving it with > report.txt.",
        "watch_out": "Don't mix error messages into normal output if another tool or script is reading the result.",
        "category": "terminal",
        "related": ["stderr", "stdin", "pipe"],
    },
    "stderr": {
        "plain": "The separate error stream where a program prints warnings and errors, kept apart from its normal results.",
        "example": "A missing file prints 'No such file' to stderr while the real results still go to stdout -- so '> out.txt' saves only the good stuff.",
        "watch_out": "Redirecting only stdout (>) leaves errors on screen. Use 2> errors.txt to capture them too.",
        "category": "terminal",
        "related": ["stdout", "stdin", "log level"],
    },
    "pipe": {
        "plain": "The | symbol: it sends one program's output straight into the next program's input, like a conveyor belt.",
        "example": "cat access.log | grep ERROR | wc -l -- find the errors, then count them, without saving anything in between.",
        "watch_out": "A pipe only carries text (stdout). Errors go around it, not through it, unless you redirect them first.",
        "category": "terminal",
        "related": ["stdout", "stdin", "grep"],
    },
    "shell": {
        "plain": "The program that reads what you type in a terminal and runs it -- bash, zsh, or PowerShell.",
        "example": "Your Termux prompt runs zsh; your laptop's PowerShell is a different shell with different commands for the same jobs.",
        "watch_out": "Commands you learn for one shell do not always work in another. 'ls' is bash; PowerShell also accepts it, but 'dir' is its native one.",
        "category": "terminal",
        "related": ["cli", "environment variable", "PATH"],
    },
    "environment variable": {
        "plain": "A named setting stored outside your code that programs read at run time -- a way to pass config without editing files.",
        "example": "OLLAMA_MODEL=qwen3.5:4b python term_lookup.py --ollama -- the model name travels in the environment, not in the code.",
        "watch_out": "Variables set in one terminal window do not exist in another. Set them where they are needed, or in your shell's startup file.",
        "category": "terminal",
        "related": ["PATH", "shell", "working directory"],
    },
    "PATH": {
        "plain": "A list of folders your shell searches, in order, when you type a command name without a full path.",
        "example": "Typing 'python3' works because its folder is on your PATH; typing a script by name only works if its folder is there too.",
        "watch_out": "Two programs with the same name in different PATH folders: the first folder wins, silently. 'which python3' shows which one.",
        "category": "terminal",
        "related": ["environment variable", "shell", "pip"],
    },
    "working directory": {
        "plain": "The folder your terminal is standing in right now. Relative paths (like data.csv) are measured from here.",
        "example": "cd ~/workspace/python-tools, then python term_lookup.py regex -- the script and its files are found relative to where you are.",
        "watch_out": "A script that works from one folder and fails from another is almost always a relative-path problem. 'pwd' shows where you are.",
        "category": "terminal",
        "related": ["absolute path", "shell", "file path"],
    },
    "absolute path": {
        "plain": "The full address of a file starting from the root of the drive, so it works no matter where your terminal is standing.",
        "example": "/home/mike/workspace/python-tools/term_lookup.py -- that address is true from any folder on the machine.",
        "watch_out": "Absolute paths break when the file moves to another machine or user, because the beginning of the address changes.",
        "category": "terminal",
        "related": ["working directory", "file path", "PATH"],
    },
    "exit code": {
        "plain": "The small number a program returns when it finishes: 0 means success, anything else means something went wrong.",
        "example": "After a script runs, 'echo $?' (bash) or '$LASTEXITCODE' (PowerShell) shows the code it left behind.",
        "watch_out": "A program can print a cheerful message and still exit with an error code. The code is the truth; the message is marketing.",
        "category": "terminal",
        "related": ["stderr", "exception", "shell"],
    },

    # ---- Logs ----
    "regex": {
        "plain": "A pattern rule that searches, matches, or cleans up text based on shape instead of exact spelling.",
        "example": "Collapsing 'timeout after 5s' and 'timeout after 8s' into one pattern so log errors group cleanly.",
        "watch_out": "One wrong symbol can match too much or nothing at all—test on sample lines first.",
        "category": "logs",
        "related": ["parse", "grep", "string"],
    },
    "parse": {
        "plain": "Breaking a raw line or block of text into labeled pieces your code can actually use.",
        "example": "Splitting a log line into timestamp, severity level, and message instead of treating it as one blob.",
        "watch_out": "Badly formatted lines can break strict rules, so track or handle lines that don't fit.",
        "category": "logs",
        "related": ["regex", "JSON", "timestamp"],
    },
    "timestamp": {
        "plain": "A date and time mark showing when an event or log line happened.",
        "example": "Checking '2026-11-08 09:12:03' to see what time errors spiked.",
        "watch_out": "Time zones can be missing or shifted between servers, making times look out of order.",
        "category": "logs",
        "related": ["log level", "parse", "tail"],
    },
    "log level": {
        "plain": "A severity label on each log line -- DEBUG, INFO, WARNING, ERROR, CRITICAL -- so you can filter noise from real problems.",
        "example": "Running log_analyzer.py --errors-only shows just the ERROR and CRITICAL lines and hides the chatter.",
        "watch_out": "A program that logs everything as ERROR trains you to ignore ERROR. Levels only work if they mean something.",
        "category": "logs",
        "related": ["stderr", "stack trace", "tail"],
    },
    "grep": {
        "plain": "A search tool that prints only the lines matching a pattern, from a file or from piped input.",
        "example": "grep ERROR access.log -- every line with ERROR in it, nothing else. Add -i to ignore case, -n to show line numbers.",
        "watch_out": "grep reads text. It cannot search inside images, zipped files, or binary files without help (use zgrep for .gz).",
        "category": "logs",
        "related": ["regex", "pipe", "tail"],
    },
    "stack trace": {
        "plain": "The list of function calls that were running when an error happened, newest first -- a map of how your program got to the crash.",
        "example": "A traceback ending in FileNotFoundError shows main() called load_glossary() called open() -- the crash is at the bottom, the cause is usually one frame up.",
        "watch_out": "Read it bottom-up: the last line names the error, the lines above it show the path. The top line is rarely the problem.",
        "category": "logs",
        "related": ["exception", "debug", "log level"],
    },
    "tail": {
        "plain": "A tool that shows the last lines of a file -- and with -f, keeps watching and prints new lines as they arrive.",
        "example": "tail -f server.log -- sit and watch errors appear live while you poke at the server.",
        "watch_out": "tail -f on a file that gets rotated (renamed) keeps watching the old file. Use tail -F to follow the name instead.",
        "category": "logs",
        "related": ["grep", "log level", "stdout"],
    },
    # ---- Networking ----
    "IP address": {
        "plain": "A device's address on a network -- four numbers like 192.168.68.126 that say exactly which machine to talk to.",
        "example": "Your Lubuntu box at 192.168.68.126: you SSH to that address and you reach that box, not the router, not your phone.",
        "watch_out": "Home addresses (192.168.x.x) change when the router reassigns them. Never carve one into stone; check it with hostname -I.",
        "category": "networking",
        "related": ["port", "DNS", "localhost"],
    },
    "port": {
        "plain": "A numbered door on a machine. The IP address finds the machine; the port picks which program on it answers.",
        "example": "ssh miker@192.168.68.126 -p 2222 -- the address finds the laptop, port 2222 is the door where WSL's SSH is listening.",
        "watch_out": "Two programs cannot listen on the same port at once. 'Address already in use' means something else is already behind that door.",
        "category": "networking",
        "related": ["IP address", "localhost", "server"],
    },
    "localhost": {
        "plain": "A name that always means 'this machine I am on right now' -- the address 127.0.0.1.",
        "example": "Ollama listens on localhost:11434, so only programs on the same machine can reach it. Your phone cannot, unless you forward it.",
        "watch_out": "Localhost on your phone is your phone, not your laptop. Same word, different machine, every time.",
        "category": "networking",
        "related": ["IP address", "port", "server"],
    },
    "DNS": {
        "plain": "The phone book of the internet: it turns a human name like github.com into the IP address machines actually use.",
        "example": "You type github.com, DNS answers 140.82.114.4, and your browser connects to that number.",
        "watch_out": "When a site 'doesn't load' but your internet works, stale or wrong DNS is a common culprit. Try another network to test it.",
        "category": "networking",
        "related": ["IP address", "HTTP", "server"],
    },
    "HTTP": {
        "plain": "The language browsers and servers use to ask for and deliver web pages: a request goes out, a response comes back.",
        "example": "python3 -m http.server 8000 serves a page; your phone's browser sends an HTTP request and gets the page as the response.",
        "watch_out": "Plain HTTP sends everything readable by anyone in the middle. HTTPS is the same language with encryption wrapped around it.",
        "category": "networking",
        "related": ["request", "response", "status code"],
    },
    "status code": {
        "plain": "The three-digit number in an HTTP response that says what happened: 200 worked, 404 not found, 500 the server broke.",
        "example": "Your server lab: asking for a missing page returns 404, and the access log records that 404 for you to find.",
        "watch_out": "A 200 does not mean the content is right -- a login page can return 200 while saying 'wrong password' in the body.",
        "category": "networking",
        "related": ["HTTP", "response", "request"],
    },
    "request": {
        "plain": "A message asking a server for something: a page, a file, data -- with a method (GET, POST) and a target address.",
        "example": "curl http://192.168.68.126:8000/ sends a GET request for the front page of your Lubuntu box's little web server.",
        "watch_out": "GET requests should only fetch things. Anything that changes data (login, delete) belongs in a POST, not a GET.",
        "category": "networking",
        "related": ["response", "HTTP", "API"],
    },
    "response": {
        "plain": "The server's answer to a request: a status code, some headers, and the body (the page, file, or data you asked for).",
        "example": "The GitHub API answers your request with status 200 and a JSON body listing your repos.",
        "watch_out": "Always check the status code before trusting the body. A 404 page is still a response, just not the one you wanted.",
        "category": "networking",
        "related": ["request", "status code", "HTTP"],
    },
    "header": {
        "plain": "The labeled details attached to an HTTP request or response -- not the content itself, but facts about it.",
        "example": "curl -I shows headers like Content-Type: text/html and Server: nginx/1.18 -- your recon tool reads these to fingerprint a server.",
        "watch_out": "Headers are easy to fake. A server can claim to be anything; never trust a Server header as proof.",
        "category": "networking",
        "related": ["request", "response", "HTTP"],
    },
    "TCP": {
        "plain": "The reliable delivery service of the internet: it breaks data into numbered pieces, checks they all arrive, and re-sends the missing ones.",
        "example": "SSH, HTTP, and file downloads all ride on TCP -- that is why a half-downloaded file is an error, not a mystery.",
        "watch_out": "TCP guarantees delivery, not speed. On a bad connection it will patiently re-send forever instead of giving up fast.",
        "category": "networking",
        "related": ["port", "SSH", "server"],
    },
    "SSH": {
        "plain": "A secure, encrypted way to log into another machine over the network and run commands on it as if you were sitting there.",
        "example": "ssh miker@192.168.68.126 from your phone drops you into a shell on the Lubuntu box, where you can start a web server.",
        "watch_out": "Password login over SSH is the weak door. Key login (a private key file, never shared) is the strong one.",
        "category": "networking",
        "related": ["TCP", "server", "port"],
    },
    "server": {
        "plain": "A program (or a machine running one) that waits for requests and answers them -- a web server answers with pages, an SSH server with a shell.",
        "example": "python3 -m http.server 8000 turns your Lubuntu box into a web server for one folder, on port 8000.",
        "watch_out": "A server that listens on 0.0.0.0 answers the whole network, not just your machine. Know which doors you opened.",
        "category": "networking",
        "related": ["localhost", "port", "SSH"],
    },
    "client": {
        "plain": "The side that asks. Your browser, your phone, curl -- anything that sends a request to a server and waits for the answer.",
        "example": "In your server lab, your phone is the client and the Lubuntu box is the server. The phone asks, the box answers.",
        "watch_out": "A client that never gets an answer just waits. Timeouts exist so a dead server cannot freeze your program forever.",
        "category": "networking",
        "related": ["server", "request", "API"],
    },
    # ---- Git & GitHub ----
    "repository": {
        "plain": "A project folder with a memory: every change ever made, who made it, and the ability to go back to any earlier version.",
        "example": "Mcgamercode/python-utilities is a repository -- all 14 tools, their history, and the README live there together.",
        "watch_out": "A repo remembers everything you commit, including secrets. Never commit passwords or API keys -- removing the file later does not erase the history.",
        "category": "git",
        "related": ["commit", "branch", "remote"],
    },
    "commit": {
        "plain": "One saved snapshot of your project, with a message saying what changed and why.",
        "example": "'Add tool #14: duplicate-photo finder' -- one commit, one clear job, easy to find later.",
        "watch_out": "A commit message that says 'stuff' helps no one, including future you. One line, one job, plain words.",
        "category": "git",
        "related": ["branch", "repository", "push"],
    },
    "branch": {
        "plain": "A separate line of work inside a repository, so you can experiment without touching the main version until it is ready.",
        "example": "fix/v1.1-code-review-ollama held the cybercrta-toolkit fixes apart from main until they were reviewed and merged.",
        "watch_out": "A branch nobody merges becomes stale and painful to bring back. Merge it or delete it -- do not let it rot.",
        "category": "git",
        "related": ["commit", "merge", "pull request"],
    },
    "merge": {
        "plain": "Combining one branch's work back into another, usually into main, after it has been checked.",
        "example": "PR #1 on cybercrta-toolkit was merged on Nov 1 -- the fixes from the branch became part of main.",
        "watch_out": "Two people editing the same lines creates a merge conflict. Git stops and asks a human to pick the right version.",
        "category": "git",
        "related": ["branch", "pull request", "commit"],
    },
    "pull request": {
        "plain": "A proposal: 'here is my branch, here is what it changes, please review it before it joins main.'",
        "example": "The v1.1.0 fixes arrived as PR #1 with a description of all five fixes, then got merged after review.",
        "watch_out": "A pull request is a review, not a rubber stamp. The reviewer is supposed to actually read the changes.",
        "category": "git",
        "related": ["branch", "merge", "remote"],
    },
    "clone": {
        "plain": "Downloading a full copy of a repository -- its files and its entire history -- onto your machine.",
        "example": "git clone https://github.com/Mcgamercode/python-utilities gives you every tool and every commit on your laptop.",
        "watch_out": "Cloning is a copy, not a live link. Changes on GitHub do not appear in your copy until you pull.",
        "category": "git",
        "related": ["repository", "remote", "push"],
    },
    "push": {
        "plain": "Uploading your local commits to the remote repository (usually GitHub) so they are stored and visible there.",
        "example": "git push origin main -- your new commits leave your laptop and land on github.com/Mcgamercode/python-utilities.",
        "watch_out": "Pushing rewrites nothing on other people's machines, but pushing a secret publishes it to the world. Check before you push.",
        "category": "git",
        "related": ["commit", "remote", "clone"],
    },
    "remote": {
        "plain": "The copy of your repository that lives somewhere else -- usually GitHub -- that you push to and pull from.",
        "example": "'origin' is the usual name for the GitHub remote of python-utilities. git remote -v shows where it points.",
        "watch_out": "Pushing to the wrong remote sends your work to the wrong repo. 'git remote -v' takes two seconds and prevents it.",
        "category": "git",
        "related": ["repository", "clone", "push"],
    },

    # ---- Security ----
    "vulnerability": {
        "plain": "A weak spot in software that an attacker can use to do something the maker never intended.",
        "example": "A login form that builds its database query from raw user input has a SQL-injection vulnerability -- the weak spot is the unguarded input.",
        "watch_out": "A vulnerability is not an attack yet. Finding one is step one; whether anyone uses it is step two.",
        "category": "security",
        "related": ["exploit", "payload", "brute force"],
    },
    "exploit": {
        "plain": "A concrete trick or piece of code that uses a vulnerability to get an effect -- reading data, running commands, getting in.",
        "example": "Typing ' OR '1'='1 into a vulnerable login to make the database query always true -- that input is the exploit.",
        "watch_out": "Testing an exploit against a system you do not own is illegal in most places, even if you mean well. Lab machines only.",
        "category": "security",
        "related": ["vulnerability", "payload", "SQL injection"],
    },
    "payload": {
        "plain": "The part of an attack that does the actual job once the door is open -- the command, the code, the thing that runs.",
        "example": "A phishing email's attachment is the delivery; the payload is the code inside it that runs when the file is opened.",
        "watch_out": "In your red-team harness, the 'payload' is just a test string with a canary secret -- a marker that proves it got through, not real malware.",
        "category": "security",
        "related": ["exploit", "vulnerability", "brute force"],
    },
    "hash": {
        "plain": "A fingerprint of some data: a short fixed-length string computed from it, so you can check the data later without keeping the original.",
        "example": "Passwords are stored as hashes, not as the password itself. Logging in hashes what you typed and compares fingerprints.",
        "watch_out": "A hash is not encryption -- you cannot turn a hash back into the original. And weak hashes (MD5, SHA1) can be cracked by guessing.",
        "category": "security",
        "related": ["encryption", "checksum", "token"],
    },
    "encryption": {
        "plain": "Scrambling data with a key so only someone with the key can read it. The scrambled form looks like random noise.",
        "example": "HTTPS encrypts your web traffic; SSH encrypts your terminal session. Anyone listening in the middle sees noise, not passwords.",
        "watch_out": "Encryption protects data in transit and at rest, but not data in use. A running program still decrypts it to work with it.",
        "category": "security",
        "related": ["hash", "token", "authentication"],
    },
    "authentication": {
        "plain": "Proving who you are -- the check at the door that asks 'are you really Mike?'",
        "example": "Typing your password, or your phone approving a login, is authentication. It answers the identity question.",
        "watch_out": "Authentication is not authorization. Proving who you are does not prove you are allowed to do the thing.",
        "category": "security",
        "related": ["authorization", "token", "hash"],
    },
    "authorization": {
        "plain": "Deciding what an already-identified user is allowed to do -- the permissions, not the identity.",
        "example": "You are authenticated as Mike, but only an admin can delete a repo. That rule is authorization.",
        "watch_out": "The most common real-world bug is checking authentication and forgetting authorization: logged in, but allowed everywhere.",
        "category": "security",
        "related": ["authentication", "token", "server"],
    },
    "token": {
        "plain": "A short secret string that proves you already logged in, so you do not have to send your password with every request.",
        "example": "Your GitHub PAT is a token: scripts send it instead of your password, and you can revoke it any time without changing your password.",
        "watch_out": "A token is as powerful as a password while it lives. Treat it like one: never paste it into chat, code, or screenshots.",
        "category": "security",
        "related": ["authentication", "authorization", "API"],
    },
    "SQL injection": {
        "plain": "An attack where user input is smuggled into a database query and changes what the query does.",
        "example": "A search box that runs SELECT * FROM users WHERE name = '<your input>' -- typing ' OR '1'='1 turns it into 'give me everyone'.",
        "watch_out": "The fix is never 'block bad words'. It is parameterized queries: the input stays data and can never become code.",
        "category": "security",
        "related": ["exploit", "query", "database"],
    },
    "brute force": {
        "plain": "Trying every possible password (or key) until one works. Slow, noisy, and unstoppable against a weak password.",
        "example": "A script trying 'password', 'password1', 'qwerty'... against a login page, thousands of guesses a minute.",
        "watch_out": "The defense is not a cleverer password alone: lockouts after a few failures and two-factor auth stop brute force cold.",
        "category": "security",
        "related": ["hash", "authentication", "vulnerability"],
    },
    # ---- Data ----
    "CSV": {
        "plain": "A plain-text table: rows on lines, columns separated by commas. The simplest way to move tabular data between programs.",
        "example": "Your csv-profiler reads a .csv of sales or logs and reports the shape of every column -- counts, blanks, top values.",
        "watch_out": "A comma inside a value (like 'Beloit, WI') breaks naive splitting. Real CSV wraps such values in quotes; your parser must respect them.",
        "category": "data",
        "related": ["JSON", "query", "database"],
    },
    "JSON": {
        "plain": "A text format for structured data: objects in curly braces, lists in square brackets, keys and values -- the common language of APIs and config.",
        "example": "Your glossary file is JSON: {\"regex\": {\"plain\": \"...\", \"example\": \"...\"}} -- readable by humans and machines alike.",
        "watch_out": "JSON is strict: one trailing comma or a single quote instead of double quotes and the whole file fails to parse.",
        "category": "data",
        "related": ["dictionary", "YAML", "API"],
    },
    "YAML": {
        "plain": "A human-friendly config format that uses indentation instead of braces -- the same data as JSON, easier on the eyes.",
        "example": "fly.toml is close kin, and your json-yaml-tools converts between JSON and YAML so you can edit configs in whichever you prefer.",
        "watch_out": "Indentation IS the structure in YAML. One space too few and a setting silently lands under the wrong key.",
        "category": "data",
        "related": ["JSON", "CSV", "file path"],
    },
    "database": {
        "plain": "An organized store for data that lets you ask questions (queries) and get answers, instead of digging through files by hand.",
        "example": "Your marketplace inventory.db is a database: one table of items, and you ask it 'which listings are 30 days old?' instead of reading rows yourself.",
        "watch_out": "A database without backups is a single accident away from losing everything. Copy the file before big changes.",
        "category": "data",
        "related": ["query", "SQLite", "schema"],
    },
    "query": {
        "plain": "A question you ask a database, written in a small language (usually SQL), that returns exactly the rows you want.",
        "example": "SELECT name, list_price FROM items WHERE status='active' -- every live listing, name and price, nothing else.",
        "watch_out": "A query with no WHERE returns the whole table. On a big database that is slow -- and on a DELETE, it is a disaster.",
        "category": "data",
        "related": ["database", "SQLite", "SQL injection"],
    },
    "SQLite": {
        "plain": "A tiny database that lives in a single file -- no server to install, no password, just open the file and ask questions.",
        "example": "inventory.db and your sqlite-query-helper: the whole marketplace tracker is one file you can copy, back up, and open anywhere.",
        "watch_out": "SQLite is one writer at a time. Two programs writing to the same file at once will fight; one of them waits or fails.",
        "category": "data",
        "related": ["database", "query", "schema"],
    },
    "schema": {
        "plain": "The blueprint of a database: which tables exist, what columns each has, and what kind of data goes in each column.",
        "example": "The items table schema says: id, name, price, status... -- every row follows that shape, so queries always know what to expect.",
        "watch_out": "Changing a schema (adding a column) is easy; changing what old data means is hard. Plan the shape before you fill it.",
        "category": "data",
        "related": ["database", "SQLite", "query"],
    },
    # ---- Dev concepts ----
    "algorithm": {
        "plain": "A recipe: a precise set of steps that turns an input into an output, written so a machine can follow it exactly.",
        "example": "The duplicate-photo finder hashes each photo into an 8x8 grid, then groups photos whose grids are nearly identical -- that recipe is the algorithm.",
        "watch_out": "A correct algorithm can still be slow. Checking every photo against every other photo is correct -- and impossibly slow at 10,000 photos.",
        "category": "dev",
        "related": ["loop", "function", "debug"],
    },
    "library": {
        "plain": "A bundle of ready-made code for one job, written by someone else, that you import instead of writing from scratch.",
        "example": "Pillow is a library for images; the json module is a library for JSON. Your tools import them and skip hundreds of lines.",
        "watch_out": "Every library is a dependency you now own. If it breaks, gets abandoned, or changes, your code feels it.",
        "category": "dev",
        "related": ["module", "framework", "dependency"],
    },
    "framework": {
        "plain": "A library that also decides the shape of your program: it calls your code, not the other way round, and fills in the boring parts.",
        "example": "Flask is a framework for web apps: you write small functions for each page, and Flask handles requests, routing, and responses.",
        "watch_out": "A framework saves time until you need something it was not built for -- then you fight it. Pick one that fits the job.",
        "category": "dev",
        "related": ["library", "dependency", "API"],
    },
    "dependency": {
        "plain": "Something your code needs in order to run: a library, a tool, a specific version of either.",
        "example": "The duplicate-photo finder depends on Pillow; the JSON/YAML tool depends on PyYAML. Without them, those tools cannot start.",
        "watch_out": "Dependencies pile up quietly. A project with 40 of them breaks when any one changes -- keep the list short and pinned.",
        "category": "dev",
        "related": ["library", "pip", "framework"],
    },
    "debug": {
        "plain": "Finding out why code does the wrong thing, by reading what it actually did instead of what you assumed it did.",
        "example": "Your log analyzer exists for this: when a server misbehaves, you read its logs and stack traces instead of guessing.",
        "watch_out": "Guessing and changing three things at once teaches you nothing. Change one thing, test, then change the next.",
        "category": "dev",
        "related": ["stack trace", "exception", "log level"],
    },
    "refactor": {
        "plain": "Rewriting code to be cleaner and easier to change, without changing what it does.",
        "example": "Pulling a repeated 20-line block out of three places into one function called once -- same behavior, one place to fix it.",
        "watch_out": "Refactor with tests, or at least with a backup. 'Cleaner' code that quietly behaves differently is a new bug, not a cleanup.",
        "category": "dev",
        "related": ["function", "syntax", "debug"],
    },
    "syntax": {
        "plain": "The exact spelling and punctuation a language demands. Right idea, wrong syntax, and the program will not run at all.",
        "example": "Forgetting the colon at the end of 'if found:' is a syntax error -- Python stops and points at the line.",
        "watch_out": "Syntax errors are the kindest errors: the program tells you the line and stops. Logic errors are the cruel ones -- the program runs and is wrong.",
        "category": "dev",
        "related": ["debug", "function", "refactor"],
    },
    "cache": {
        "plain": "A stash of recent results kept close at hand, so the next identical request is answered instantly instead of recomputed.",
        "example": "Your browser caches images so the second visit to a page loads fast; pip caches downloads so reinstalling is quick.",
        "watch_out": "A cache can go stale: it keeps answering with yesterday's data after the real data changed. 'Clear the cache' is a real fix, not a joke.",
        "category": "dev",
        "related": ["server", "dependency", "database"],
    },
    # ---- Files ----
    "file path": {
        "plain": "The address of a file: which folders to walk through, in order, to reach it.",
        "example": "~/workspace/python-tools/term_lookup.py -- home, then workspace, then python-tools, then the file.",
        "watch_out": "Spaces and special characters in a path break commands that are not quoted. Wrap paths in quotes when they contain spaces.",
        "category": "files",
        "related": ["absolute path", "working directory", "extension"],
    },
    "extension": {
        "plain": "The suffix after the last dot in a file name (.py, .json, .log) that says what kind of file it is.",
        "example": "term_lookup.py ends in .py, so your system treats it as Python; glossary.json ends in .json, so tools read it as data.",
        "watch_out": "An extension is a label, not a guarantee. Renaming photo.txt to photo.jpg does not turn text into a picture.",
        "category": "files",
        "related": ["file path", "encoding", "JSON"],
    },
    "checksum": {
        "plain": "A short number computed from a file's contents, so you can tell later whether the file changed -- even by one byte.",
        "example": "Your Takeout verifier computes a CRC32 checksum for every file in the zip and compares it to the manifest. A mismatch means the copy is damaged.",
        "watch_out": "A checksum proves the file is unchanged, not that it is safe. A malicious file can have a perfectly valid checksum.",
        "category": "files",
        "related": ["hash", "file path", "encoding"],
    },
    "encoding": {
        "plain": "The rule that turns characters into bytes and back. UTF-8 is the standard one: it handles every language, emoji included.",
        "example": "Reading a file with encoding='utf-8' tells Python how to turn its bytes back into the text you expect.",
        "watch_out": "A file saved in the wrong encoding shows mojibake -- 'cafÃ©' instead of 'café'. The bytes are fine; the reading rule is wrong.",
        "category": "files",
        "related": ["checksum", "extension", "string"],
    },
}

# "API" is used as a related term in several cards, so it gets its own card.
TERMS["API"] = {
    "plain": "A menu a program offers to other programs: a set of addresses you can call to ask it to do things or give you data, without using its buttons.",
    "example": "The GitHub API: your upload script calls it to create a file in the repo -- same GitHub, no browser, no clicks.",
    "watch_out": "APIs change versions and rate-limit you. Read the error message in the response; it usually tells you exactly what went wrong.",
    "category": "networking",
    "related": ["request", "response", "JSON"],
}

# Two more cards for exact strings that came up in real use (Nov 19, 2026):
# ".sh" is a file extension, not a word, and "0" is the exit code for success
# (and the first position when counting list items).
TERMS[".sh"] = {
    "plain": "The file extension for a shell script -- a text file full of terminal commands that run top to bottom when you execute it.",
    "example": "pentest-ops.sh: you run it and it runs every command inside, one after another, instead of you typing each one by hand.",
    "watch_out": "A .sh file does nothing until it is executable (chmod +x) and you actually run it -- opening it just shows the text.",
    "category": "files",
    "related": ["shell", "extension", "cli"],
}

TERMS["0"] = {
    "plain": "The number zero shows up in two places that matter: as the exit code that means 'it worked', and as the first position when counting items in a list.",
    "example": "A command that finishes cleanly exits with 0; and in errors = ['timeout', 'denied'], errors[0] is 'timeout' -- counting starts at 0, not 1.",
    "watch_out": "Don't mix the two up: exit code 0 means success, but list position 0 just means 'first' -- it says nothing about success or failure.",
    "category": "terminal",
    "related": ["exit code", "list"],
}

# Case-insensitive lookup table. TERMS keys use their natural casing
# ("API", "JSON", "SQL injection"), but lookups arrive lowercased, so a
# plain TERMS.get(lowercased) missed every acronym. This maps every key
# to its lowercase form once, and build_entry consults it instead.
_TERMS_BY_LOWER_KEY = {k.lower(): v for k, v in TERMS.items()}

# ---------------------------------------------------------------------------
# Colours + card rendering
# ---------------------------------------------------------------------------
USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Paint:
    """Tiny ANSI colour helper. All methods return plain text when colour is off."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def cyan(self, text: str) -> str:
        return self._wrap("1;36", text)

    def yellow(self, text: str) -> str:
        return self._wrap("1;33", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)


def _box_chars(ascii_only: bool) -> dict[str, str]:
    if ascii_only:
        return {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"}
    return {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"}


def render_card(entry: dict, paint: Paint, ascii_only: bool = False, width: int = 74) -> str:
    """Render one glossary entry as a boxed card."""
    box = _box_chars(ascii_only)
    inner = width - 4
    lines: list[str] = []

    title = entry.get("term", "?")
    cat = CATEGORIES.get(entry.get("category", ""), entry.get("category", ""))
    title_text = f" {title} "
    if cat:
        title_text += f"· {cat}"
    bar_len = max(1, width - 2 - len(title_text))
    lines.append(box["tl"] + paint.cyan(title_text) + box["h"] * bar_len + box["tr"])

    def add_row(label: str, text: str, label_paint=None, text_paint=None) -> None:
        wrapped = textwrap.wrap(text, width=inner) or [""]
        for i, piece in enumerate(wrapped):
            lab = label if i == 0 else " " * len(label)
            lab = (label_paint or paint.yellow)(lab) if i == 0 else lab
            body = (text_paint or (lambda t: t))(piece)
            lines.append(f"{box['v']} {lab}{body}{' ' * (inner - len(lab) - len(piece))} {box['v']}")

    add_row("Plain:     ", entry.get("plain", ""))
    add_row("Example:   ", entry.get("example", ""))
    add_row("Watch out: ", entry.get("watch_out", ""), text_paint=paint.red)
    related = entry.get("related") or []
    if related:
        add_row("See also:  ", ", ".join(related), text_paint=paint.green)
    stats = entry.get("stats", {})
    if stats.get("quiz_seen"):
        seen = stats["quiz_seen"]
        correct = stats.get("quiz_correct", 0)
        add_row("Quiz:      ", f"{correct}/{seen} correct", text_paint=paint.dim)
    lines.append(box["bl"] + box["h"] * (width - 2) + box["br"])
    return "\n".join(lines)


def print_card(entry: dict, glossary_path: Path, paint: Paint, ascii_only: bool = False, plain_format: bool = False) -> None:
    if plain_format:
        ctx_label = f" --context {entry['context']}" if entry.get("context") else ""
        print(f"$ python3 term_lookup.py{ctx_label}")
        print(f"Term: {entry['term']}")
        print(f"Plain meaning: {entry['plain']}")
        print(f"Real example: {entry['example']}")
        print(f"Watch out for: {entry['watch_out']}")
        print(f"\n[Saved to local glossary: {glossary_path}]")
        return
    print(render_card(entry, paint, ascii_only=ascii_only))
    print(paint.dim(f"[Saved to local glossary: {glossary_path}]"))


# ---------------------------------------------------------------------------
# Glossary storage (backward compatible with v1 files)
# ---------------------------------------------------------------------------
def load_glossary(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_glossary(path: Path, data: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _blank_stats() -> dict:
    return {"lookups": 0, "quiz_seen": 0, "quiz_correct": 0}


def build_entry(term: str, context: str | None, ollama: bool = False,
                ollama_model: str = DEFAULT_OLLAMA_MODEL,
                ollama_host: str = DEFAULT_OLLAMA_HOST) -> tuple[dict, str]:
    """Build a glossary entry for a term. Returns (entry, source).

    source is one of: 'built-in', 'ollama', 'stub' (no card yet).
    """
    key = term.strip().lower()
    base = _TERMS_BY_LOWER_KEY.get(key)
    if base is None:
        # Forgiving forms of the same term: ".json" is the JSON file
        # extension, "A.P.I" is API typed with dots. Try each shape in
        # turn and take the first one the deck actually has.
        for candidate in (key.lstrip("."), key.replace(".", "")):
            base = _TERMS_BY_LOWER_KEY.get(candidate)
            if base:
                break
    ctx = context.strip() if context else None

    if base:
        entry = {
            "term": term.strip(),
            "context": ctx,
            "plain": base["plain"],
            "example": base["example"],
            "watch_out": base["watch_out"],
            "category": base["category"],
            "related": list(base["related"]),
            "source": "built-in",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": _blank_stats(),
        }
        return entry, "built-in"

    if ollama:
        card, err = ollama_generate(term.strip(), ctx, ollama_model, ollama_host)
        if card:
            entry = {
                "term": term.strip(),
                "context": ctx,
                "plain": card.get("plain", ""),
                "example": card.get("example", ""),
                "watch_out": card.get("watch_out", ""),
                "category": card.get("category") if card.get("category") in CATEGORIES else "dev",
                "related": [r for r in (card.get("related") or []) if isinstance(r, str)][:3],
                "source": "ollama",
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "stats": _blank_stats(),
            }
            return entry, "ollama"
        print(f"(Ollama could not write a card right now: {err}. Saved a stub instead -- try again when Ollama is running.)")

    ctx_note = f" (in {ctx} context)" if ctx else ""
    entry = {
        "term": term.strip(),
        "context": ctx,
        "plain": f"No built-in card for '{term.strip()}'{ctx_note} yet -- add your own note with --add, or re-run with --ollama to have your local model write one.",
        "example": f"Look up where '{term.strip()}' appears in your code, log, or config file and jot down one real line.",
        "watch_out": "Don't guess blindly from how a word sounds in everyday English -- check how it's used right there.",
        "category": "dev",
        "related": [],
        "source": "stub",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": _blank_stats(),
    }
    return entry, "stub"


def ollama_generate(term: str, context: str | None, model: str, host: str,
                    timeout: int = 120) -> tuple[dict | None, str]:
    """Ask the local Ollama model to write a plain-English card. Stdlib only.

    Returns (card_dict, None) on success, (None, reason) on failure.
    Nothing leaves the machine: the request goes to localhost.
    """
    ctx_part = f" in the context of {context}" if context else ""
    prompt = (
        f"You are a plain-English teacher for a self-taught programmer who is "
        f"learning to read code and logs. Explain the tech term \"{term}\"{ctx_part}. "
        "Reply with ONLY a JSON object, no markdown, no extra text, with exactly "
        "these keys: \"plain\" (one simple sentence, no jargon), \"example\" (one "
        "real line from code, a log, or a terminal), \"watch_out\" (one practical "
        "pitfall), \"category\" (one of: python, terminal, logs, networking, git, "
        "security, data, dev, files), \"related\" (a list of 2 related tech terms)."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    req = urllib.request.Request(
        host.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return None, "Ollama is not reachable at " + host
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        return None, f"request failed ({exc})"

    text = (data.get("response") or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        card = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                card = json.loads(text[start:end + 1])
            except Exception:
                return None, "model reply was not valid JSON"
        else:
            return None, "model reply was not valid JSON"
    if not isinstance(card, dict) or "plain" not in card:
        return None, "model reply was missing the card"
    return card, None


def record_lookup(glossary: dict[str, dict], entry: dict) -> None:
    """Merge a looked-up entry into the glossary, keeping its quiz stats."""
    key = entry["term"].strip().lower()
    old = glossary.get(key, {})
    old_stats = old.get("stats") or {}
    new_stats = entry.get("stats") or {}
    merged_stats = {
        "lookups": old_stats.get("lookups", 0) + 1,
        "quiz_seen": max(old_stats.get("quiz_seen", 0), new_stats.get("quiz_seen", 0)),
        "quiz_correct": max(old_stats.get("quiz_correct", 0), new_stats.get("quiz_correct", 0)),
    }
    entry["stats"] = merged_stats
    glossary[key] = entry

# ---------------------------------------------------------------------------
# Learning modes: search, quiz, learn, today, stats, export
# ---------------------------------------------------------------------------
def all_known_terms(glossary: dict[str, dict]) -> dict[str, dict]:
    """Built-in deck plus anything saved in the glossary (custom/ollama)."""
    known: dict[str, dict] = {}
    for key, base in TERMS.items():
        known[key] = {
            "term": key,
            "plain": base["plain"],
            "example": base["example"],
            "watch_out": base["watch_out"],
            "category": base["category"],
            "related": list(base["related"]),
            "source": "built-in",
        }
    for key, item in glossary.items():
        known.setdefault(key, {
            "term": item.get("term", key),
            "plain": item.get("plain", ""),
            "example": item.get("example", ""),
            "watch_out": item.get("watch_out", ""),
            "category": item.get("category", "dev"),
            "related": item.get("related") or [],
            "source": item.get("source", "custom"),
        })
    return known


def search_terms(query: str, glossary: dict[str, dict]) -> list[dict]:
    q = query.strip().lower()
    hits = []
    for key, item in all_known_terms(glossary).items():
        hay = " ".join([key, item.get("plain", ""), item.get("example", ""),
                        item.get("category", "")]).lower()
        if q in hay:
            hits.append(item)
    return sorted(hits, key=lambda e: e["term"].lower())


def quiz_accuracy(entry: dict) -> float | None:
    stats = entry.get("stats") or {}
    seen = stats.get("quiz_seen", 0)
    if not seen:
        return None
    return stats.get("quiz_correct", 0) / seen


def run_quiz(glossary: dict[str, dict], glossary_path: Path, paint: Paint,
             rounds: int = 5, ascii_only: bool = False) -> int:
    """Flashcards: show the plain meaning, guess the term. Weakest first."""
    known = all_known_terms(glossary)
    # Stubs have no real card -- their "plain" text IS the answer ("No built-in
    # card for 'X' yet..."), so quizzing them gives the answer away for free
    # and inflates the score. Only real cards (built-in, custom, ollama) play.
    skipped = sum(1 for item in known.values() if item.get("source") == "stub")
    known = {k: v for k, v in known.items() if v.get("source") != "stub"}
    # Attach saved stats so ordering reflects real performance.
    for key, item in known.items():
        saved = glossary.get(key, {})
        item["stats"] = saved.get("stats") or _blank_stats()

    def sort_key(item: dict):
        acc = quiz_accuracy(item)
        seen = (item.get("stats") or {}).get("quiz_seen", 0)
        # Unseen first, then lowest accuracy, then fewest attempts, then name.
        return (0 if acc is None else 1, acc if acc is not None else 0.0, seen,
                item["term"].lower())

    pool = sorted(known.values(), key=sort_key)[: max(1, rounds)]
    if not pool:
        print("No terms to quiz on yet.")
        return 0

    print(paint.bold(f"Quiz time -- {len(pool)} card(s). Weakest terms first."))
    if skipped:
        print(f"(Skipped {skipped} term(s) with no card yet -- fill them in with "
              f"--add or --ollama and they will join the quiz.)")
    print("I show the plain meaning. You type the term. (Ctrl+C to stop early.)\n")
    correct = 0
    for i, item in enumerate(pool, 1):
        print(f"--- Card {i}/{len(pool)} [{CATEGORIES.get(item.get('category', ''), item.get('category', ''))}] ---")
        print(f"  {item['plain']}")
        try:
            answer = input("  What term is this? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        key = item["term"].strip().lower()
        stats = glossary.setdefault(key, dict(item))
        stats["stats"] = stats.get("stats") or _blank_stats()
        stats["stats"]["quiz_seen"] = stats["stats"].get("quiz_seen", 0) + 1
        if answer == key:
            print(paint.green("  Correct!"))
            stats["stats"]["quiz_correct"] = stats["stats"].get("quiz_correct", 0) + 1
            correct += 1
        else:
            print(f"  The term was: {paint.cyan(item['term'])}")
            try:
                knew = input("  Did you actually know it and just mistype? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                knew = ""
            if knew in ("y", "yes"):
                stats["stats"]["quiz_correct"] = stats["stats"].get("quiz_correct", 0) + 1
                correct += 1
                print(paint.green("  Counted as correct -- but watch the spelling next time."))
            else:
                print_card(item, glossary_path, paint, ascii_only=ascii_only)
        print()
    save_glossary(glossary_path, glossary)
    total = min(len(pool), i)
    print(paint.bold(f"Score: {correct}/{total}"))
    if total and correct == total:
        print("Clean sweep. Your weakest terms just got stronger -- that is the whole game.")
    elif total:
        print("The ones you missed will come back first next time. That is how the connections stick.")
    return 0


def run_learn(glossary: dict[str, dict], glossary_path: Path, paint: Paint,
              category: str | None, ascii_only: bool = False) -> int:
    """Walk through one topic (or the whole deck) card by card, at your pace."""
    known = all_known_terms(glossary)
    if category:
        cat = category.strip().lower()
        if cat not in CATEGORIES:
            print(f"Unknown category '{category}'. Try --categories to see them.")
            return 1
        items = [it for it in known.values() if it.get("category") == cat]
        title = CATEGORIES[cat]
    else:
        items = list(known.values())
        title = "the whole deck"
    items.sort(key=lambda e: e["term"].lower())
    print(paint.bold(f"Learning {title} -- {len(items)} card(s). Enter = next card, q = stop.\n"))
    for i, item in enumerate(items, 1):
        print(f"Card {i}/{len(items)}")
        print_card(item, glossary_path, paint, ascii_only=ascii_only)
        record_lookup(glossary, dict(item))
        try:
            nxt = input("[Enter] next, q quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if nxt in ("q", "quit", "exit"):
            break
        print()
    save_glossary(glossary_path, glossary)
    return 0


def term_of_the_day(glossary: dict[str, dict]) -> dict:
    keys = sorted(TERMS)
    idx = date.today().toordinal() % len(keys)
    key = keys[idx]
    base = TERMS[key]
    return {
        "term": key, "plain": base["plain"], "example": base["example"],
        "watch_out": base["watch_out"], "category": base["category"],
        "related": list(base["related"]), "source": "built-in",
    }


def show_stats(glossary: dict[str, dict]) -> int:
    known = all_known_terms(glossary)
    total_lookups = sum((g.get("stats") or {}).get("lookups", 0) for g in glossary.values())
    seen = sum((g.get("stats") or {}).get("quiz_seen", 0) for g in glossary.values())
    correct = sum((g.get("stats") or {}).get("quiz_correct", 0) for g in glossary.values())
    print(f"Built-in deck: {len(TERMS)} terms across {len(CATEGORIES)} topics")
    print(f"Saved in your glossary: {len(glossary)} terms")
    print(f"Total lookups: {total_lookups}")
    if seen:
        print(f"Quiz: {correct}/{seen} correct ({correct / seen:.0%} overall)")
    else:
        print("Quiz: no rounds yet -- try --quiz to start building your score.")

    def weakest():
        scored = []
        for key, g in glossary.items():
            acc = quiz_accuracy(g)
            if acc is not None:
                scored.append((acc, g.get("stats", {}).get("quiz_seen", 0), g.get("term", key)))
        scored.sort()
        return scored[:5]

    weak = weakest()
    if weak:
        print("\nWeakest terms (these come first in the next quiz):")
        for acc, n, term in weak:
            print(f"  - {term}: {acc:.0%} ({n} round{'s' if n != 1 else ''})")
    print("\nDeck by topic:")
    for cat, label in CATEGORIES.items():
        n = sum(1 for t in TERMS.values() if t["category"] == cat)
        print(f"  - {label}: {n}")
    return 0


def export_glossary(glossary: dict[str, dict], fmt: str, out_path: Path) -> int:
    known = all_known_terms(glossary)
    # Attach quiz stats from the saved glossary.
    for key, item in known.items():
        saved = glossary.get(key, {})
        item["stats"] = saved.get("stats") or _blank_stats()
    grouped: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for item in known.values():
        grouped.setdefault(item.get("category", "dev"), []).append(item)
    for items in grouped.values():
        items.sort(key=lambda e: e["term"].lower())

    today = date.today().isoformat()
    if fmt == "md":
        lines = [f"# My Tech Glossary", "", f"Exported {today} -- {len(known)} terms.", ""]
        for cat, label in CATEGORIES.items():
            items = grouped.get(cat, [])
            if not items:
                continue
            lines.append(f"## {label} ({len(items)})")
            lines.append("")
            for item in items:
                lines.append(f"### {item['term']}")
                lines.append(f"- **Plain:** {item['plain']}")
                lines.append(f"- **Example:** {item['example']}")
                lines.append(f"- **Watch out:** {item['watch_out']}")
                if item.get("related"):
                    lines.append(f"- **See also:** {', '.join(item['related'])}")
                stats = item.get("stats") or {}
                if stats.get("quiz_seen"):
                    lines.append(f"- **Quiz:** {stats.get('quiz_correct', 0)}/{stats['quiz_seen']} correct")
                lines.append("")
        out_path.write_text("\n".join(lines), encoding="utf-8")
    else:
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<title>My Tech Glossary</title><style>",
            "body{background:#14161a;color:#e8e8e8;font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;}",
            "h1{color:#7fd4ff} h2{color:#ffd479;border-bottom:1px solid #333;padding-bottom:.3rem}",
            ".card{background:#1d2026;border:1px solid #333;border-radius:10px;padding:1rem;margin:1rem 0}",
            ".card h3{margin:.1rem 0;color:#7fd4ff} .lbl{color:#ffd479;font-weight:700}",
            ".warn{color:#ff9a9a} .rel{color:#9fe8a8}",
            "</style></head><body>",
            f"<h1>My Tech Glossary</h1><p>Exported {today} &mdash; {len(known)} terms.</p>",
        ]
        for cat, label in CATEGORIES.items():
            items = grouped.get(cat, [])
            if not items:
                continue
            parts.append(f"<h2>{label} ({len(items)})</h2>")
            for item in items:
                parts.append("<div class='card'>")
                parts.append(f"<h3>{item['term']}</h3>")
                parts.append(f"<p><span class='lbl'>Plain:</span> {item['plain']}</p>")
                parts.append(f"<p><span class='lbl'>Example:</span> {item['example']}</p>")
                parts.append(f"<p><span class='warn'>Watch out:</span> {item['watch_out']}</p>")
                if item.get("related"):
                    parts.append(f"<p><span class='rel'>See also:</span> {', '.join(item['related'])}</p>")
                stats = item.get("stats") or {}
                if stats.get("quiz_seen"):
                    parts.append(f"<p>Quiz: {stats.get('quiz_correct', 0)}/{stats['quiz_seen']} correct</p>")
                parts.append("</div>")
        parts.append("</body></html>")
        out_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"Exported {len(known)} terms to {out_path}")
    return 0


def add_term_interactive(glossary: dict[str, dict], glossary_path: Path, term: str) -> int:
    print(f"Adding your own card for '{term}'. Plain words, your own example -- that is what makes it stick.")
    try:
        plain = input("Plain meaning (one simple sentence): ").strip()
        example = input("Real example (one line from your code/logs): ").strip()
        watch = input("Watch out for (one pitfall): ").strip()
        cat = input(f"Topic {sorted(CATEGORIES)} [dev]: ").strip().lower() or "dev"
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled -- nothing saved.")
        return 0
    if cat not in CATEGORIES:
        print(f"Unknown topic '{cat}' -- saving under 'dev'.")
        cat = "dev"
    related_raw = ""
    try:
        related_raw = input("See also (comma-separated terms, or blank): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
    related = [r.strip().lower() for r in related_raw.split(",") if r.strip()]
    entry = {
        "term": term.strip(),
        "context": None,
        "plain": plain or "(no plain meaning written yet)",
        "example": example or "",
        "watch_out": watch or "",
        "category": cat,
        "related": related,
        "source": "custom",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": _blank_stats(),
    }
    glossary[term.strip().lower()] = entry
    save_glossary(glossary_path, glossary)
    print(f"Saved '{term.strip()}' to your glossary.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Look up plain-English meanings for tech/log/code terms and save a local glossary.",
        epilog="Examples: term_lookup.py regex --context logs | term_lookup.py --quiz 5 | term_lookup.py --learn python | term_lookup.py --today",
    )
    p.add_argument("term", nargs="?", help="Word or phrase to look up (omit to enter interactive mode)")
    p.add_argument("--context", help="Optional context tag, e.g. logs, python, config")
    p.add_argument("--list", action="store_true", help="List saved terms in your local glossary")
    p.add_argument("--all", action="store_true", help="List the full built-in deck, grouped by topic")
    p.add_argument("--categories", action="store_true", help="List topics and how many terms each has")
    p.add_argument("--category", metavar="TOPIC", help="Browse one topic, e.g. --category logs")
    p.add_argument("--search", metavar="TEXT", help="Find terms by keyword in name or definition")
    p.add_argument("--random", action="store_true", help="Show a random card from the deck")
    p.add_argument("--today", action="store_true", help="Show today's term (same term all day)")
    p.add_argument("--quiz", nargs="?", const=5, type=int, metavar="N", help="Flashcard quiz, weakest terms first (default 5 rounds)")
    p.add_argument("--learn", nargs="?", const=None, metavar="TOPIC", help="Walk through a topic card by card (omit TOPIC for the whole deck)")
    p.add_argument("--add", metavar="TERM", help="Add your own card for TERM, in your own words")
    p.add_argument("--stats", action="store_true", help="Show glossary size, quiz score, weakest terms")
    p.add_argument("--export", choices=["md", "html"], metavar="FORMAT", help="Export the glossary as a study sheet (md or html)")
    p.add_argument("--out", type=Path, help="Output file for --export (default term-glossary.md / .html in this folder)")
    p.add_argument("--ollama", action="store_true", help="If a term has no built-in card, ask local Ollama to write one")
    p.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL, help=f"Ollama model for --ollama (default: {DEFAULT_OLLAMA_MODEL})")
    p.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help=f"Ollama host (default: {DEFAULT_OLLAMA_HOST})")
    p.add_argument("--no-color", action="store_true", help="Disable coloured output")
    p.add_argument("--ascii", action="store_true", help="Use ASCII box characters instead of Unicode")
    p.add_argument("--plain", action="store_true", help="Print the old plain (unboxed) card format")
    p.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY,
                   help=f"Path to glossary JSON file (default: {DEFAULT_GLOSSARY})")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paint = Paint(USE_COLOR and not args.no_color)
    glossary = load_glossary(args.glossary)

    if args.list:
        if not glossary:
            print("No saved terms yet.")
            return 0
        for name in sorted(glossary):
            item = glossary[name]
            ctx = f" [{item['context']}]" if item.get("context") else ""
            src = f" ({item.get('source', 'saved')})" if item.get("source") else ""
            print(f"- {item.get('term', name)}{ctx}{src}: {item.get('plain', '')}")
        return 0

    if args.all:
        known = all_known_terms(glossary)
        for cat, label in CATEGORIES.items():
            items = sorted([it for it in known.values() if it.get("category") == cat],
                           key=lambda e: e["term"].lower())
            if not items:
                continue
            print(paint.bold(f"\n{label} ({len(items)})"))
            for item in items:
                print(f"  - {item['term']}")
        return 0

    if args.categories:
        for cat, label in CATEGORIES.items():
            n = sum(1 for t in TERMS.values() if t["category"] == cat)
            print(f"{cat:12} {label} ({n})")
        return 0

    if args.category:
        cat = args.category.strip().lower()
        if cat not in CATEGORIES:
            print(f"Unknown topic '{args.category}'. Try --categories.")
            return 1
        items = sorted([it for k, it in all_known_terms(glossary).items()
                        if it.get("category") == cat], key=lambda e: e["term"].lower())
        print(paint.bold(f"{CATEGORIES[cat]} -- {len(items)} term(s):"))
        for item in items:
            print(f"- {item['term']}: {item['plain']}")
        return 0

    if args.search:
        hits = search_terms(args.search, glossary)
        if not hits:
            print(f"No terms match '{args.search}'. Try --all to browse, or --add to write your own card.")
            return 0
        print(f"{len(hits)} match(es) for '{args.search}':")
        for item in hits:
            print(f"- {item['term']}: {item['plain']}")
        return 0

    if args.random:
        key = random.choice(sorted(TERMS))
        base = TERMS[key]
        entry = {"term": key, "plain": base["plain"], "example": base["example"],
                 "watch_out": base["watch_out"], "category": base["category"],
                 "related": list(base["related"]), "source": "built-in"}
        record_lookup(glossary, entry)
        save_glossary(args.glossary, glossary)
        print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
        return 0

    if args.today:
        entry = term_of_the_day(glossary)
        record_lookup(glossary, entry)
        save_glossary(args.glossary, glossary)
        print(paint.bold("Term of the day:"))
        print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
        return 0

    if args.quiz is not None:
        return run_quiz(glossary, args.glossary, paint, rounds=args.quiz, ascii_only=args.ascii)

    if args.learn is not None or "--learn" in (argv or sys.argv[1:]):
        # --learn with no value reaches here as None; argparse const handles it.
        return run_learn(glossary, args.glossary, paint, args.learn, ascii_only=args.ascii)

    if args.add:
        return add_term_interactive(glossary, args.glossary, args.add)

    if args.stats:
        return show_stats(glossary)

    if args.export:
        out = args.out or Path(f"term-glossary.{args.export}")
        return export_glossary(glossary, args.export, out)

    if args.term:
        entry, source = build_entry(args.term, args.context, ollama=args.ollama,
                                    ollama_model=args.ollama_model, ollama_host=args.host)
        record_lookup(glossary, entry)
        save_glossary(args.glossary, glossary)
        print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
        if source == "ollama":
            print(paint.green("(Card written by your local Ollama model and saved -- it is yours now.)"))
        return 0

    # Interactive mode: type one term at a time; blank line or Ctrl+C to quit.
    print("Interactive term lookup. Type a term and press Enter (blank line or Ctrl+C to exit).")
    print("Commands: :quiz [n]  :random  :today  :list  :stats  :help  :quit")
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            break
        if raw.startswith(":"):
            parts = raw[1:].split()
            cmd = parts[0].lower() if parts else ""
            if cmd in ("q", "quit", "exit"):
                break
            if cmd == "help":
                print("  :quiz [n]  flashcard quiz (weakest first)   :random  random card")
                print("  :today     today's term                      :list    your saved terms")
                print("  :stats     glossary + quiz score             :quit    exit")
                continue
            if cmd == "quiz":
                n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                run_quiz(glossary, args.glossary, paint, rounds=n, ascii_only=args.ascii)
                glossary = load_glossary(args.glossary)
                continue
            if cmd == "random":
                key = random.choice(sorted(TERMS))
                base = TERMS[key]
                entry = {"term": key, "plain": base["plain"], "example": base["example"],
                         "watch_out": base["watch_out"], "category": base["category"],
                         "related": list(base["related"]), "source": "built-in"}
                record_lookup(glossary, entry)
                save_glossary(args.glossary, glossary)
                print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
                continue
            if cmd == "today":
                entry = term_of_the_day(glossary)
                record_lookup(glossary, entry)
                save_glossary(args.glossary, glossary)
                print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
                continue
            if cmd == "list":
                for name in sorted(glossary):
                    item = glossary[name]
                    print(f"- {item.get('term', name)}: {item.get('plain', '')}")
                continue
            if cmd == "stats":
                show_stats(glossary)
                continue
            print(f"Unknown command '{raw}'. Try :help.")
            continue
        entry, source = build_entry(raw, args.context, ollama=args.ollama,
                                    ollama_model=args.ollama_model, ollama_host=args.host)
        record_lookup(glossary, entry)
        save_glossary(args.glossary, glossary)
        print_card(entry, args.glossary, paint, ascii_only=args.ascii, plain_format=args.plain)
        if source == "ollama":
            print(paint.green("(Card written by your local Ollama model and saved -- it is yours now.)"))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
