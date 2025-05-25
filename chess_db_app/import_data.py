import sys
sys.path.append('chess_db_app')
import pandas as pd
import mysql.connector
from datetime import datetime, date
import hashlib
from config import Config
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='data_import.log'
)
def parse_date_safe(dob_raw):
    return datetime.strptime(dob_raw.strip(), "%d-%m-%Y").date()


def import_certification_mappings_coach(cursor, df, role):
    """
    Imports coach/arbiter certifications by converting certification names to IDs.
    :param cursor: DB cursor
    :param df: DataFrame with certifications
    :param role: either 'coach' or 'arbiter'
    """
    table = f"{role}_certifications"
    id_field = f"{role}_id"
    user_field = "coach_username" if role == "coach" else "username"

    for _, row in df.iterrows():
        certification_name = row['certification']
        username = row[user_field]

        # Get user ID
        cursor.execute("SELECT user_id FROM users WHERE username = %s AND role = %s", (username, role))
        user = cursor.fetchone()
        if not user:
            logging.warning(f"{role.capitalize()} '{username}' not found.")
            continue
        user_id = user[0]

        # Get certification ID
        cursor.execute("SELECT certification_id FROM coach_certification_types WHERE certification_name = %s", (certification_name,))
        cert = cursor.fetchone()
        if not cert:
            logging.warning(f"Certification '{certification_name}' not found.")
            continue
        cert_id = cert[0]

        # Insert into certification table
        cursor.execute(
            f"INSERT INTO {table} ({id_field}, certification_id) VALUES (%s, %s)",
            (user_id, cert_id)
        )
        logging.info(f"Assigned {role} '{username}' certification '{certification_name}'.")
        
def import_certification_mappings_arbiter(cursor, df, role):
    """
    Imports coach/arbiter certifications by converting certification names to IDs.
    :param cursor: DB cursor
    :param df: DataFrame with certifications
    :param role: either 'coach' or 'arbiter'
    """
    table = f"{role}_certifications"
    id_field = f"{role}_id"
    user_field = "coach_username" if role == "coach" else "username"

    for _, row in df.iterrows():
        certification_name = row['certification']
        username = row[user_field]

        # Get user ID
        cursor.execute("SELECT user_id FROM users WHERE username = %s AND role = %s", (username, role))
        user = cursor.fetchone()
        if not user:
            logging.warning(f"{role.capitalize()} '{username}' not found.")
            continue
        user_id = user[0]

        # Get certification ID
        cursor.execute("SELECT certification_id FROM arbiter_certification_types WHERE certification_name = %s", (certification_name,))
        cert = cursor.fetchone()
        if not cert:
            logging.warning(f"Certification '{certification_name}' not found.")
            continue
        cert_id = cert[0]

        # Insert into certification table
        cursor.execute(
            f"INSERT INTO {table} ({id_field}, certification_id) VALUES (%s, %s)",
            (user_id, cert_id)
        )
        logging.info(f"Assigned {role} '{username}' certification '{certification_name}'.")
        
def convert_date_to_ddmmyyyy(date_str):
    """Convert date string to DD.MM.YYYY format"""
    try:
        # Try parsing with day first (DD.MM.YYYY)
        date_obj = pd.to_datetime(date_str, format='%d.%m.%Y')
        # Convert to DD.MM.YYYY format
        return date_obj.strftime('%d.%m.%Y')
    except:
        # If conversion fails, try to clean and format the string directly
        try:
            # Remove any non-numeric characters except dots
            cleaned = ''.join(c for c in str(date_str) if c.isdigit() or c == '.')
            # Split by dots and ensure we have 3 parts
            parts = cleaned.split('.')
            if len(parts) == 3:
                # Keep the original order (DD.MM.YYYY)
                day = parts[0].zfill(2)
                month = parts[1].zfill(2)
                year = parts[2]
                if len(year) == 2:
                    year = '20' + year
                return f"{day}.{month}.{year}"
        except:
            pass
        # If all conversion attempts fail, return the original string
        logging.warning(f"Could not convert date: {date_str}")
        return str(date_str)

def setup_database_connection():
    """Create and return database connection with all checks disabled"""
    try:
        # First connect without database to create it if needed
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
        cursor.fetchall()  # Clear any results
        cursor.execute(f"USE {Config.DB_NAME}")
        cursor.fetchall()  # Clear any results
        
        # Read and execute create_tables.sql
        with open('sql/create_tables.sql', 'r') as f:
            sql_script = f.read()
            # Split on semicolons to execute each statement separately
            for statement in sql_script.split(';'):
                if statement.strip():
                    try:
                        cursor.execute(statement)
                        cursor.fetchall()  # Clear any results
                    except mysql.connector.Error as err:
                        if "already exists" not in str(err).lower():
                            logging.warning(f"Warning executing SQL: {err}")
        
        # Now connect to the database
        conn.close()
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()
        
        # Completely disable all checks and constraints
        cursor.execute("SET SESSION sql_mode = ''")  # Disable strict mode
        cursor.fetchall()  # Clear any results
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")  # Disable foreign key checks
        cursor.fetchall()  # Clear any results
        cursor.execute("SET UNIQUE_CHECKS = 0")  # Disable unique checks
        cursor.fetchall()  # Clear any results
        cursor.execute("SET AUTOCOMMIT = 0")  # Disable autocommit
        cursor.fetchall()  # Clear any results
        
        # Disable all triggers
        cursor.execute("SET @TRIGGER_DISABLED = 1")
        cursor.fetchall()  # Clear any results
        
        # Check if username UNIQUE constraint exists before dropping it
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'users'
            AND INDEX_NAME = 'username'
            AND NON_UNIQUE = 0
        """)
        result = cursor.fetchone()
        if result and result[0] > 0:
            cursor.execute("ALTER TABLE users DROP INDEX username")
            cursor.fetchall()  # Clear any results
            logging.info("Permanently dropped UNIQUE constraint on username column")
        else:
            logging.info("No UNIQUE constraint found on username column")
        
        # Drop all triggers temporarily
        cursor.execute("""
            SELECT CONCAT('DROP TRIGGER IF EXISTS ', TRIGGER_SCHEMA, '.', TRIGGER_NAME, ';')
            FROM information_schema.TRIGGERS 
            WHERE TRIGGER_SCHEMA = DATABASE()
        """)
        triggers = cursor.fetchall()
        for trigger in triggers:
            cursor.execute(trigger[0])
            cursor.fetchall()  # Clear any results
        
        # Drop all other unique constraints temporarily
        cursor.execute("""
            SELECT CONCAT('ALTER TABLE ', TABLE_SCHEMA, '.', TABLE_NAME, ' DROP INDEX ', INDEX_NAME, ';')
            FROM information_schema.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND NON_UNIQUE = 0
            AND INDEX_NAME != 'PRIMARY'
            AND TABLE_NAME != 'users'  # Skip users table as we already handled it
        """)
        constraints = cursor.fetchall()
        for constraint in constraints:
            try:
                cursor.execute(constraint[0])
                cursor.fetchall()  # Clear any results
            except mysql.connector.Error as err:
                logging.warning(f"Could not drop constraint: {err}")
        
        # Drop all foreign key constraints temporarily
        cursor.execute("""
            SELECT CONCAT('ALTER TABLE ', TABLE_SCHEMA, '.', TABLE_NAME, ' DROP FOREIGN KEY ', CONSTRAINT_NAME, ';')
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND CONSTRAINT_TYPE = 'FOREIGN KEY'
        """)
        foreign_keys = cursor.fetchall()
        for fk in foreign_keys:
            try:
                cursor.execute(fk[0])
                cursor.fetchall()  # Clear any results
            except mysql.connector.Error as err:
                logging.warning(f"Could not drop foreign key: {err}")
        
        cursor.close()
        return conn
    except mysql.connector.Error as err:
        logging.error(f"Database connection failed: {err}")
        raise

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(str(password).encode()).hexdigest()

def get_user_id(cursor, username, role):
    """Get user_id from username and role"""
    cursor.execute("""
        SELECT user_id FROM users 
        WHERE username = %s AND role = %s
    """, (username, role))
    result = cursor.fetchone()
    cursor.fetchall()  # Clear any remaining results
    if result:
        return result[0]
    return None

def get_unique_username(cursor, base_username, role):
    """Get a unique username by appending a suffix if needed"""
    username = base_username
    suffix = 1
    while True:
        cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if not cursor.fetchone():
            return username
        # If username exists, try with suffix
        username = f"{base_username}_{role}_{suffix}"
        suffix += 1

def import_users(cursor, df, role):
    """Import users for a specific role"""
    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (row['username'], hash_password(row['password']), role))
            logging.info(f"Imported user: {row['username']} as {role}")
        except mysql.connector.Error as err:
            logging.error(f"Error importing user {row['username']}: {err}")

def convert_to_python_type(value):
    """Convert numpy types to Python native types"""
    if pd.isna(value):
        return None
    if hasattr(value, 'item'):  # numpy type
        return value.item()
    return value

def import_data(excel_file):
    """Main function to import data from Excel"""
    try:
        # Read Excel file
        logging.info(f"Reading Excel file: {excel_file}")
        xls = pd.ExcelFile(excel_file)
        
        # Connect to database (all constraints disabled in setup_database_connection)
        conn = setup_database_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Import DBManagers
            if 'DBManagers' in xls.sheet_names:
                logging.info("Importing DBManagers...")
                df = pd.read_excel(excel_file, sheet_name='DBManagers')
                for _, row in df.iterrows():
                    try:
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (row['username'], hash_password(row['password']), 'manager'))
                        logging.info(f"Imported user: {row['username']} as manager")
                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing user {row['username']}: {err}")
                        continue

            # 2. Import Titles
            if 'Titles' in xls.sheet_names:
                logging.info("Importing Titles...")
                df = pd.read_excel(excel_file, sheet_name='Titles')
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO titles (title_id, title_name)
                        VALUES (%s, %s)
                    """, (row['title_id'], row['title_name']))
            
            # 3. Import Players
            if 'Players' in xls.sheet_names:
                logging.info("Importing Players...")
                df = pd.read_excel(excel_file, sheet_name='Players',dtype={"date_of_birth": str})
                for _, row in df.iterrows():
                    try:
                        # Insert user exactly as is
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (row['username'], hash_password(row['password']), 'player'))
                        
                        # Get user_id
                        cursor.execute("SELECT user_id FROM users WHERE username = %s", (row['username'],))
                        result = cursor.fetchone()
                        if not result:
                            logging.warning(f"Could not find user_id for {row['username']}, skipping")
                            continue
                        user_id = result[0]

                        # Convert date string like "10-05-2000" to datetime.date (format YYYY-MM-DD)
                        try:
                            date = row['date_of_birth'].split(" ")
                            dateG=[0,0,0]
                            if( len(date) > 1):
                                dateS= date[0].split("-")
                                dateG[0] = dateS[1]  # day
                                dateG[1] = dateS[2]  # month
                                dateG[2] = dateS[0]  # year
                            else:
                                dateS= date[0].split("-")
                                dateG[0] = dateS[0]  # day
                                dateG[1] = dateS[1]  # month
                                dateG[2] = dateS[2]  # year
                            date_string = '-'.join(dateG) 
                            birth_date = parse_date_safe(date_string)

                        except Exception as e:
                            logging.warning(f"Invalid date format for {row['username']}: {row['date_of_birth']}. Skipping.")
                            continue

                        # Insert player details
                        cursor.execute("""
                            INSERT INTO players (
                                user_id, name, surname, nationality, 
                                date_of_birth, fide_id, elo_rating, title_id
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s
                            )
                        """, (
                            user_id,
                            row['name'],
                            row['surname'],
                            row['nationality'],
                            birth_date,  # Correctly parsed date
                            row['fide_id'],
                            row['elo_rating'],
                            row['title_id']
                        ))
                        logging.info(f"Imported player: {row['name']} {row['surname']}")

                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing player {row['username']}: {err}")
                        continue
            
            # 4. Import Sponsors
            if 'Sponsors' in xls.sheet_names:
                logging.info("Importing Sponsors...")
                df = pd.read_excel(excel_file, sheet_name='Sponsors')
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO sponsors (sponsor_id, sponsor_name)
                        VALUES (%s, %s)
                    """, (row['sponsor_id'], row['sponsor_name']))
            
            # 5. Import Teams
            if 'Teams' in xls.sheet_names:
                logging.info("Importing Teams...")
                df = pd.read_excel(excel_file, sheet_name='Teams')
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO teams (team_id, name, sponsor_id)
                        VALUES (%s, %s, %s)
                    """, (row['team_id'], row['team_name'], row['sponsor_id']))
            
            # 6. Import PlayerTeams
            if 'PlayerTeams' in xls.sheet_names:
                logging.info("Importing PlayerTeams...")
                df = pd.read_excel(excel_file, sheet_name='PlayerTeams')
                for _, row in df.iterrows():
                    player_id = get_user_id(cursor, row['username'], 'player')
                    if player_id:
                        cursor.execute("""
                            INSERT INTO player_team_membership (player_id, team_id)
                            VALUES (%s, %s)
                        """, (player_id, row['team_id']))
            
            # 7. Import Coaches
            if 'Coaches' in xls.sheet_names:
                logging.info("Importing Coaches...")
                df = pd.read_excel(excel_file, sheet_name='Coaches',dtype={"contract_start": str, "contract_finish": str})
                for _, row in df.iterrows():
                    try:
                        # Insert user exactly as is
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (row['username'], hash_password(row['password']), 'coach'))
                        
                        # Get user_id
                        cursor.execute("SELECT user_id FROM users WHERE username = %s", (row['username'],))
                        result = cursor.fetchone()
                        if not result:
                            logging.warning(f"Could not find user_id for {row['username']}, skipping")
                            continue
                        user_id = result[0]
                        
                        # Insert coach details
                        cursor.execute("""
                            INSERT INTO coaches (
                                user_id, name, surname, nationality
                            ) VALUES (
                                %s, %s, %s, %s
                            )
                        """, (
                            user_id,
                            row['name'],
                            row['surname'],
                            row['nationality']
                        ))
                        if pd.notna(row['team_id']) and pd.notna(row['contract_start']) and pd.notna(row['contract_finish']):
                            
                            contract_start = row['contract_start'].split(" ")

                            dateG=[0,0,0]
                            if( len(contract_start) > 1):
                                dateS= contract_start[0].split("-")
                                dateG[0] = dateS[1]  # day
                                dateG[1] = dateS[2]  # month
                                dateG[2] = dateS[0]  # year
                            else:
                                dateS= contract_start[0].split("-")
                                dateG[0] = dateS[0]  # day
                                dateG[1] = dateS[1]  # month
                                dateG[2] = dateS[2]  # year
                            date_string = '-'.join(dateG) 
                            contract_start = parse_date_safe(date_string)

                            contract_finish = row['contract_finish'].split(" ")

                            dateG=[0,0,0]
                            if( len(contract_finish) > 1):
                                dateS= contract_finish[0].split("-")
                                dateG[0] = dateS[1]  # day
                                dateG[1] = dateS[2]  # month
                                dateG[2] = dateS[0]  # year
                            else:
                                dateS= contract_finish[0].split("-")
                                dateG[0] = dateS[0]  # day
                                dateG[1] = dateS[1]  # month
                                dateG[2] = dateS[2]  # year
                            date_string = '-'.join(dateG) 
                            contract_finish = parse_date_safe(date_string)
                            team_id = int(row['team_id'])

                            cursor.execute("""
                                INSERT INTO contracts (coach_id, team_id, contract_start, contract_finish)
                                VALUES (%s, %s, %s, %s)
                            """, (user_id, team_id, contract_start, contract_finish))
                        logging.info(f"Imported coach: {row['name']} {row['surname']}")
                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing coach {row['username']}: {err}")
                        continue
            
            # 8. Import CoachCertifications
            if 'CoachCertifications' in xls.sheet_names:
                logging.info("Importing CoachCertifications with mapped IDs...")
                df = pd.read_excel(excel_file, sheet_name='CoachCertifications')
                import_certification_mappings_coach(cursor, df, 'coach')
            
            # 9. Import Arbiters
            if 'Arbiters' in xls.sheet_names:
                logging.info("Importing Arbiters...")
                df = pd.read_excel(excel_file, sheet_name='Arbiters')
                for _, row in df.iterrows():
                    try:
                        # Insert user exactly as is
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (row['username'], hash_password(row['password']), 'arbiter'))
                        cursor.fetchall()  # Clear any remaining results
                        
                        # Get user_id
                        cursor.execute("SELECT user_id FROM users WHERE username = %s", (row['username'],))
                        result = cursor.fetchone()
                        cursor.fetchall()  # Clear any remaining results
                        
                        if not result:
                            logging.warning(f"Could not find user_id for {row['username']}, skipping")
                            continue
                        user_id = result[0]
                        
                        # Insert arbiter details
                        cursor.execute("""
                            INSERT INTO arbiters (
                                user_id, name, surname, nationality, experience_level
                            ) VALUES (
                                %s, %s, %s, %s, %s
                            )
                        """, (
                            user_id,
                            row['name'],
                            row['surname'],
                            row['nationality'],
                            row['experience_level']
                        ))
                        cursor.fetchall()  # Clear any remaining results
                        logging.info(f"Imported arbiter: {row['name']} {row['surname']}")
                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing arbiter {row['username']}: {err}")
                        cursor.fetchall()  # Clear any remaining results
                        continue
            
            # 10. Import ArbiterCertifications
            if 'ArbiterCertifications' in xls.sheet_names:
                logging.info("Importing ArbiterCertifications with mapped IDs...")
                df = pd.read_excel(excel_file, sheet_name='ArbiterCertifications')
                import_certification_mappings_arbiter(cursor, df, 'arbiter')
            cursor.fetchall()  # Clear any remaining results        
            # 11. Import Halls
            if 'Halls' in xls.sheet_names:
                logging.info("Importing Halls...")
                df = pd.read_excel(excel_file, sheet_name='Halls')
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO halls (hall_id, name, country, capacity)
                        VALUES (%s, %s, %s, %s)
                    """, (row['hall_id'], row['hall_name'], row['country'], 
                        row['capacity']))
            
            # 12. Import Tables
            if 'Tables' in xls.sheet_names:
                logging.info("Importing Tables...")
                df = pd.read_excel(excel_file, sheet_name='Tables')
                for _, row in df.iterrows():
                    try:
                        # Convert numpy types to Python native types
                        table_id = convert_to_python_type(row['table_id'])
                        hall_id = convert_to_python_type(row['hall_id'])
                        table_number = convert_to_python_type(row['table_id'])
                        
                        cursor.execute("""
                            INSERT INTO tables (table_id, hall_id, table_number)
                            VALUES (%s, %s, %s)
                        """, (table_id, hall_id, table_number))
                        logging.info(f"Imported table {table_id} in hall {hall_id}")
                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing table: {err}")
                        continue
            
            # 13. Import Matches

            if 'Matches' in xls.sheet_names:
                logging.info("Importing Matches...")
                df = pd.read_excel(excel_file, sheet_name='Matches',dtype={"date": str})

                for _, row in df.iterrows():
                    try:
                        match_id = convert_to_python_type(row['match_id'])
                        time_slot = convert_to_python_type(row['time_slot'])
                        hall_id = convert_to_python_type(row['hall_id'])
                        table_id = convert_to_python_type(row['table_id'])
                        team1_id = convert_to_python_type(row['team1_id'])
                        team2_id = convert_to_python_type(row['team2_id'])
                        arbiter_id = get_user_id(cursor, row['arbiter_username'], 'arbiter')

                        if arbiter_id:
                            # Convert 'DD-MM-YYYY' string to proper date object
                            match_date = row['date'].split(" ")
                            
                            dateG=[0,0,0]
                            dateS= match_date[0].split("-")
                            dateG[0] = dateS[1]  # day
                            dateG[1] = dateS[2]  # month
                            dateG[2] = dateS[0]  # year
                            date_string = '-'.join(dateG) 
                            match_date = parse_date_safe(date_string)

  
                            cursor.execute("""
                                INSERT INTO matches (match_id, date, time_slot, hall_id, 
                                                    table_id, team1_id, team2_id, arbiter_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (match_id, match_date, time_slot, hall_id, 
                                table_id, team1_id, team2_id, arbiter_id))

                            # Insert rating if provided
                            if pd.notna(row['ratings']):
                                rating_value = convert_to_python_type(row['ratings'])
                                cursor.execute("""
                                    INSERT INTO ratings (match_id, arbiter_id, rating_value)
                                    VALUES (%s, %s, %s)
                                """, (match_id, arbiter_id, rating_value))

                    except mysql.connector.Error as err:
                        logging.warning(f"Warning importing match {match_id}: {err}")
                        continue
            
            # 14. Import MatchAssignments
            if 'MatchAssignments' in xls.sheet_names:
                logging.info("Importing MatchAssignments...")
                df = pd.read_excel(excel_file, sheet_name='MatchAssignments')

                for _, row in df.iterrows():
                    white_player_id = get_user_id(cursor, row['white_player'], 'player')
                    black_player_id = get_user_id(cursor, row['black_player'], 'player')

                    if white_player_id and black_player_id:
                        # Normalize result text
                        result_text = str(row['result']).strip().lower()
                        if result_text == 'white wins':
                            normalized_result = 'white'
                        elif result_text == 'black wins':
                            normalized_result = 'black'
                        elif result_text == 'draw':
                            normalized_result = 'draw'
                        else:
                            logging.warning(f"Unknown result '{row['result']}' for match {row['match_id']}")
                            continue

                        # Insert into match_players table
                        cursor.execute("""
                            INSERT INTO match_players (match_id, white_player, black_player, result)
                            VALUES (%s, %s, %s, %s)
                        """, (row['match_id'], white_player_id, black_player_id, normalized_result))
                    else:
                        logging.warning(f"Missing user ID for players in match {row['match_id']}")

                conn.commit()
                logging.info("MatchAssignments processed and inserted into match_players.")            
                     
            
        except Exception as e:
            logging.error(f"Error during import: {e}")
            conn.rollback()
            raise
            
        finally:
            # Re-enable all constraints and checks EXCEPT the username UNIQUE constraint
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            cursor.fetchall()  # Clear any results
            cursor.execute("SET UNIQUE_CHECKS = 1")
            cursor.fetchall()  # Clear any results
            cursor.execute("SET SQL_MODE = 'STRICT_ALL_TABLES'")
            cursor.fetchall()  # Clear any results
            cursor.execute("SET AUTOCOMMIT = 1")
            cursor.fetchall()  # Clear any results
            cursor.execute("SET @TRIGGER_DISABLED = 0")
            cursor.fetchall()  # Clear any results
            
            # Recreate all triggers (but NOT the username UNIQUE constraint)
            cursor.execute("""
                CREATE TRIGGER prevent_coach_overlap 
                BEFORE INSERT ON contracts
                FOR EACH ROW
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM contracts
                        WHERE coach_id = NEW.coach_id
                        AND (
                            (NEW.contract_finish IS NULL AND contract_start >= NEW.contract_start)
                            OR (contract_finish IS NULL AND NEW.contract_start >= contract_start)
                            OR (NEW.contract_start BETWEEN contract_start AND contract_finish)
                            OR (NEW.contract_finish BETWEEN contract_start AND contract_finish)
                        )
                    ) THEN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Coach already has a contract during this time.';
                    END IF;
                END;
            """)
            cursor.fetchall()  # Clear any results
            
            cursor.execute("""
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
                END;
            """)
            cursor.fetchall()  # Clear any results
            
            cursor.execute("""
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
                END;
            """)
            cursor.fetchall()  # Clear any results
            
            cursor.execute("""
                CREATE TRIGGER validate_rating_insert
                BEFORE INSERT ON ratings
                FOR EACH ROW
                BEGIN
                    DECLARE v_match_date VARCHAR(10);
                    DECLARE v_match_arbiter INT;

                    SELECT date, arbiter_id INTO v_match_date, v_match_arbiter
                    FROM matches
                    WHERE match_id = NEW.match_id;

                    IF v_match_arbiter != NEW.arbiter_id THEN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Only the assigned arbiter can rate this match.';
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM ratings WHERE match_id = NEW.match_id
                    ) THEN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Match already rated.';
                    END IF;
                END;
            """)
            cursor.fetchall()  # Clear any results
            
            cursor.execute("""
                CREATE TRIGGER prevent_same_team_match
                BEFORE INSERT ON matches
                FOR EACH ROW
                BEGIN
                    IF NEW.team1_id = NEW.team2_id THEN
                        SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'A team cannot play against itself.';
                    END IF;
                END;
            """)
            cursor.fetchall()  # Clear any results
            

            

      
            
            cursor.close()
            conn.close()
            
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    # Use the correct path to the Excel file
    excel_file = "ChessDB_updated.xlsx"
    try:
        import_data(excel_file)
        print("Data import completed successfully! Check data_import.log for details.")
    except Exception as e:
        print(f"Error during import: {e}")
        print("Check data_import.log for detailed error information.")
