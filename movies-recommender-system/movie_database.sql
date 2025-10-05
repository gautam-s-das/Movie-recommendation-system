CREATE DATABASE movies_db;
USE movies_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(255) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);

-- Search history table
CREATE TABLE IF NOT EXISTS search_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    movie_id INT NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Genre search history table
CREATE TABLE IF NOT EXISTS genre_search_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    genre_name VARCHAR(255) NOT NULL,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

drop table genre_search_history;
select * from users;
select * from search_history;
select * from genre_search_history;
truncate table genre_search_history;



SELECT username, movie_id, COUNT(*) AS cnt
FROM search_history
GROUP BY username, movie_id
HAVING cnt > 1;



