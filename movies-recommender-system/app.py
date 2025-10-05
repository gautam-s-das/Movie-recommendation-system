import streamlit as st
import pickle as pkl
import pandas as pd
import requests
import time
import os
import json
from typing import Tuple, List
import logging
import db_auth
import datetime



# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# set app config
st.set_page_config(page_title="TMDB", page_icon="🍿", layout="wide")    
st.markdown(f"""
            <style>
            
            .stApp {{background-image: url(""); 
                     background-attachment: fixed;
                     base: light;
                     background-size: cover}}
            
         </style>
         """, unsafe_allow_html=True)
#  Custom CSS for hover + transitions
st.markdown("""
<style>
.poster-container {
    transition: all 0.3s ease;
    cursor: pointer;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 15px;
}
.poster-container:hover {
    transform: scale(1.05);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.25);
    z-index: 10;
}
.poster-title {
    font-weight: bold;
    margin-top: 8px;
    font-size: 14px;
    text-align: center;
    color: white;
    line-height: 1.3;
}
.poster-image {
    width: 100%;
    height: auto;
    border-radius: 10px;
    transition: transform 0.3s ease-in-out;
}
</style>
""", unsafe_allow_html=True)


# App Layout
st.image("images/applogo1.png")
st.title("Movie Finder 🍿 🤖")

# Setup requests session with retries
session = requests.Session()
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    respect_retry_after_header=True
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Configuration
API_KEY = os.getenv("TMDB_API_KEY", "3176ec361fc0532ffae0928e2f2dc5a0")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/500x750/gray/white?text=No+Image+Available"
REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 0.75

# Poster cache file
POSTER_CACHE_FILE = 'poster_cache.json'

def load_poster_cache() -> dict:
    if os.path.exists(POSTER_CACHE_FILE):
        try:
            with open(POSTER_CACHE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_poster_cache():
    try:
        with open(POSTER_CACHE_FILE, 'w') as f:
            json.dump(poster_cache, f)
    except Exception as e:
        logger.error(f"Failed to save poster cache: {e}")

poster_cache = load_poster_cache()

def fetch_movie_data(movie_id: int, max_retries: int = 3) -> Tuple[str, str, str, List[str], str, int, float]:
    if not movie_id or movie_id <= 0:
        return PLACEHOLDER_IMAGE, 'N/A', 'No overview available.', [], 'N/A', 0, 0.0

    if str(movie_id) in poster_cache:
        cached = poster_cache[str(movie_id)]
        if len(cached) == 7:
            return tuple(cached)

    url = f"{BASE_URL}/movie/{movie_id}"
    params = {'api_key': API_KEY, 'language': 'en-US'}

    for attempt in range(max_retries):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            poster_path = data.get('poster_path')
            poster_url = f"{IMAGE_BASE_URL}{poster_path}" if poster_path else PLACEHOLDER_IMAGE

            release_date = data.get('release_date', 'N/A')
            year = release_date.split("-")[0] if release_date and len(release_date) >= 4 else 'N/A'

            overview = data.get('overview', 'No overview available.').replace('"', "'").strip()

            genres_data = data.get('genres', [])
            genres = [genre['name'] for genre in genres_data]
            
            runtime = data.get('runtime', 0)  # minutes
            vote_avg = data.get('vote_average', 0.0)  # rating

            # cache full 7-tuple
            poster_cache[str(movie_id)] = (poster_url, year, overview, genres, release_date, runtime, vote_avg)
            save_poster_cache()

            return poster_url, year, overview, genres, release_date, runtime, vote_avg

        except Exception as e:
            logger.error(f"Failed to fetch movie data for {movie_id}: {e}")

    # fallback (7 values)
    return PLACEHOLDER_IMAGE, 'N/A', 'No overview available.', [], 'N/A', 0, 0.0

def get_movie_index(movie: str):
    # Case-insensitive search
    matches = movies[movies['title'].str.lower().str.contains(movie.lower())]
    if matches.empty:
        return None

    # Prefer exact match
    exact_match = matches[matches['title'].str.lower() == movie.lower()]
    if not exact_match.empty:
        return exact_match.index[0]

    # Special handling for Avatar (2009)
    if movie.lower() == "avatar":
        avatar_2009 = matches[matches['title'].str.contains("Avatar", case=False) & matches['title'].str.contains("2009", case=False)]
        if not avatar_2009.empty:
            return avatar_2009.index[0]

    # Otherwise, return the first match
    return matches.index[0]


def recommend(movie: str) -> Tuple[List[str], List[Tuple[str, str, str, List[str]]]]:
    movie_index = get_movie_index(movie)
    if movie_index is None:
        return [], []
    # try:
    #     movie_index = movies[movies['title'] == movie].index[0]
    # except IndexError:
    #     return [], []

    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[0:5]

    recommended_movies = []
    recommended_movie_data = []

    for i in range(len(movies_list)):
        try:
            idx = movies_list[i][0]
            movie_id = movies.iloc[idx].movie_id
            movie_title = movies.iloc[idx].title

            poster_url, year, overview, genres,release_date, runtime, vote_avg = fetch_movie_data(movie_id)
            recommended_movies.append(movie_title)
            recommended_movie_data.append((poster_url, year, overview, genres,release_date, runtime, vote_avg))

            if i < len(movies_list) - 1:
                time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            logger.error(f"Error processing recommendation {i + 1}: {e}")
            recommended_movies.append(f"Movie {i + 1}")
            recommended_movie_data.append((PLACEHOLDER_IMAGE, 'N/A', 'No overview available.', []))

    return recommended_movies, recommended_movie_data

@st.cache_resource(ttl=3600)
def load_data():
    try:
        movies_dist = pkl.load(open('movies_dict.pkl', 'rb'))
        movies = pd.DataFrame(movies_dist)
        similarity = pkl.load(open('similarity.pkl', 'rb'))
        return movies, similarity
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

movies, similarity = load_data()

# Fetch available genres from TMDB
@st.cache_data(ttl=86400)
def fetch_genres():
    url = f"{BASE_URL}/genre/movie/list"
    params = {'api_key': API_KEY, 'language': 'en-US'}
    try:
        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        data = res.json()
        return {g['name']: g['id'] for g in data.get('genres', [])}
    except Exception as e:
        st.error(f"Failed to fetch genres: {e}")
        return {}
    
# ----------------- User Authentication -----------------
db_auth.init_db()  # make sure DB & table exist

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    db_auth.auth_ui()
    st.stop()
else:
    st.sidebar.success(f"👋 Welcome, {st.session_state['username']}!")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()
        
# ----------------- Movie Recommender System -----------------
st.subheader("🕒 Your Recent Searches")

recent_searches = db_auth.get_recent_searches(st.session_state["username"], limit=5)

if recent_searches:
    if len(recent_searches) == 1:
        # ✅ Single poster → fixed size 200x400
        movie_title, searched_at, movie_id = recent_searches[0]
        poster_url, year, overview, genres, release_date, runtime, vote_avg = fetch_movie_data(movie_id)

        st.markdown(
            f"""
            <div class="poster-container">
                <img src="{poster_url}" 
                     alt="{movie_title}" 
                     onerror="this.src='{PLACEHOLDER_IMAGE}'"" />
                <div class="poster-title">{movie_title}<br>({year})</div>
                <small style="color: gray;">{searched_at}</small>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("Get Recs", key="recent_single"):
            st.session_state["movie_select"] = movie_title
            st.rerun()

    else:
        # ✅ Multiple posters → responsive columns
        cols = st.columns(len(recent_searches))
        for i, (movie_title, searched_at, movie_id) in enumerate(recent_searches):
            poster_url, year, overview, genres, release_date, runtime, vote_avg = fetch_movie_data(movie_id)

            with cols[i]:
                st.markdown(
                    f"""
                    <div class="poster-container">
                        <img src="{poster_url}" class="poster-image" alt="{movie_title}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                        <div class="poster-title">{movie_title}<br>({year})</div>
                        <small style="color: gray;">{searched_at}</small>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        if st.button("Get Recs", key=f"recent_{i}"):
            st.session_state["movie_select"] = movie_title
            st.rerun()
else:
    st.info("No recent searches yet. Start searching movies!")



st.title('🎬 Movie Recommender System')
st.markdown("---")

st.subheader("🎯 Find by Movie Name")
selected_movie_name = st.selectbox(
    'Select a movie to get recommendations:',
    movies['title'].values,
    key="movie_select"  # Unique key
)

# ✅ Initialize session state
if "selected_movie" not in st.session_state:
    st.session_state.selected_movie = None
if "recommendations" not in st.session_state:
    st.session_state.recommendations = None
    

# --- Fetch recommendations when button is clicked ---
if st.button('🔍 Get Recommendations', type="primary", key="get_recs"):
    if not selected_movie_name:
        st.warning("Please select a movie first!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text('Analyzing movie similarities...')
            progress_bar.progress(20)
            
            names, movie_data = recommend(selected_movie_name)
           
            
            if not names:
                st.error("No recommendations found. Please try a different movie.")
            else:
                status_text.text('Fetching movie posters and details...')
                progress_bar.progress(80)
                progress_bar.empty()
                status_text.empty()

                st.success(f"Found {len(names)} recommendations for '{selected_movie_name}'")
                 # ✅ Compute movie_id for the selected title and save the search
                try:
                    movie_index = get_movie_index(selected_movie_name)
                    movie_id = int(movies.iloc[movie_index].movie_id) if movie_index is not None else None
                except Exception:
                    movie_id = None

                if movie_id is not None:
                    # For MySQL version of db_auth.add_search(username, movie_id, movie_title)
                    db_auth.add_search(st.session_state["username"], movie_id, selected_movie_name)
                else:
                    # Optional: avoid breaking the app if we can't resolve the ID
                    st.warning("Couldn’t resolve a TMDB movie_id for this title, so it wasn’t saved to history.")
                
                # ✅ Save in session_state so it persists after rerun
                st.session_state.recommendations = (names, movie_data)
                st.session_state.selected_movie = None
                # ✅ Save search history
                db_auth.add_search(st.session_state["username"],movie_id, selected_movie_name)

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"An error occurred while generating recommendations: {str(e)}")
            logger.error(f"Recommendation error: {e}")

# ----------------- Year-Based Search Section -----------------
st.subheader("📅 Find Top Movies by Year")

# Create dropdown for year selection
current_year = datetime.datetime.now().year
selected_year = st.selectbox(
    "Select a year to view top movies:",
    list(range(current_year, 1979, -1)),  # From current year down to 1980
    index=0
)

# Function to fetch top movies by year
def fetch_top_movies_by_year(year: int, count: int = 5):
    url = f"{BASE_URL}/discover/movie"
    params = {
        "api_key": API_KEY,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "primary_release_year": year,
        "page": 1
    }
    try:
        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])[:count]

        movies_list = []
        movie_data = []

        for m in results:
            movie_id = m.get("id")
            title = m.get("title", "Untitled")
            poster_url, year, overview, genres, release_date, runtime, vote_avg = fetch_movie_data(movie_id)

            movies_list.append(title)
            movie_data.append((poster_url, year, overview, genres, release_date, runtime, vote_avg))
            time.sleep(RATE_LIMIT_DELAY)

        return movies_list, movie_data

    except Exception as e:
        st.error(f"Failed to fetch movies for {year}: {e}")
        return [], []

# Initialize session state
if "year_recommendations" not in st.session_state:
    st.session_state.year_recommendations = None
if "selected_year_movie" not in st.session_state:
    st.session_state.selected_year_movie = None

# Fetch button
if st.button("🎞️ Show Top Movies", type="primary", key="year_button"):
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text(f"Fetching top movies from {selected_year}...")
        progress_bar.progress(40)
        names, movie_data = fetch_top_movies_by_year(selected_year)

        if not names:
            st.warning(f"No movies found for {selected_year}.")
        else:
            status_text.text("Fetching movie details...")
            progress_bar.progress(80)
            progress_bar.empty()
            status_text.empty()

            st.success(f"Top {len(names)} movies from {selected_year}:")
            st.session_state.year_recommendations = (names, movie_data)
            st.session_state.selected_year_movie = None

    except Exception as e:
        st.error(f"Error fetching top movies: {str(e)}")
        logger.error(f"Year fetch error: {e}")
        progress_bar.empty()
        status_text.empty()

# Display fetched movies
if st.session_state.year_recommendations:
    names, movie_data = st.session_state.year_recommendations

    if st.session_state.selected_year_movie is None:
        cols = st.columns(5)
        for i in range(len(names)):
            poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[i]
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="poster-container">
                        <img src="{poster_url}" class="poster-image" alt="{names[i]}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                        <div class="poster-title">{names[i]}<br>({year})</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("See details", key=f"year_see_details_{i}"):
                    st.session_state.selected_year_movie = i
                    st.rerun()
    else:
        idx = st.session_state.selected_year_movie
        poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[idx]

        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(poster_url, width=250)
        with col2:
            st.markdown(f"## 🎬 {names[idx]} ({year})")
            st.write(f"**Release Date:** {release_date}")
            st.write(f"**Runtime:** {runtime} min")
            st.write(f"**Vote Average:** ⭐ {vote_avg}/10")
            st.write(f"**Genres:** {', '.join(genres) if genres else 'Not available'}")
            st.write(overview)

        if st.button("⬅️ Back to Year Results", key="back_year_button"):
            st.session_state.selected_year_movie = None
            st.rerun()

# --- Render recommendations (grid or details) ---
if st.session_state.recommendations:
    names, movie_data = st.session_state.recommendations

    # Show poster grid if no movie is selected yet
    if st.session_state.selected_movie is None:
        cols = st.columns(5)
        for i in range(len(names)):
            poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[i]
            movie_title = names[i]

            with cols[i]:
                st.markdown(
                f"""
                <div class="poster-container">
                    <img src="{poster_url}" class="poster-image" alt="{movie_title}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                </div>
                """,
                unsafe_allow_html=True
                )
                if st.button("See details", key=f"see_details_{i}"):
                    st.session_state.selected_movie = i
                    st.rerun()

    # Show details of selected movie
    else:
        # Create two columns
        col1, col2 = st.columns([1, 2]) # Adjust width ratio      
        idx = st.session_state.selected_movie
        poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[idx]
        
        with col1:
            st.image(poster_url, width=250)
        with col2:
            st.markdown(f"## 🎬 {names[idx]} ({year})")
            st.write(f"**Release Date:** {release_date}")
            st.write(f"**Runtime:** {runtime} min")
            st.write(f"**Vote Average:** ⭐ {vote_avg}/10")
            st.write(f"**Genres:** {', '.join(genres) if genres else 'Not available'}")
            st.write(overview)

        if st.button("⬅️ Back to recommendations", key="back_button"):
            st.session_state.selected_movie = None
            st.rerun()
            
# ----------------- End of Movie Recommender System -----------------
genres_dict = fetch_genres()

def recommend_by_genre(selected_genres_ids: list):
    if not selected_genres_ids:
        return [], []

    url = f"{BASE_URL}/discover/movie"
    params = {
        'api_key': API_KEY,
        'language': 'en-US',
        'sort_by': 'popularity.desc',
        'with_genres': ",".join(map(str, selected_genres_ids)),
        'page': 1
    }
    try:
        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        data = res.json()
        movies_data = data.get('results', [])[:5]

        recommended_movies = []
        recommended_movie_data = []
        for m in movies_data:
            movie_id = m.get("id")
            movie_title = m.get("title", "Untitled")

            # ✅ Fetch full details
            poster_url, year, overview, genres, release_date, runtime, vote_avg = fetch_movie_data(movie_id)

            recommended_movies.append(movie_title)
            recommended_movie_data.append((poster_url, year, overview, genres, release_date, runtime, vote_avg))

            time.sleep(RATE_LIMIT_DELAY)

        return recommended_movies, recommended_movie_data

    except Exception as e:
        st.error(f"Failed to fetch movies by genre: {e}")
        return [], []
    
def fetch_genre_poster(genre_name: str):
    """Fetch a representative poster for a genre using TMDB discover endpoint."""
    try:
        genre_id = genres_dict.get(genre_name)
        if not genre_id:
            return PLACEHOLDER_IMAGE, "N/A"

        url = f"{BASE_URL}/discover/movie"
        params = {
            'api_key': API_KEY,
            'language': 'en-US',
            'sort_by': 'popularity.desc',
            'with_genres': genre_id,
            'page': 1
        }

        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        data = res.json()
        results = data.get('results', [])

        if results:
            m = results[0]  # pick the most popular movie
            poster_url = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get('poster_path') else PLACEHOLDER_IMAGE
            year = m.get("release_date", "N/A").split("-")[0] if m.get("release_date") else "N/A"
            return poster_url, year

        return PLACEHOLDER_IMAGE, "N/A"

    except Exception as e:
        logger.error(f"Error fetching genre poster for {genre_name}: {e}")
        return PLACEHOLDER_IMAGE, "N/A"


# ----------------- Recent Genre Searches -----------------
st.subheader("🕒 Your Recent Genre Searches")

recent_genre_searches = db_auth.get_recent_genre_searches(st.session_state["username"], limit=5)

if recent_genre_searches:
    cols = st.columns(len(recent_genre_searches))
    for i, (genre_name, searched_at) in enumerate(recent_genre_searches):
        poster_url, year = fetch_genre_poster(genre_name)

        with cols[i]:
            st.markdown(
                f"""
                <div class="poster-container">
                    <img src="{poster_url}" class="poster-image" alt="{genre_name}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                    <div class="poster-title">{genre_name}<br>({year})</div>
                    <small style="color: gray;">{searched_at}</small>
                </div>
                """,
                unsafe_allow_html=True
            )
    if st.button("Get Genre Recs", key=f"recent_genre_{i}"):
        st.session_state["selected_genres"] = [genre_name]
        st.rerun()
else:
    st.info("No recent genre searches yet. Try searching by genre!")




# ----------------- Genre Search Section -----------------

st.subheader("🎯 Or Find by Genre(s)")
selected_genres = st.multiselect(
    "Select one or more genres:",
    list(genres_dict.keys()),
    key="genre_multiselect"
)

# ✅ Initialize session state
if "selected_genre_movie" not in st.session_state:
    st.session_state.selected_genre_movie = None
if "genre_recommendations" not in st.session_state:
    st.session_state.genre_recommendations = None
    
# Save genre searches
for g in selected_genres:
    db_auth.add_genre_search(st.session_state["username"], g)


# --- Genre Recommendation Button ---
if st.button('🎬 Get Recommendations by Genre(s)', type="primary", key="genre_button"):
    if not selected_genres:
        st.warning("Please select at least one genre!")
    else:
        selected_genre_ids = [genres_dict[g] for g in selected_genres]
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text('Finding popular movies in selected genres...')
            progress_bar.progress(20)
            names, movie_data = recommend_by_genre(selected_genre_ids)

            if not names:
                st.error("No movies found for selected genres.")
            else:
                status_text.text('Fetching posters and details...')
                progress_bar.progress(80)
                progress_bar.empty()
                status_text.empty()

                st.success(f"Found {len(names)} recommendations for genres: {', '.join(selected_genres)}")

                # ✅ Save results in session state
                st.session_state.genre_recommendations = (names, movie_data)
                st.session_state.selected_genre_movie = None

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"An error occurred while fetching genre recommendations: {str(e)}")
            logger.error(f"Genre recommendation error: {e}")

# --- Render genre recommendations (grid or details) ---
if st.session_state.genre_recommendations:
    names, movie_data = st.session_state.genre_recommendations

    # Show poster grid
    if st.session_state.selected_genre_movie is None:
        cols = st.columns(5)
        for i in range(len(names)):
            poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[i]
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="poster-container">
                        <img src="{poster_url}" class="poster-image" alt="{names[i]}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                        <div class="poster-title">{names[i]}<br>({year})</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("See details", key=f"genre_see_details_{i}"):
                    st.session_state.selected_genre_movie = i
                    st.rerun()

    # Show detail view
    else:
        idx = st.session_state.selected_genre_movie
        poster_url, year, overview, genres, release_date, runtime, vote_avg = movie_data[idx]

        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(poster_url, width=250)
        with col2:
            st.markdown(f"## 🎬 {names[idx]} ({year})")
            st.write(f"**Release Date:** {release_date}")
            st.write(f"**Runtime:** {runtime} min")
            st.write(f"**Vote Average:** ⭐ {vote_avg}/10")
            st.write(f"**Genres:** {', '.join(genres) if genres else 'Not available'}")
            st.write(overview)

        if st.button("⬅️ Back to genre results", key="back_genre_button"):
            st.session_state.selected_genre_movie = None
            st.rerun()
# ----------------- End of Genre Search Section -----------------
              




