import streamlit as st
import pickle as pkl
import pandas as pd
import requests
import time
import os
from typing import Tuple, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup requests session with enhanced retries
session = requests.Session()
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Enhanced retry strategy
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
API_KEY = "3176ec361fc0532ffae0928e2f2dc5a0"  # Consider using environment variable
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/500x750/gray/white?text=No+Image+Available"
REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 0.75  # Increased delay to avoid rate limits

def fetch_poster_and_year(movie_id: int, max_retries: int = 3) -> Tuple[str, str]:
    """
    Fetch movie poster and release year from TMDb API with enhanced error handling.
    
    Args:
        movie_id: TMDb movie ID
        max_retries: Maximum number of retry attempts
        
    Returns:
        Tuple of (poster_url, year)
    """
    if not movie_id or movie_id <= 0:
        logger.warning(f"Invalid movie_id: {movie_id}")
        return PLACEHOLDER_IMAGE, 'N/A'
    
    url = f"{BASE_URL}/movie/{movie_id}"
    params = {
        'api_key': API_KEY,
        'language': 'en-US'
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching data for movie_id={movie_id}, attempt {attempt + 1}")
            
            response = session.get(
                url, 
                params=params, 
                timeout=REQUEST_TIMEOUT,
                headers={
                    'User-Agent': 'MovieRecommenderApp/1.0',
                    'Accept': 'application/json'
                }
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Validate response content
            if not response.content:
                logger.error(f"Empty response for movie_id={movie_id}")
                continue
                
            data = response.json()
            
            # Validate JSON structure
            if not isinstance(data, dict):
                logger.error(f"Invalid JSON structure for movie_id={movie_id}")
                continue
            
            # Extract poster path
            poster_path = data.get('poster_path')
            if poster_path and poster_path.strip():
                poster_url = f"{IMAGE_BASE_URL}{poster_path}"
                logger.info(f"Successfully fetched poster for movie_id={movie_id}")
            else:
                logger.warning(f"No poster available for movie_id={movie_id}")
                poster_url = PLACEHOLDER_IMAGE
            
            # Extract release year
            release_date = data.get('release_date', '')
            if release_date and len(release_date) >= 4:
                year = release_date.split("-")[0]
            else:
                year = 'N/A'
            
            return poster_url, year
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error for movie_id={movie_id}, attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'Unknown'
            logger.error(f"HTTP error {status_code} for movie_id={movie_id}, attempt {attempt + 1}")
            
            if status_code == 429:  # Rate limit
                time.sleep(5)  # Wait longer for rate limit
            elif status_code == 404:  # Movie not found
                logger.warning(f"Movie not found for movie_id={movie_id}")
                break
            elif attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for movie_id={movie_id}, attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for movie_id={movie_id}: {e}, attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except ValueError as e:
            logger.error(f"JSON decode error for movie_id={movie_id}: {e}")
            break
            
        except Exception as e:
            logger.error(f"Unexpected error for movie_id={movie_id}: {e}")
            break
    
    logger.warning(f"Failed to fetch data for movie_id={movie_id} after {max_retries} attempts")
    return PLACEHOLDER_IMAGE, 'N/A'

def recommend(movie: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Recommend movies based on similarity scores.
    
    Args:
        movie: Selected movie title
        
    Returns:
        Tuple of (movie_names, poster_data)
    """
    try:
        movie_index = movies[movies['title'] == movie].index[0]
    except IndexError:
        logger.error(f"Movie '{movie}' not found in dataset")
        return [], []
    
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

    recommended_movies = []
    recommended_movie_posters = []

    for i, (idx, similarity_score) in enumerate(movies_list):
        try:
            movie_id = movies.iloc[idx].movie_id
            movie_title = movies.iloc[idx].title
            
            logger.info(f"Processing recommendation {i+1}/5: {movie_title}")
            
            poster_url, year = fetch_poster_and_year(movie_id)
            recommended_movies.append(movie_title)
            recommended_movie_posters.append((poster_url, year))
            
            # Rate limiting between requests
            if i < len(movies_list) - 1:  # Don't sleep after the last request
                time.sleep(RATE_LIMIT_DELAY)
                
        except Exception as e:
            logger.error(f"Error processing recommendation {i+1}: {e}")
            # Continue with placeholder data
            recommended_movies.append(f"Movie {i+1}")
            recommended_movie_posters.append((PLACEHOLDER_IMAGE, 'N/A'))

    return recommended_movies, recommended_movie_posters

# Load data with error handling
@st.cache_data
def load_data():
    """Load movie data and similarity matrix with error handling."""
    try:
        movies_dist = pkl.load(open('movies_dict.pkl', 'rb'))
        movies = pd.DataFrame(movies_dist)
        similarity = pkl.load(open('similarity.pkl', 'rb'))
        
        # Validate data
        if movies.empty or similarity.size == 0:
            raise ValueError("Loaded data is empty")
            
        logger.info(f"Successfully loaded {len(movies)} movies")
        return movies, similarity
        
    except FileNotFoundError as e:
        st.error(f"Data files not found: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

# Load data
movies, similarity = load_data()

# Streamlit UI
st.title('🎬 Movie Recommender System')
st.markdown("---")

# Movie selection
selected_movie_name = st.selectbox(
    'Select a movie to get recommendations:',
    movies['title'].values,
    help="Choose a movie from the dropdown to get 5 similar movie recommendations"
)

# Display selected movie info
if selected_movie_name:
    selected_movie_info = movies[movies['title'] == selected_movie_name].iloc[0]
    st.info(f"Selected: **{selected_movie_name}**")

# Recommendation button
if st.button('🔍 Get Recommendations', type="primary"):
    if not selected_movie_name:
        st.warning("Please select a movie first!")
    else:
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text('Analyzing movie similarities...')
            progress_bar.progress(20)
            
            names, posters = recommend(selected_movie_name)
            
            if not names:
                st.error("No recommendations found. Please try a different movie.")
            else:
                status_text.text('Fetching movie posters...')
                progress_bar.progress(80)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"Found {len(names)} recommendations for '{selected_movie_name}'")
                
                # Enhanced CSS for better UI
                enhanced_css = """
                    <style>
                    .poster-container {
                        transition: all 0.3s ease;
                        cursor: pointer;
                        border-radius: 10px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        margin-bottom: 15px;
                    }
                    .poster-container:hover {
                        transform: scale(1.05);
                        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
                        z-index: 10;
                    }
                    .poster-title {
                        font-weight: bold;
                        margin-top: 8px;
                        font-size: 14px;
                        text-align: center;
                        color: #333;
                        line-height: 1.3;
                    }
                    .poster-image {
                        width: 100%;
                        height: auto;
                        border-radius: 8px;
                    }
                    </style>
                """
                st.markdown(enhanced_css, unsafe_allow_html=True)

                # Display recommendations in columns
                cols = st.columns(5)
                for i in range(len(names)):
                    with cols[i]:
                        st.markdown(
                            f"""
                            <div class="poster-container">
                                <img src="{posters[i][0]}" class="poster-image" alt="{names[i]}" onerror="this.src='{PLACEHOLDER_IMAGE}'"/>
                                <div class="poster-title">{names[i]}<br>({posters[i][1]})</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"An error occurred while generating recommendations: {str(e)}")
            logger.error(f"Recommendation error: {e}")

# Footer
st.markdown("---")
st.markdown("*Powered by The Movie Database (TMDb) API*")