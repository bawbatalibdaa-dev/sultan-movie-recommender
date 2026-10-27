import hashlib
import hmac
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE = Path(__file__).with_name("cinema_compass.db")


def initialise_accounts():
    with closing(sqlite3.connect(DATABASE)) as db:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY, salt TEXT NOT NULL,
                password_hash TEXT NOT NULL)""")


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                              bytes.fromhex(salt), 600_000).hex()


def create_account(username, password):
    username = username.strip().lower()
    if not 3 <= len(username) <= 30:
        return False, "Use a username with 3 to 30 characters."
    if not all(c.isascii() and (c.isalnum() or c == "_") for c in username):
        return False, "Use letters, numbers or underscores."
    if not 8 <= len(password) <= 128:
        return False, "Use a password with 8 to 128 characters."
    salt = secrets.token_hex(16)
    digest = hash_password(password, salt)
    try:
        with closing(sqlite3.connect(DATABASE)) as db:
            with db:
                db.execute("INSERT INTO accounts VALUES (?, ?, ?)",
                           (username, salt, digest))
        return True, "Account created. You can now log in."
    except sqlite3.IntegrityError:
        return False, "This username is already registered."


def check_login(username, password):
    if not 8 <= len(password) <= 128:
        return False
    with closing(sqlite3.connect(DATABASE)) as db:
        row = db.execute(
            "SELECT salt, password_hash FROM accounts WHERE username=?",
            (username.strip().lower(),)).fetchone()
    return row is not None and hmac.compare_digest(
        hash_password(password, row[0]), row[1])


initialise_accounts()
