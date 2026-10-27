from dataclasses import dataclass, field


@dataclass(frozen=True)
class Movie:
    id: int
    title: str
    genre: str
    year: int

    def display_label(self):
        return f"{self.title} ({self.year})"


@dataclass
class ViewerProfile:
    username: str
    preferred_genres: list = field(default_factory=list)
    release_years: tuple = (1990, 2026)
    ratings: dict = field(default_factory=dict)
    watched_titles: set = field(default_factory=set)

    def has_seen_or_rated(self, title):
        return title in self.ratings or title in self.watched_titles


class RecommendationService:
    """An explainable scoring baseline, without a trained ML model."""

    def __init__(self, movies, history_weight=0.25):
        self.movies = list(movies)
        self.history_weight = history_weight

    def recommend(self, profile, limit=5):
        if limit <= 0:
            return []
        by_title = {movie.title: movie for movie in self.movies}
        genre_votes = {}
        for title, rating in profile.ratings.items():
            if title in by_title:
                genre = by_title[title].genre
                genre_votes.setdefault(genre, []).append(rating - 3)
        watched_genres = {
            by_title[title].genre for title in profile.watched_titles if title in by_title
        }
        ranked = []
        start, end = profile.release_years
        for movie in self.movies:
            if profile.has_seen_or_rated(movie.title) or not start <= movie.year <= end:
                continue
            if profile.preferred_genres and movie.genre not in profile.preferred_genres:
                continue
            votes = genre_votes.get(movie.genre, [])
            affinity = sum(votes) / len(votes) if votes else 0
            score = (2 if profile.preferred_genres else 1) + affinity
            if movie.genre in watched_genres:
                score += self.history_weight
            related = [
                (by_title[title], rating - 3)
                for title, rating in profile.ratings.items()
                if title in by_title and by_title[title].genre == movie.genre
            ]
            if related:
                score += 0.35 * sum(
                    vote / (1 + abs(movie.year - rated.year) / 10)
                    for rated, vote in related
                ) / len(related)
            if score <= 0:
                continue
            reasons = ["Saved genre and year range" if profile.preferred_genres
                       else "Within your release-year range"]
            if affinity > 0:
                reasons.append("positive ratings in this genre")
            elif affinity < 0:
                reasons.append("lower priority after your ratings")
            if movie.genre in watched_genres:
                reasons.append("similar to your viewing history")
            ranked.append({"Movie": movie.title, "Genre": movie.genre,
                           "Year": movie.year, "Why this pick": "; ".join(reasons),
                           "_score": score})
        ranked.sort(key=lambda row: (-row["_score"], -row["Year"], row["Movie"].casefold()))
        return [{key: value for key, value in row.items() if key != "_score"}
                for row in ranked[:limit]]
