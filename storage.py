import json
import sqlite3
from contextlib import closing
from accounts import DATABASE


def initialise_storage():
    with closing(sqlite3.connect(DATABASE)) as db:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS profiles (
                username TEXT PRIMARY KEY, genres TEXT NOT NULL,
                start_year INTEGER NOT NULL, end_year INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS rating_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL, movie_title TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                saved_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%d %H:%M:%S', 'now')))""")
            db.execute("""CREATE TABLE IF NOT EXISTS viewing_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL, movie_title TEXT NOT NULL,
                watched_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%d %H:%M:%S', 'now')))""")


def save_profile(username, profile):
    start, end = profile["years"]
    if not (1888 <= start <= end <= 2100):
        raise ValueError("Check the release-year range.")
    with closing(sqlite3.connect(DATABASE)) as db:
        with db:
            db.execute("""INSERT INTO profiles VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                genres=excluded.genres, start_year=excluded.start_year,
                end_year=excluded.end_year""",
                (username, json.dumps(profile["genres"]), start, end))


def load_profile(username):
    with closing(sqlite3.connect(DATABASE)) as db:
        row = db.execute(
            "SELECT genres, start_year, end_year FROM profiles WHERE username=?",
            (username,)).fetchone()
    return None if row is None else {
        "genres": json.loads(row[0]), "years": (row[1], row[2])}


def save_rating(username, movie_title, rating):
    if type(rating) is not int or not 1 <= rating <= 5:
        raise ValueError("Rating must be an integer from 1 to 5.")
    with closing(sqlite3.connect(DATABASE)) as db:
        with db:
            db.execute("""INSERT INTO rating_events
                (username, movie_title, rating) VALUES (?, ?, ?)""",
                (username, movie_title, rating))


def load_ratings(username):
    with closing(sqlite3.connect(DATABASE)) as db:
        rows = db.execute("""SELECT movie_title, rating
            FROM rating_events WHERE username=? ORDER BY id""",
            (username,)).fetchall()
    return dict(rows)


def load_rating_history(username):
    with closing(sqlite3.connect(DATABASE)) as db:
        rows = db.execute("""SELECT movie_title, rating, saved_at
            FROM rating_events WHERE username=? ORDER BY id DESC""",
            (username,)).fetchall()
    return [dict(zip(["Movie", "Rating", "Saved At (UTC)"], row)) for row in rows]


def save_viewing(username, movie_title):
    with closing(sqlite3.connect(DATABASE)) as db:
        with db:
            db.execute("""INSERT INTO viewing_events
                (username, movie_title) VALUES (?, ?)""", (username, movie_title))


def load_viewings(username):
    with closing(sqlite3.connect(DATABASE)) as db:
        rows = db.execute("""SELECT movie_title, watched_at
            FROM viewing_events WHERE username=? ORDER BY id""",
            (username,)).fetchall()
    return [dict(zip(["Movie", "Watched At (UTC)"], row)) for row in rows]


def load_recent_viewings():
    with closing(sqlite3.connect(DATABASE)) as db:
        rows = db.execute("""SELECT movie_title, watched_at
            FROM viewing_events
            WHERE watched_at >= datetime('now', '-7 days')
              AND watched_at <= datetime('now') ORDER BY id""").fetchall()
    return [dict(zip(["Movie", "Watched At (UTC)"], row)) for row in rows]


def load_all_viewings():
    with closing(sqlite3.connect(DATABASE)) as db:
        rows = db.execute("""SELECT username, movie_title, watched_at
            FROM viewing_events ORDER BY id""").fetchall()
    return [dict(zip(["User", "Movie", "Watched At (UTC)"], row)) for row in rows]


initialise_storage()
