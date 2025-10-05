import streamlit as st
import mysql.connector
import bcrypt

# --- MySQL Connection Helper ---
def get_connection():
    return mysql.connector.connect(
        host="localhost",        # your MySQL host
        user="root",             # your MySQL username
        password="1234", # your MySQL password
        database="movies_db"     # your MySQL database
    )

# --- Initialize Tables ---
def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(255) PRIMARY KEY,
            password VARCHAR(255) NOT NULL
        )
    """)

    # Create search history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            movie_id INT NOT NULL,
            movie_title VARCHAR(255) NOT NULL,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# --- Add new user (Signup) ---
def add_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
        conn.commit()
        return True
    except mysql.connector.IntegrityError:  # username already exists
        return False
    finally:
        conn.close()

# --- Check user (Login) ---
def check_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = %s", (username,))
    row = c.fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row[0].encode()):
        return True
    return False

# --- Authentication UI ---
def auth_ui():
    st.title("🔑 User Authentication")

    choice = st.radio("Choose action", ["Login", "Signup"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if choice == "Signup":
        if st.button("Sign Up"):
            if add_user(username, password):
                st.success("✅ Signup successful! Please login.")
            else:
                st.error("⚠️ Username already exists!")

    elif choice == "Login":
        if st.button("Login"):
            if check_user(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("🎉 Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

# --- Save search history ---
def add_search(username, movie_id, movie_title):
    conn = get_connection()
    c = conn.cursor()

    # Check if this user already searched for this movie
    c.execute(
        "SELECT id FROM search_history WHERE username = %s AND movie_id = %s",
        (username, movie_id)
    )
    row = c.fetchone()

    if row:
        # Update timestamp if it exists
        c.execute(
            "UPDATE search_history SET searched_at = CURRENT_TIMESTAMP WHERE id = %s",
            (row[0],)
        )
    else:
        # Insert new search record
        c.execute(
            "INSERT INTO search_history (username, movie_id, movie_title) VALUES (%s, %s, %s)",
            (username, movie_id, movie_title)
        )

    conn.commit()
    conn.close()


# --- Fetch recent searches ---
def get_recent_searches(username, limit=5):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT movie_title, searched_at, movie_id
        FROM search_history
        WHERE username = %s
        ORDER BY searched_at DESC
        LIMIT %s
    """, (username, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# --- Add a genre search ---
def add_genre_search(username, genre_name):
    conn = get_connection()
    c = conn.cursor()

    # Check if this user already searched for this genre
    c.execute(
        "SELECT id FROM genre_search_history WHERE username = %s AND genre_name = %s",
        (username, genre_name)
    )
    row = c.fetchone()

    if row:
        # Update timestamp if it exists
        c.execute(
            "UPDATE genre_search_history SET searched_at = CURRENT_TIMESTAMP WHERE id = %s",
            (row[0],)
        )
    else:
        # Insert new search record
        c.execute(
            "INSERT INTO genre_search_history (username, genre_name) VALUES (%s, %s)",
            (username, genre_name)
        )

    conn.commit()
    conn.close()


# --- Fetch recent genre searches ---
def get_recent_genre_searches(username, limit=5):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT genre_name, searched_at
        FROM genre_search_history
        WHERE username = %s
        ORDER BY searched_at DESC
        LIMIT %s
    """, (username, limit))
    rows = c.fetchall()
    conn.close()
    return rows


