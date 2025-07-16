import streamlit as st
import pickle as pkl
import pandas as pd
import requests
import time

# Setup requests session with retries
session = requests.Session()
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Function to fetch poster and year
def fetch_poster_and_year(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=3176ec361fc0532ffae0928e2f2dc5a0&language=en-US"
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        poster_path = data.get('poster_path')
        release_date = data.get('release_date', '')
        year = release_date.split("-")[0] if release_date else 'N/A'

        if poster_path:
            poster_url = "https://image.tmdb.org/t/p/w500/" + poster_path
        else:
            poster_url = "https://via.placeholder.com/500x750?text=No+Image"

        return poster_url, year
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for movie_id={movie_id}: {e}")
        return "https://via.placeholder.com/500x750?text=No+Image", 'N/A'

# Function to recommend movies
def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

    recommended_movies = []
    recommended_movie_posters = []

    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        poster_url, year = fetch_poster_and_year(movie_id)
        recommended_movies.append(movies.iloc[i[0]].title)
        recommended_movie_posters.append((poster_url, year))
        time.sleep(0.5)  # Avoid hitting API rate limits

    return recommended_movies, recommended_movie_posters

# Load data
movies_dist = pkl.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dist)
similarity = pkl.load(open('similarity.pkl', 'rb'))

# Streamlit UI
st.title('Movie Recommender System')
selected_movie_name = st.selectbox(
    'Select a movie to get recommendations:',
    movies['title'].values
)

if st.button('Recommend'):
    with st.spinner('Fetching recommendations...'):
        names, posters = recommend(selected_movie_name)

    # Create a responsive row layout with hover effect
    hover_css = """
        <style>
        .poster-container {
            transition: transform 0.3s ease;
            cursor: pointer;
        }
        .poster-container:hover {
            transform: scale(1.1);
            z-index: 10;
        }
        .poster-title {
            font-weight: bold;
            margin-top: 5px;
        }
        </style>
    """
    st.markdown(hover_css, unsafe_allow_html=True)

    cols = st.columns(5)
    for i in range(len(names)):
        with cols[i]:
            st.markdown(
                f"""
                <div class="poster-container">
                    <img src="{posters[i][0]}" width="100%" style="border-radius:10px"/>
                    <div class="poster-title">{names[i]} ({posters[i][1]})</div>
                </div>
                """,
                unsafe_allow_html=True
            )
