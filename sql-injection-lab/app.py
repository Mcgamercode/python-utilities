"""
SQL Injection Lab - REAL working version
For local learning only, on your own machine, 127.0.0.1 only.

Two logins side by side, same users table:
  /vuln  - VULNERABLE: builds SQL with an f-string, executes it for real
  /safe  - FIXED: uses a parameterized query (? placeholders)

Run it:
  python app.py
Then open http://127.0.0.1:5000 in your browser.

Lab accounts (plaintext on purpose, this is a lab, never do this in real code):
  admin / admin123
  user  / user123

Try on /vuln, username box, password anything:
  admin' --
That comments out the password check. The page shows you the exact
SQL it ran, so you can see why it worked.

Why the classic ' OR '1'='1 payload is tricky here:
  The query is  WHERE username = '<you>' AND password = '<pass>'
  AND binds tighter than OR, so
  '' OR '1'='1' AND password='x'  =  '' OR ('1'='1' AND 'x'='x' is false)
  It fails. The -- comment payload works because it deletes the rest.
  That AND/OR precedence trap is a real pentest lesson.
"""

import os
import sqlite3
from flask import Flask, g, request, render_template_string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Fresh lab DB every start, so you can reset by restarting."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)"
    )
    db.execute("INSERT INTO users VALUES (1, 'admin', 'admin123')")
    db.execute("INSERT INTO users VALUES (2, 'user', 'user123')")
    db.commit()
    db.close()


FORM = """
<h1>{{ title }}</h1>
<p>{{ note }}</p>
<form method="post" action="{{ action }}">
  <label>Username: <input type="text" name="username"></label><br><br>
  <label>Password: <input type="password" name="password"></label><br><br>
  <button type="submit">Login</button>
</form>
<p><a href="/">Back to home</a></p>
"""

RESULT = """
<h1>{{ title }}</h1>
<p><b>SQL that actually ran:</b></p>
<pre>{{ query }}</pre>
<p>{{ message }}</p>
<p><a href="{{ back }}">Try again</a> | <a href="/">Home</a></p>
"""

INDEX = """
<h1>SQL Injection Lab</h1>
<p>Local only, 127.0.0.1. Same users table, two different ways of asking it.</p>
<p>Lab accounts: <b>admin / admin123</b> and <b>user / user123</b></p>
<ul>
  <li><a href="/vuln">/vuln - Vulnerable login</a> - f-string SQL, really executes</li>
  <li><a href="/safe">/safe - Fixed login</a> - parameterized query, ? placeholders</li>
</ul>
<p>On /vuln, try username <code>admin' --</code> with any password, and watch the SQL it shows you.</p>
<p>Then try the exact same thing on /safe. It should fail, and the SQL it shows will still have the ? placeholders, with your input kept separate.</p>
"""


@app.route("/")
def index():
    return render_template_string(INDEX)


@app.route("/vuln")
def vuln_form():
    return render_template_string(
        FORM,
        title="Vulnerable Login",
        note="This one builds SQL with an f-string and runs it. Watch what it does with your input.",
        action="/vuln/login",
    )


@app.route("/vuln/login", methods=["POST"])
def vuln_login():
    username = request.form["username"]
    password = request.form["password"]
    # THE VULNERABILITY: user input pasted straight into the SQL string.
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
    try:
        row = get_db().execute(query).fetchone()
    except sqlite3.Error as e:
        return render_template_string(
            RESULT,
            title="Vulnerable Login - SQL error",
            query=query,
            message=f"SQL broke: {e}. That error itself is information to an attacker.",
            back="/vuln",
        )
    if row:
        msg = f"Welcome, {row['username']}! You are logged in as id {row['id']}."
    else:
        msg = "Invalid credentials"
    return render_template_string(
        RESULT, title="Vulnerable Login", query=query, message=msg, back="/vuln"
    )


@app.route("/safe")
def safe_form():
    return render_template_string(
        FORM,
        title="Fixed Login",
        note="This one uses a parameterized query. Your input is data, never code.",
        action="/safe/login",
    )


@app.route("/safe/login", methods=["POST"])
def safe_login():
    username = request.form["username"]
    password = request.form["password"]
    # THE FIX: ? placeholders. sqlite3 sends the values separately,
    # so even admin' -- is just treated as a weird username to look up.
    query = "SELECT * FROM users WHERE username = ? AND password = ?"
    row = get_db().execute(query, (username, password)).fetchone()
    if row:
        msg = f"Welcome, {row['username']}! You are logged in as id {row['id']}."
    else:
        msg = "Invalid credentials"
    return render_template_string(
        RESULT, title="Fixed Login", query=query, message=msg, back="/safe"
    )


if __name__ == "__main__":
    init_db()
    # 127.0.0.1 only, debug on for learning. Never expose this.
    app.run(host="127.0.0.1", port=5000, debug=True)
