import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path

import accounts
import storage
import catalogue
from catalogue import MovieCatalogue
from domain import Movie, ViewerProfile, RecommendationService

ROOT = Path(__file__).resolve().parent


@contextmanager
def db_session(path):
    with closing(sqlite3.connect(path)) as db:
        with db:
            yield db


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.db = Path(self.temp.name) / "test.db"
        accounts.DATABASE = self.db
        storage.DATABASE = self.db
        catalogue.DATABASE = self.db
        accounts.initialise_accounts()
        storage.initialise_storage()
        self.catalogue = MovieCatalogue(ROOT / "movies.csv", self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_account_password_hash_and_case_insensitive_login(self):
        self.assertTrue(accounts.create_account("Sultan", "Example-only-123")[0])
        self.assertTrue(accounts.check_login(" SULTAN ", "Example-only-123"))
        self.assertFalse(accounts.check_login("sultan", "Wrong-password"))
        with db_session(self.db) as db:
            salt, digest = db.execute("SELECT salt, password_hash FROM accounts").fetchone()
        self.assertEqual(len(salt), 32)
        self.assertNotIn("Example-only-123", (salt, digest))

    def test_duplicate_account_and_validation(self):
        self.assertFalse(accounts.create_account("a", "short")[0])
        self.assertFalse(accounts.create_account("bad name", "Example-only-123")[0])
        self.assertTrue(accounts.create_account("sultan", "Example-only-123")[0])
        self.assertFalse(accounts.create_account("SULTAN", "Example-only-123")[0])

    def test_profile_roundtrip_and_user_isolation(self):
        profile = {"genres": ["Animation"], "years": (2010, 2026)}
        storage.save_profile("sultan", profile)
        self.assertEqual(storage.load_profile("sultan"), profile)
        self.assertIsNone(storage.load_profile("other"))
        with self.assertRaises(ValueError):
            storage.save_profile("sultan", {"genres": [], "years": (2026, 1990)})

    def test_latest_rating_and_complete_history(self):
        storage.save_rating("sultan", "Arrival", 4)
        storage.save_rating("sultan", "Arrival", 2)
        self.assertEqual(storage.load_ratings("sultan"), {"Arrival": 2})
        self.assertEqual([row["Rating"] for row in storage.load_rating_history("sultan")], [2, 4])
        self.assertEqual(storage.load_ratings("other"), {})
        self.assertTrue(storage.load_rating_history("sultan")[0]["Saved At (UTC)"])

    def test_invalid_rating_rejected(self):
        for rating in (0, 6, True, 2.5, "4"):
            with self.assertRaises(ValueError):
                storage.save_rating("sultan", "Arrival", rating)
        self.assertEqual(storage.load_ratings("sultan"), {})

    def test_repeated_viewings_and_user_isolation(self):
        storage.save_viewing("sultan", "Coco")
        storage.save_viewing("sultan", "Coco")
        self.assertEqual(len(storage.load_viewings("sultan")), 2)
        self.assertEqual(storage.load_viewings("other"), [])
        self.assertEqual(len(storage.load_all_viewings()), 2)

    def test_recent_viewings_exclude_old_and_future(self):
        storage.save_viewing("sultan", "Coco")
        with db_session(self.db) as db:
            db.execute("""INSERT INTO viewing_events (username, movie_title, watched_at)
                          VALUES ('other', 'Arrival', datetime('now', '-8 days'))""")
            db.execute("""INSERT INTO viewing_events (username, movie_title, watched_at)
                          VALUES ('other', 'Gravity', datetime('now', '+1 day'))""")
        self.assertEqual([row["Movie"] for row in storage.load_recent_viewings()], ["Coco"])
        self.assertEqual(len(storage.load_all_viewings()), 3)

    def test_existing_schema_initialisation_preserves_data(self):
        accounts.create_account("sultan", "Example-only-123")
        storage.save_rating("sultan", "Arrival", 4)
        storage.save_viewing("sultan", "Coco")
        accounts.initialise_accounts()
        storage.initialise_storage()
        self.assertTrue(accounts.check_login("sultan", "Example-only-123"))
        self.assertEqual(storage.load_ratings("sultan"), {"Arrival": 4})
        self.assertEqual(len(storage.load_viewings("sultan")), 1)

    def test_add_and_reload_catalogue(self):
        movie_id = self.catalogue.add_movie("Sultan Test Film", "Drama", 2026)
        reloaded = MovieCatalogue(ROOT / "movies.csv", self.db)
        added = next(row for row in reloaded.list_movies() if row["id"] == movie_id)
        self.assertEqual(added["title"], "Sultan Test Film")
        self.assertEqual(len(reloaded.list_movies()), 13)

    def test_duplicate_blank_genre_and_year_validation(self):
        bad = [("arrival", "Sci-Fi", 2016), (" ", "Drama", 2026),
               ("Valid", "Bad Genre", 2026), ("Valid", "Drama", 1800),
               ("Valid", "Drama", 2026.5)]
        for title, genre, year in bad:
            with self.assertRaises(ValueError):
                self.catalogue.add_movie(title, genre, year)
        self.assertEqual(len(self.catalogue.list_movies()), 12)

    def test_edit_title_migrates_user_records(self):
        storage.save_rating("sultan", "Arrival", 4)
        storage.save_viewing("sultan", "Arrival")
        self.catalogue.edit_movie(1, "Arrival Updated", "Drama", 2017)
        self.assertEqual(storage.load_ratings("sultan"), {"Arrival Updated": 4})
        self.assertEqual(storage.load_viewings("sultan")[0]["Movie"], "Arrival Updated")
        row = next(row for row in self.catalogue.list_movies() if row["id"] == 1)
        self.assertEqual((row["genre"], row["year"]), ("Drama", 2017))

    def test_duplicate_rename_rolls_back(self):
        storage.save_rating("sultan", "Arrival", 4)
        with self.assertRaises(ValueError):
            self.catalogue.edit_movie(1, "Gravity", "Drama", 2026)
        self.assertEqual(storage.load_ratings("sultan"), {"Arrival": 4})
        self.assertEqual(self.catalogue.list_movies()[0]["title"], "Arrival")

    def test_remove_preserves_history_and_stays_removed(self):
        storage.save_viewing("sultan", "Arrival")
        self.catalogue.remove_movie(1)
        self.assertNotIn("Arrival", [row["title"] for row in self.catalogue.list_movies()])
        self.assertEqual(storage.load_viewings("sultan")[0]["Movie"], "Arrival")
        self.assertEqual(len(MovieCatalogue(ROOT / "movies.csv", self.db).list_movies()), 11)

    def test_empty_catalogue_is_not_reseeded(self):
        for row in self.catalogue.list_movies():
            self.catalogue.remove_movie(row["id"])
        self.assertEqual(MovieCatalogue("missing.csv", self.db).list_movies(), [])
        self.catalogue.add_movie("Fresh Film", "Drama", 2026)
        self.assertEqual(len(self.catalogue.list_movies()), 1)

    def test_missing_movie_edit_and_remove(self):
        with self.assertRaises(ValueError):
            self.catalogue.edit_movie(9999, "Missing", "Drama", 2026)
        with self.assertRaises(ValueError):
            self.catalogue.remove_movie(9999)

    def test_sql_characters_are_saved_as_literal_title(self):
        title = "Director's Cut; DROP TABLE accounts;"
        movie_id = self.catalogue.add_movie(title, "Drama", 2026)
        self.assertEqual(self.catalogue.list_movies()[-1]["id"], movie_id)
        with db_session(self.db) as db:
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='accounts'").fetchone())


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.movies = [
            Movie(1, "Arrival", "Sci-Fi", 2016),
            Movie(2, "The Martian", "Sci-Fi", 2015),
            Movie(3, "Gravity", "Sci-Fi", 2013),
            Movie(4, "Soul", "Animation", 2020),
            Movie(5, "Coco", "Animation", 2017),
            Movie(6, "Ratatouille", "Animation", 2007),
            Movie(7, "Skyfall", "Action", 2012),
        ]
        self.engine = RecommendationService(self.movies)

    def test_genre_and_inclusive_year_bounds(self):
        profile = ViewerProfile("sultan", ["Animation"], (2017, 2020))
        self.assertEqual([row["Movie"] for row in self.engine.recommend(profile)], ["Soul", "Coco"])

    def test_watched_and_rated_excluded(self):
        profile = ViewerProfile("sultan", ["Animation"], (1990, 2026),
                                {"Soul": 5}, {"Coco"})
        self.assertEqual([row["Movie"] for row in self.engine.recommend(profile)], ["Ratatouille"])

    def test_ratings_affect_ranking(self):
        profile = ViewerProfile("sultan", [], (1990, 2026), {"Arrival": 5})
        picks = self.engine.recommend(profile)
        self.assertEqual(picks[0]["Movie"], "The Martian")
        self.assertIn("positive ratings", picks[0]["Why this pick"])

    def test_dislike_suppresses_related_genre(self):
        profile = ViewerProfile("sultan", [], (1990, 2026), {"Arrival": 1})
        self.assertNotIn("Sci-Fi", [row["Genre"] for row in self.engine.recommend(profile)])

    def test_watch_history_influences_priority(self):
        profile = ViewerProfile("sultan", [], (1990, 2026), {}, {"Arrival"})
        self.assertEqual(self.engine.recommend(profile)[0]["Movie"], "The Martian")

    def test_missing_old_titles_do_not_create_signals(self):
        profile = ViewerProfile("sultan", [], (1990, 2026), {"Removed Film": 5}, {"Unknown"})
        self.assertEqual(self.engine.recommend(profile)[0]["Movie"], "Soul")

    def test_empty_and_limit(self):
        self.assertEqual(RecommendationService([]).recommend(ViewerProfile("sultan")), [])
        self.assertEqual(self.engine.recommend(ViewerProfile("sultan"), 0), [])
        self.assertEqual(len(self.engine.recommend(ViewerProfile("sultan"), 2)), 2)


if __name__ == "__main__":
    unittest.main()
