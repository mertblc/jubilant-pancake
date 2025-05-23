-- Drop and create database
DROP DATABASE IF EXISTS chessdb;
CREATE DATABASE chessdb;
USE chessdb;
-- Certification Types Table (Shared by coach and arbiter)
CREATE TABLE coach_certification_types (
    certification_id INT AUTO_INCREMENT PRIMARY KEY,
    certification_name VARCHAR(100) NOT NULL UNIQUE
);

-- Insert initial certification types
INSERT INTO coach_certification_types (certification_name) VALUES 
    ('National Level'),
    ('FIDE Certified'),
    ('Regional Certified'),
    ('Club Level');
    
CREATE TABLE arbiter_certification_types (
    certification_id INT AUTO_INCREMENT PRIMARY KEY,
    certification_name VARCHAR(100) NOT NULL UNIQUE
);

-- Insert initial certification types
INSERT INTO arbiter_certification_types (certification_name) VALUES 
    ('National Arbiter'),
    ('FIDE Certified'),
    ('Regional Certification'),
    ('International Arbiter'),
    ('Local Certification');
-- 1. BASE TABLES (No foreign key dependencies)
-- Users table (base table for all user types)
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('player', 'coach', 'arbiter', 'manager') NOT NULL
);

-- Titles table (referenced by players)
CREATE TABLE titles (
    title_id VARCHAR(10) PRIMARY KEY,
    title_name VARCHAR(100) NOT NULL
);

-- Sponsors table (referenced by teams)
CREATE TABLE sponsors (
    sponsor_id INT AUTO_INCREMENT PRIMARY KEY,
    sponsor_name VARCHAR(100) UNIQUE NOT NULL
);

-- 2. USER PROFILE TABLES (Depend on users table)
-- Players table
CREATE TABLE players (
    user_id INT PRIMARY KEY,
    name VARCHAR(100),
    surname VARCHAR(100),
    nationality VARCHAR(50),
    date_of_birth DATE ,
    fide_id VARCHAR(20) UNIQUE,
    elo_rating INT,
    title_id VARCHAR(10),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (title_id) REFERENCES titles(title_id),
    CHECK (elo_rating >= 1000)
);

-- Coaches table
CREATE TABLE coaches (
    user_id INT PRIMARY KEY,
    name VARCHAR(100),
    surname VARCHAR(100),
    nationality VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Arbiters table
CREATE TABLE arbiters (
    user_id INT PRIMARY KEY,
    name VARCHAR(100),
    surname VARCHAR(100),
    nationality VARCHAR(50),
    experience_level VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 3. VENUE TABLES (No dependencies on user tables)
-- Halls table
CREATE TABLE halls (
    hall_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50),
    capacity INT
);

-- Tables table
CREATE TABLE tables (
    table_id INT AUTO_INCREMENT PRIMARY KEY,
    hall_id INT NOT NULL,
    table_number INT NOT NULL,
    FOREIGN KEY (hall_id) REFERENCES halls(hall_id),
    UNIQUE(hall_id, table_number)
);

-- 4. TEAM AND MEMBERSHIP TABLES
-- Teams table
CREATE TABLE teams (
    team_id INT AUTO_INCREMENT PRIMARY KEY,
    sponsor_id INT,
    name VARCHAR(100) NOT NULL,
    FOREIGN KEY (sponsor_id) REFERENCES sponsors(sponsor_id)
);

-- Player team membership
CREATE TABLE player_team_membership (
    player_id INT NOT NULL,
    team_id INT NOT NULL,
    PRIMARY KEY(player_id, team_id),
    FOREIGN KEY (player_id) REFERENCES players(user_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- Coach contracts
CREATE TABLE contracts (
    contract_id INT AUTO_INCREMENT PRIMARY KEY,
    coach_id INT NOT NULL,
    team_id INT NOT NULL,
    contract_start DATE NOT NULL,
    contract_finish DATE NOT NULL,
    FOREIGN KEY (coach_id) REFERENCES coaches(user_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

-- 5. CERTIFICATION TABLES
-- Coach certifications
CREATE TABLE coach_certifications (
    coach_id INT,
    certification_id INT,
    PRIMARY KEY (coach_id, certification_id),
    FOREIGN KEY (coach_id) REFERENCES coaches(user_id),
    FOREIGN KEY (certification_id) REFERENCES coach_certification_types(certification_id)
);

-- Arbiter certifications
CREATE TABLE arbiter_certifications (
    arbiter_id INT,
    certification_id INT,
    PRIMARY KEY (arbiter_id, certification_id),
    FOREIGN KEY (arbiter_id) REFERENCES arbiters(user_id),
    FOREIGN KEY (certification_id) REFERENCES arbiter_certification_types(certification_id)
);


-- Matches table
CREATE TABLE matches (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    time_slot INT,
    hall_id INT,
    table_id INT,
    team1_id INT,
    team2_id INT,
    arbiter_id INT,
    FOREIGN KEY (hall_id) REFERENCES halls(hall_id),
    FOREIGN KEY (table_id) REFERENCES tables(table_id),
    FOREIGN KEY (team1_id) REFERENCES teams(team_id),
    FOREIGN KEY (team2_id) REFERENCES teams(team_id),
    FOREIGN KEY (arbiter_id) REFERENCES arbiters(user_id),
    CHECK (time_slot BETWEEN 1 AND 4)
);
CREATE TABLE created (
    coach_id INT NOT NULL,
    match_id INT NOT NULL,
    PRIMARY KEY (coach_id, match_id),
    FOREIGN KEY (coach_id) REFERENCES coaches(user_id),
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE
);

-- Match players
CREATE TABLE match_players (
    match_id INT PRIMARY KEY,
    white_player INT,
    black_player INT,
    result ENUM('white', 'black', 'draw'),
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (white_player) REFERENCES users(user_id),
    FOREIGN KEY (black_player) REFERENCES users(user_id)
);

-- Ratings table
CREATE TABLE ratings (
    match_id INT PRIMARY KEY,
    arbiter_id INT NOT NULL,
    rating_value FLOAT NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (arbiter_id) REFERENCES arbiters(user_id),
    CHECK (rating_value BETWEEN 1 AND 10)
);

-- 7. TRIGGERS
DELIMITER $$



-- Prevent match scheduling conflicts
CREATE TRIGGER prevent_match_overlap
BEFORE INSERT ON matches
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1 FROM matches
        WHERE hall_id = NEW.hall_id
        AND table_id = NEW.table_id
        AND date = NEW.date
        AND (
            NEW.time_slot BETWEEN time_slot AND time_slot + 1
            OR time_slot BETWEEN NEW.time_slot AND NEW.time_slot + 1
        )
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Time conflict detected for table in hall.';
    END IF;
END $$

-- Prevent arbiter scheduling conflicts
CREATE TRIGGER prevent_arbiter_conflict
BEFORE INSERT ON matches
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1 FROM matches
        WHERE arbiter_id = NEW.arbiter_id
        AND date = NEW.date
        AND (
            NEW.time_slot BETWEEN time_slot AND time_slot + 1
            OR time_slot BETWEEN NEW.time_slot AND NEW.time_slot + 1
        )
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Arbiter already assigned to another match during this time.';
    END IF;
END $$

-- Validate rating insertions
CREATE TRIGGER validate_rating_insert
BEFORE INSERT ON ratings
FOR EACH ROW
BEGIN
    DECLARE match_date DATE;
    DECLARE match_arbiter INT;

    SELECT date, arbiter_id INTO match_date, match_arbiter
    FROM matches
    WHERE match_id = NEW.match_id;

    IF match_arbiter != NEW.arbiter_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only the assigned arbiter can rate this match.';
    END IF;

    IF CURDATE() <= match_date THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot rate match before it is played.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM ratings WHERE match_id = NEW.match_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Match already rated.';
    END IF;
END $$

-- Prevent same team matches
CREATE TRIGGER prevent_same_team_match
BEFORE INSERT ON matches
FOR EACH ROW
BEGIN
    IF NEW.team1_id = NEW.team2_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A team cannot play against itself.';
    END IF;
END $$

-- Validate player team membership
DROP TRIGGER IF EXISTS validate_player_team_membership;
DELIMITER $$

CREATE TRIGGER validate_player_team_membership
BEFORE INSERT ON match_players
FOR EACH ROW
BEGIN
    DECLARE match_date DATE;

    -- Get match date
    SELECT date INTO match_date
    FROM matches
    WHERE match_id = NEW.match_id;

    -- Validate white player membership
    IF NOT EXISTS (
        SELECT 1 FROM player_team_membership
        WHERE player_id = NEW.white_player
        AND match_date BETWEEN start_date AND end_date
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'White player is not a valid member of a team at the match date.';
    END IF;

    -- Validate black player membership
    IF NOT EXISTS (
        SELECT 1 FROM player_team_membership
        WHERE player_id = NEW.black_player
        AND match_date BETWEEN start_date AND end_date
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Black player is not a valid member of a team at the match date.';
    END IF;
END$$

DELIMITER ;


 

-- Validate team tournament registration
DELIMITER $$

CREATE TRIGGER validate_players_teams_in_tournament
BEFORE INSERT ON match_players
FOR EACH ROW
BEGIN
    DECLARE v_tournament_id INT;
    DECLARE white_team_id INT;
    DECLARE black_team_id INT;

    -- Get tournament ID from the match
    SELECT tournament_id INTO v_tournament_id
    FROM matches
    WHERE match_id = NEW.match_id
    LIMIT 1;

    -- Validate the match exists and has a tournament
    IF v_tournament_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Match does not exist or is not linked to a tournament.';
    END IF;

    -- Get white player's team (assuming latest or current team)
    SELECT team_id INTO white_team_id
    FROM player_team_membership
    WHERE player_id = NEW.white_player
    ORDER BY start_date DESC
    LIMIT 1;

    -- Get black player's team
    SELECT team_id INTO black_team_id
    FROM player_team_membership
    WHERE player_id = NEW.black_player
    ORDER BY start_date DESC
    LIMIT 1;

    -- Validate white player's team registration
    IF NOT EXISTS (
        SELECT 1 FROM tournament_teams
        WHERE tournament_id = v_tournament_id AND team_id = white_team_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'White player''s team is not registered in the tournament.';
    END IF;

    -- Validate black player's team registration
    IF NOT EXISTS (
        SELECT 1 FROM tournament_teams
        WHERE tournament_id = v_tournament_id AND team_id = black_team_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Black player''s team is not registered in the tournament.';
    END IF;
END$$

DELIMITER ;

-- 8. Initial database manager setup
-- INSERT INTO users (username, password_hash, role)
-- SELECT 'admin', SHA2('initial_password', 256), 'manager'
-- WHERE NOT EXISTS (
--     SELECT 1 FROM users WHERE role = 'manager'
-- );
















