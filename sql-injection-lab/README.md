# SQL Injection Lab - real version

Local learning lab only. Runs on `127.0.0.1:5000`, nothing leaves your machine.

Your Qwen model gave you a mock version where the SQL string was built but never executed, so injection could not actually work. This version uses a real `sqlite3` database, so it can.

## Run it

```powershell
# Windows PowerShell, from this folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install flask
python app.py
```

```bash
# Linux / Termux / Kali

```

Then open http://127.0.0.1:5000

Restarting `app.py` resets the database fresh.

## Lab accounts

- `admin` / `admin123`
- `user` / `user123`

Plaintext on purpose for the lab. Never do this in real code.

## What to try

1. Log in normally on `/vuln` with `admin` / `admin123`. It works.
2. On `/vuln`, put this in the username box, any password:

```
   admin' --
```

   You log in as admin without the password. The result page shows the exact SQL that ran, so you can see the `--` commented out the password check.

3. Try the same payload on `/safe`. It fails. The result page shows the query still has `?` placeholders, your input was sent as data, not code.
4. Try `' OR '1'='1` on `/vuln` and watch it fail. That is the AND/OR precedence trap explained in `app.py`: `AND` binds tighter than `OR`, so that payload does not bypass this exact query shape.

## The lesson in one line

- Vulnerable: `f"SELECT ... WHERE username = '{username}' ..."` - input becomes part of the code.
- Fixed: `"SELECT ... WHERE username = ? AND password = ?"` with `(username, password)` passed separately - input stays data.

## Safety

- Binds to `127.0.0.1` only.
- `debug=True` is on for learning. Never expose this app to a network, and never use this pattern in real code.