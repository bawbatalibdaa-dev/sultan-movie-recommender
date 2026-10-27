import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from accounts import DATABASE


class MovieCatalogue:
    GENRES = ("Action", "Animation", "Comedy", "Drama", "Sci-Fi", "Thriller")

    def __init__(self, seed_csv="movies.csv", database=None):
        self.database = Path(database) if database is not None else DATABASE
        self.seed_csv = Path(seed_csv)
        with closing(sqlite3.connect(self.database, timeout=15)) as db:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    genre TEXT NOT NULL, year INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1)""")
                if db.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0:
                    with self.seed_csv.open(encoding="utf-8-sig", newline="") as source:
                        for row in csv.DictReader(source):
                            values = self._validate(
                                row["title"], row["genre"], int(row["year"]))
                            db.execute("""INSERT INTO movies
                                (id, title, genre, year) VALUES (?, ?, ?, ?)""",
                                (int(row["id"]), *values))

    def _validate(self, title, genre, year):
        title = title.strip()
        if not 1 <= len(title) <= 150:
            raise ValueError("Enter a movie title with 1 to 150 characters.")
        if genre not in self.GENRES:
            raise ValueError("Select one of the available genres.")
        maximum_year = datetime.now(timezone.utc).year + 2
        if type(year) is not int or not 1888 <= year <= maximum_year:
            raise ValueError(f"Enter a whole release year from 1888 to {maximum_year}.")
        return title, genre, year

    def list_movies(self):
        with closing(sqlite3.connect(self.database, timeout=15)) as db:
            rows = db.execute("""SELECT id, title, genre, year FROM movies
                WHERE active=1 ORDER BY id""").fetchall()
        return [dict(zip(["id", "title", "genre", "year"], row)) for row in rows]

    def add_movie(self, title, genre, year):
        values = self._validate(title, genre, year)
        try:
            with closing(sqlite3.connect(self.database, timeout=15)) as db:
                with db:
                    cursor = db.execute("""INSERT INTO movies
                        (title, genre, year) VALUES (?, ?, ?)""", values)
                    return cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError("That title already exists, including removed titles.") from error

    def edit_movie(self, movie_id, title, genre, year):
        values = self._validate(title, genre, year)
        try:
            with closing(sqlite3.connect(self.database, timeout=15)) as db:
                with db:
                    old = db.execute("SELECT title FROM movies WHERE id=? AND active=1",
                                     (movie_id,)).fetchone()
                    if old is None:
                        raise ValueError("This movie is no longer available.")
                    db.execute("UPDATE movies SET title=?, genre=?, year=? WHERE id=?",
                               (*values, movie_id))
                    # Migrate the prototype's title-based records in the same transaction.
                    for table in ("rating_events", "viewing_events"):
                        exists = db.execute("""SELECT 1 FROM sqlite_master
                            WHERE type='table' AND name=?""", (table,)).fetchone()
                        if exists:
                            db.execute(f"UPDATE {table} SET movie_title=? WHERE movie_title=?",
                                       (values[0], old[0]))
        except sqlite3.IntegrityError as error:
            raise ValueError("Another movie already uses that title.") from error

    def remove_movie(self, movie_id):
        with closing(sqlite3.connect(self.database, timeout=15)) as db:
            with db:
                result = db.execute("UPDATE movies SET active=0 WHERE id=? AND active=1",
                                    (movie_id,))
                if result.rowcount != 1:
                    raise ValueError("This movie is no longer available.")
