from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from accounts import create_account, check_login
from storage import (
    load_profile, save_profile, load_ratings, save_rating,
    load_rating_history, load_viewings, save_viewing, load_recent_viewings,
)
from catalogue import MovieCatalogue
from domain import Movie, ViewerProfile, RecommendationService
from admin_panel import render_admin

st.set_page_config(page_title="Cinema Compass", page_icon="🎬", layout="wide")


def authenticate():
    if st.session_state.get("current_user") is not None:
        return st.session_state.current_user
    st.title("Cinema Compass")
    st.write("Log in or create an account to continue.")
    login, register = st.tabs(["Log In", "Create Account"])
    with login:
        with st.form("login_form"):
            name = st.text_input("Username", key="login_name")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In")
        if submitted:
            if check_login(name, password):
                st.session_state.clear()
                st.session_state.current_user = name.strip().lower()
                st.rerun()
            st.error("Incorrect username or password.")
    with register:
        with st.form("register_form"):
            name = st.text_input("Choose a username")
            password = st.text_input("Choose a password", type="password")
            confirmation = st.text_input("Confirm your password", type="password")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            if password != confirmation:
                st.error("The passwords do not match.")
            else:
                created, message = create_account(name, password)
                (st.success if created else st.error)(message)
    st.stop()


username = authenticate()
catalogue = MovieCatalogue(Path(__file__).with_name("movies.csv"))
movie_rows = catalogue.list_movies()
movies = pd.DataFrame(movie_rows, columns=["id", "title", "genre", "year"])

with st.sidebar:
    st.title("Cinema Compass")
    st.write(f"Logged in as: {username}")
    page = st.radio("Navigation", ["Discover", "My Activity", "Catalogue Manager"])
    if st.button("Log Out"):
        st.session_state.clear()
        st.rerun()

notice = st.session_state.pop("user_notice", None)
if notice:
    st.success(notice)

if page == "Catalogue Manager":
    render_admin(catalogue)
    st.stop()

# Read each user's saved records before calculating recommendations.
saved_profile = load_profile(username)
ratings = load_ratings(username)
journal = load_viewings(username)
year_now = datetime.now(timezone.utc).year

if page == "Discover":
    st.title("Cinema Compass")
    st.write("Find your next movie through your interests and viewing history.")
    st.header("Explore the Catalogue")
    search_column, genre_column = st.columns([2, 1])
    with search_column:
        search = st.text_input("Search for a movie")
    with genre_column:
        genre_filter = st.selectbox(
            "Choose a genre", ["All genres"] + sorted(movies["genre"].unique().tolist()))
    results = movies.copy()
    if search.strip():
        results = results[results["title"].str.contains(
            search.strip(), case=False, regex=False, na=False)]
    if genre_filter != "All genres":
        results = results[results["genre"] == genre_filter]
    st.caption(f"{len(results)} movie(s) found")
    if results.empty:
        st.info("No movies match your search.")
    else:
        st.dataframe(results[["title", "genre", "year"]],
                     hide_index=True, width="stretch")

    st.divider()
    st.header("Build Your Movie Profile")
    initial = saved_profile or {"genres": [], "years": (1990, year_now)}
    # Keep saved genres selectable even if the last movie of a genre was removed.
    available_genres = sorted(set(catalogue.GENRES) | set(initial["genres"]))
    with st.form("profile_form"):
        preferred = st.multiselect("Which genres do you enjoy?", available_genres,
                                  default=initial["genres"])
        years = st.slider("Preferred release years", 1888, max(year_now + 2, initial["years"][1]),
                          value=tuple(initial["years"]))
        save = st.form_submit_button("Save My Profile")
    if save:
        save_profile(username, {"genres": preferred, "years": years})
        st.session_state.user_notice = "Your movie profile has been saved."
        st.rerun()

    st.divider()
    st.header("Your Movie Picks")
    if saved_profile is None:
        st.info("Save your movie profile to see recommendations.")
    else:
        profile = ViewerProfile(
            username=username,
            preferred_genres=saved_profile["genres"],
            release_years=tuple(saved_profile["years"]),
            ratings=ratings,
            watched_titles={entry["Movie"] for entry in journal},
        )
        engine = RecommendationService([Movie(**row) for row in movie_rows])
        picks = engine.recommend(profile)
        st.caption(
            "Uses your saved genres, year range, ratings and viewing history. "
            "Already watched or rated movies are excluded. "
            "Ranking considers genre feedback and release-period similarity.")
        if picks:
            st.dataframe(pd.DataFrame(picks), hide_index=True, width="stretch")
        else:
            st.info("No matching movies. Try adjusting your profile.")

    st.divider()
    st.header("Community Trends")
    st.caption(
        "Recorded viewings across all users in the last 7 days for the current catalogue. "
        "Repeat viewings are counted separately.")
    recent = load_recent_viewings()
    if not recent:
        st.info("Record a viewing to start building community trends.")
    else:
        trend = pd.DataFrame(recent).merge(
            movies[["title", "genre"]], left_on="Movie", right_on="title", how="inner")
        if trend.empty:
            st.info("No recent viewings match the current catalogue.")
        else:
            movie_column, genre_column = st.columns(2)
            with movie_column:
                st.subheader("Trending Movies")
                counts = trend["Movie"].value_counts().head(5)
                st.bar_chart(counts.rename("Viewings").to_frame())
            with genre_column:
                st.subheader("Popular Genres")
                counts = trend["genre"].value_counts()
                st.bar_chart(counts.rename("Viewings").to_frame())

elif page == "My Activity":
    st.title("My Activity")
    st.header("Rate a Movie")
    if movies.empty:
        st.info("The catalogue is empty. Ratings can be added after a movie is available.")
    else:
        by_id = {row["id"]: Movie(**row) for row in movie_rows}
        chosen = st.selectbox("Select a movie to rate", list(by_id),
                             format_func=lambda key: by_id[key].display_label())
        selected_movie = by_id[chosen]
        with st.form(f"rating_form_{chosen}"):
            rating = st.radio("Your rating: 1 = dislike, 5 = love", [1, 2, 3, 4, 5],
                              index=ratings.get(selected_movie.title, 3) - 1, horizontal=True)
            save = st.form_submit_button("Save Rating")
        if save:
            save_rating(username, selected_movie.title, int(rating))
            st.session_state.user_notice = "Your rating has been saved."
            st.rerun()
    st.subheader("Your Saved Ratings")
    if ratings:
        st.dataframe(pd.DataFrame(ratings.items(), columns=["Movie", "Rating"]),
                     hide_index=True, width="stretch")
    else:
        st.info("You have not rated any movies yet.")
    with st.expander("Rating Change Log"):
        history = load_rating_history(username)
        if history:
            st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
        else:
            st.info("No rating changes have been recorded yet.")

    st.divider()
    st.header("My Viewing Journal")
    if movies.empty:
        st.info("Add a movie to the catalogue before recording a viewing.")
    else:
        with st.form("viewing_form"):
            watched_id = st.selectbox(
                "Which movie did you watch?", list(by_id),
                format_func=lambda key: by_id[key].display_label())
            record = st.form_submit_button("Record Viewing")
        st.caption("Each click records one separate viewing.")
        if record:
            save_viewing(username, by_id[watched_id].title)
            st.session_state.user_notice = "Your viewing has been recorded."
            st.rerun()
    if journal:
        st.dataframe(pd.DataFrame(journal).iloc[::-1],
                     hide_index=True, width="stretch")
    else:
        st.info("Your viewing journal is empty.")

    st.divider()
    st.header("Your Viewing Snapshot")
    if journal:
        frame = pd.DataFrame(journal)
        total, unique = st.columns(2)
        total.metric("Recorded Viewings", len(frame))
        unique.metric("Different Movies Watched", frame["Movie"].nunique())
        st.subheader("Your Most-Watched Movies")
        counts = frame["Movie"].value_counts().rename("Viewings").to_frame()
        st.bar_chart(counts)
    else:
        st.info("Record a viewing to see your activity summary.")
