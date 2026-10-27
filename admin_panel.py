import hmac
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from storage import load_all_viewings


def configured_admin_key():
    try:
        value = st.secrets.get("ADMIN_KEY", "")
    except Exception:
        return ""
    return value if isinstance(value, str) else ""


def render_admin(catalogue):
    st.header("Catalogue Manager")
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False
    configured = configured_admin_key()
    if not configured:
        st.error("Administrator access is not configured.")
        return
    if not st.session_state.admin_unlocked:
        with st.form("admin_login_form"):
            entered = st.text_input("Administrator key", type="password")
            unlock = st.form_submit_button("Unlock Catalogue Manager")
        if unlock:
            if hmac.compare_digest(entered.encode("utf-8"), configured.encode("utf-8")):
                st.session_state.admin_unlocked = True
                st.rerun()
            st.error("Incorrect administrator key.")
        return

    st.success("Administrator access granted.")
    if st.button("Lock Catalogue Manager"):
        st.session_state.admin_unlocked = False
        st.rerun()
    notice = st.session_state.pop("admin_notice", None)
    if notice:
        st.success(notice)
    maximum_year = datetime.now(timezone.utc).year + 2
    add_tab, edit_tab, remove_tab, analytics_tab = st.tabs(
        ["Add Movie", "Edit Movie", "Remove Movie", "Engagement"])

    with add_tab:
        with st.form("add_movie_form", clear_on_submit=False):
            title = st.text_input("Movie title", max_chars=150)
            genre = st.selectbox("Genre", catalogue.GENRES)
            year = st.number_input("Release year", 1888, maximum_year,
                                   datetime.now(timezone.utc).year)
            add = st.form_submit_button("Add Movie")
        if add:
            try:
                catalogue.add_movie(title, genre, int(year))
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state.admin_notice = f'Movie added successfully: {title.strip()}.'
                st.rerun()

    available = catalogue.list_movies()
    by_id = {movie["id"]: movie for movie in available}
    def label(movie_id):
        movie = by_id[movie_id]
        return f'{movie["title"]} ({movie["year"]})'

    with edit_tab:
        if not available:
            st.info("The catalogue is empty. Add a movie first.")
        else:
            selected = st.selectbox("Select a movie to edit", list(by_id),
                                    format_func=label, key="edit_movie_choice")
            movie = by_id[selected]
            with st.form(f"edit_movie_form_{selected}"):
                changed_title = st.text_input("Updated title", movie["title"], max_chars=150)
                changed_genre = st.selectbox("Updated genre", catalogue.GENRES,
                    index=catalogue.GENRES.index(movie["genre"]))
                changed_year = st.number_input("Updated release year", 1888,
                                               maximum_year, int(movie["year"]))
                edit = st.form_submit_button("Save Movie Changes")
            if edit:
                try:
                    catalogue.edit_movie(selected, changed_title, changed_genre,
                                         int(changed_year))
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state.admin_notice = (
                        f'Movie updated successfully: {changed_title.strip()}.')
                    st.rerun()

    with remove_tab:
        if not available:
            st.info("There are no movies to remove.")
        else:
            selected_remove = st.selectbox("Select a movie to remove", list(by_id),
                                          format_func=label, key="remove_movie_choice")
            st.caption("Removal hides the movie from the catalogue. Viewing and rating records are retained.")
            with st.form(f"remove_movie_form_{selected_remove}"):
                confirmed = st.checkbox("I confirm removal of this movie.")
                remove = st.form_submit_button("Remove Movie")
            if remove:
                if not confirmed:
                    st.warning("Confirm the removal first.")
                else:
                    try:
                        catalogue.remove_movie(selected_remove)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.session_state.admin_notice = (
                            f'Movie removed successfully: {by_id[selected_remove]["title"]}.')
                        st.rerun()

    with analytics_tab:
        st.subheader("Community Engagement")
        events = load_all_viewings()
        if not events:
            st.info("No viewings have been recorded yet.")
        else:
            frame = pd.DataFrame(events)
            total, unique = st.columns(2)
            total.metric("Total Recorded Viewings", len(frame))
            unique.metric("Unique Viewers", frame["User"].nunique())
            st.caption("All-time counts include movies removed from the catalogue.")
            counts = frame["Movie"].value_counts().rename_axis("Movie").to_frame("Viewings")
            st.subheader("Most-Watched Movies")
            st.bar_chart(counts.head(10))
            st.dataframe(counts.reset_index(), hide_index=True, width="stretch")
            st.subheader("Daily Viewings in the Last 7 Days")
            times = pd.to_datetime(frame["Watched At (UTC)"], utc=True)
            today = pd.Timestamp.now(tz="UTC").normalize()
            dates = pd.date_range(today - pd.Timedelta(days=6), today, freq="D")
            daily = times.dt.normalize().value_counts().reindex(dates, fill_value=0)
            st.bar_chart(daily.rename("Viewings").to_frame())
            st.caption("Calendar dates use UTC; missing days have a count of zero.")
