# Cinema Compass
Sultan Juma Murad Abdulla Alblooshi — 0396550

A Python and Streamlit movie recommendation application.

## Run
Install the packages with:
    python -m pip install -r requirements.txt
Start the development app with:
    python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8502

Create an account, log in, and use the sidebar:
- Discover: literal title search, genre filtering, saved genre/year preferences,
  explained recommendations, and seven-day community trends.
- My Activity: current ratings, timestamped rating changes, viewing journal,
  repeated-viewing counts and personal charts.
- Catalogue Manager: an additional administrator key, add/edit/remove controls,
  all-time engagement totals and a seven-day daily chart.

## Administrator configuration
Create .streamlit/secrets.toml locally and set ADMIN_KEY to a private string.
Set the same variable in the hosted app's Secrets settings when deploying.
The real secrets file and cinema_compass.db are excluded from version control.

## Data and migration
SQLite stores accounts, preferences, rating events, viewing events and the movie
catalogue. The original movies.csv seeds the catalogue only when its table has
no records. Catalogue edits thereafter use SQLite. Removing a movie hides it
without deleting its history. Removed titles remain reserved. Renaming a movie
updates the prototype's title-based rating and viewing records in the same
transaction. Rating-history labels therefore show the current movie title.
Local records survive logout and a normal app restart on the same filesystem.
Community Cloud local files are not a durable production database; hosted
rebuilds or replacement instances can lose later user-created records. Use an
external database if durable hosted storage is required.

## Recommendation method
Movie, ViewerProfile and RecommendationService are in domain.py.
MovieCatalogue is in catalogue.py.
The scoring method is an explainable baseline, not a trained machine-learning
model. It uses genre and year constraints, mean genre feedback (rating minus
three), a viewing-history signal, and release-period similarity to rated
films. Seen/rated movies and removed catalogue entries are excluded.
An empty preferred-genre selection allows all genres within the year range.
Only positive final scores are returned, ordered by score, year and title.

## Checks
    python -m unittest -v test_core.py
The 23 backend tests cover account validation and hashing, user isolation,
saved preferences, rating changes, repeat viewing, recent-viewing bounds,
catalogue persistence/validation, rename rollback, history preservation,
empty catalogues, literal SQL characters, and recommendation behavior.
Backend tests passed during preparation on 27 October 2026.
The Streamlit interface and a public deployment still require user testing.
This source package is a development review update, not the final report.

## Deployment
Use app.py as the main file and install requirements.txt.
Configure ADMIN_KEY in the hosting platform rather than the repository.
Use only test data during the demonstration. Capture the successful add,
edit and removal messages, along with the user journeys and analytics.
