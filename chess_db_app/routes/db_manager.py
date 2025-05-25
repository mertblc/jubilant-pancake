from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from datetime import datetime
from routes.auth import login_required, get_db_connection, hash_password

db_manager_bp = Blueprint('db_manager', __name__)

def manager_required(f):
    """Decorator to check if user is a database manager"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("DEBUGG", session.get('role'))

        if session.get('role') != 'manager':
            flash('Access denied. Database manager role required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@db_manager_bp.route('/dashboard')
@login_required
@manager_required
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user counts by role
        cursor.execute("""
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        """)
        user_counts = {row['role']: row['count'] for row in cursor.fetchall()}
        
        # Get all halls
        cursor.execute("""
            SELECT h.*, COUNT(t.table_id) as table_count
            FROM halls h
            LEFT JOIN tables t ON h.hall_id = t.hall_id
            GROUP BY h.hall_id
            ORDER BY h.name
        """)
        halls = cursor.fetchall()
        print(f"Debug - Number of halls found: {len(halls)}")
        if len(halls) > 0:
            print(f"Debug - First hall data: {halls[0]}")
        else:
            # Let's check if the halls table exists and has any data
            cursor.execute("SELECT COUNT(*) as count FROM halls")
            count = cursor.fetchone()['count']
            print(f"Debug - Total count from halls table: {count}")
            
            # Check table structure
            cursor.execute("DESCRIBE halls")
            columns = cursor.fetchall()
            print(f"Debug - Halls table structure: {columns}")
        
        # Get hall statistics
        cursor.execute("""
            SELECT COUNT(*) as hall_count,
                   SUM(capacity) as total_capacity
            FROM halls
        """)
        hall_stats = cursor.fetchone()
        
        # Get match counts - simplified to just count total matches
        cursor.execute("""
            SELECT COUNT(*) as match_count
            FROM matches
        """)
        match_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT certification_name FROM coach_certification_types
        """)
        coach_certification_types = [row['certification_name'] for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT certification_name FROM arbiter_certification_types
        """)
        arbiter_certification_types = [row['certification_name'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT title_name FROM titles")
        titles = [row['title_name'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT name FROM teams")
        teams = [row['name'] for row in cursor.fetchall()]
        
        return render_template('db_manager_dashboard.html',
                             user_counts=user_counts,
                             halls=halls,
                             hall_stats=hall_stats,
                             match_stats=match_stats,
                             titles=titles,
                             teams=teams,
                             coach_certification_types=coach_certification_types,
                             arbiter_certification_types=arbiter_certification_types)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        conn.close()

@db_manager_bp.route('/users')
@login_required
@manager_required
def users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        role = request.args.get('role', 'all')
        
        # Build query based on role filter
        query = """
            SELECT u.*, 
                   CASE 
                       WHEN u.role = 'player' THEN p.elo_rating
                       WHEN u.role = 'coach' THEN c.years_of_experience
                       WHEN u.role = 'arbiter' THEN a.years_of_experience
                       ELSE NULL
                   END as role_specific_info
            FROM users u
            LEFT JOIN players p ON u.user_id = p.user_id
            LEFT JOIN coaches c ON u.user_id = c.user_id
            LEFT JOIN arbiters a ON u.user_id = a.user_id
        """
        params = []
        
        if role != 'all':
            query += " WHERE u.role = %s"
            params.append(role)
        
        query += " ORDER BY u.username"
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        return render_template('db_manager/users.html',
                             users=users,
                             current_role=role)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('db_manager.dashboard'))
    finally:
        cursor.close()
        conn.close()

@db_manager_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create_user():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            user_type = request.form.get('user_type')  # Changed from role to user_type to match form
            
            print(f"Debug - Creating user with data: username={username}, type={user_type}")  # Debug log
            
            # Validate required fields
            if not all([username, password, confirm_password, user_type]):
                flash('All fields are required', 'error')
                return redirect(url_for('db_manager.dashboard'))
            
            # Validate password match
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('db_manager.dashboard'))
            
            # Validate role
            if user_type not in ['player', 'coach', 'arbiter']:
                flash('Invalid user type selected', 'error')
                return redirect(url_for('db_manager.dashboard'))
            
            # Check if username exists
            cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                return redirect(url_for('db_manager.dashboard'))
            
            # Insert into users table
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (username, hash_password(password), user_type))
            
            user_id = cursor.lastrowid
            print(f"Debug - Created user with ID: {user_id}")  # Debug log
            
            # Create role-specific profile
            if user_type == 'player':
                playerName = request.form.get('player-name', '')
                playerSurname = request.form.get('player-surname', '')
                playerNationality = request.form.get('player-nationality', '')
                playerDateStr = request.form.get('player-date', '')
                playerFide = request.form.get('player-fide', '')
                playerElo = request.form.get('player-elo', '')
                playerTitle = request.form.get('player-title')  # only one
                print(request.form.to_dict)  # Debug log
                
                playerDate = None
                # Check if FIDE ID already exists
                if playerFide:  # Only check if FIDE ID is provided
                    cursor.execute("SELECT 1 FROM players WHERE fide_id = %s", (playerFide,))
                    if cursor.fetchone():
                        flash('A player with this FIDE ID already exists.', 'error')
                        return redirect(url_for('db_manager.create_user'))
                if playerDateStr:
                    try:
                        playerDate = datetime.strptime(playerDateStr, "%d-%m-%Y").date()  # Convert to Python date
                    except ValueError:
                        flash("Invalid date format. Please use DD-MM-YYYY.", "error")
                        return redirect(url_for('manager.create_user'))
                    
                playerTitleId = None
                if playerTitle:
                    cursor.execute("SELECT title_id FROM titles WHERE title_name = %s", (playerTitle,))
                    title_result = cursor.fetchone()
                    if title_result:
                        playerTitleId = title_result[0]
                print(f"Name: {playerName}, Surname: {playerSurname}, Date: {playerDate}, FIDE: {playerFide}, Elo: {playerElo}, Title: {playerTitleId}")  # Debug log
                # 1. Insert coach profile
                cursor.execute("""
                    INSERT INTO players (user_id, name, surname, nationality, date_of_birth, fide_id,elo_rating,title_id)
                    VALUES (%s, %s, %s, %s, %s,%s, %s, %s)
                """, (user_id, playerName, playerSurname, playerNationality,playerDate,playerFide,playerElo,playerTitleId))
                print(f"Debug - Created player {playerName} {playerSurname}, title={playerTitle}")  # Debug log
                    
            elif user_type == 'coach':
                name = request.form.get('coach_name', '')
                surname = request.form.get('coach_surname', '')
                nationality = request.form.get('coach_nationality', '')
                certification_name = request.form.get('coach_certification')  # only one
                team= request.form.get('coach_team')  # only one
                contract_start = request.form.get('coach_contract_start', '')
                contract_end = request.form.get('coach_contract_finish', '')
                start_date = datetime.strptime(contract_start.strip(), "%d-%m-%Y").date()
                end_date = datetime.strptime(contract_end.strip(), "%d-%m-%Y").date()
                
                # Get team_id from team name
                cursor.execute("SELECT team_id FROM teams WHERE name = %s", (team,))
                team_result = cursor.fetchone()
                if not team_result:
                    flash(f"Team '{team}' not found.", "error")
                    # Consume any remaining results to prevent InternalError
                    while cursor.nextset():
                        cursor.fetchall()
                    cursor.close()
                    conn.close()
                    return redirect(url_for('db_manager.dashboard'))  # Or wherever you want to go

                team_id = team_result[0]

                # Check for overlapping contracts
                cursor.execute("""
                    SELECT * FROM contracts
                    WHERE team_id = %s
                    AND NOT (
                        contract_finish < %s OR
                        contract_start > %s
                    )
                """, (team_id, start_date, end_date))

                if cursor.fetchone():
                    flash(f"A coach is already assigned to {team} during this period.", "error")
                    # Consume any remaining results to prevent InternalError
                    while cursor.nextset():
                        cursor.fetchall()
                    cursor.close()
                    conn.close()
                    return redirect(url_for('db_manager.dashboard'))  # Or your form page

                # 1. Insert coach profile
                cursor.execute("""
                    INSERT INTO coaches (user_id, name, surname, nationality)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, name, surname, nationality))

                # 2. If a certification was selected, insert it using its ID
                if certification_name:
                    cursor.execute("""
                        SELECT certification_id FROM coach_certification_types
                        WHERE certification_name = %s
                    """, (certification_name,))
                    result = cursor.fetchone()
                    if result:
                        cert_id = result[0]
                        cursor.execute("""
                            INSERT INTO coach_certifications (coach_id, certification_id)
                            VALUES (%s, %s)
                        """, (user_id, cert_id))
                # 3. Insert contract for this coach
                cursor.execute("""
                    INSERT INTO contracts (coach_id, team_id, contract_start, contract_finish)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, team_id, start_date, end_date))

                print(f"Debug - Created coach {name} {surname}, certification={certification_name}")  # Debug log
            elif user_type == 'arbiter':
                arbitername = request.form.get('arbiter-name', '')
                arbitersurname = request.form.get('arbiter-surname', '')
                arbiternationality = request.form.get('arbiter-nationality', '')
                experience_level = request.form.get('experience-level', '')
                arbitercertification_name = request.form.get('arbiter-certification')  # only one
                print(request.form.to_dict)  # Debug log
                # 1. Insert coach profile
                cursor.execute("""
                    INSERT INTO arbiters (user_id, name, surname, nationality, experience_level)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, arbitername, arbitersurname, arbiternationality, experience_level))

                # 2. If a certification was selected, insert it using its ID
                if arbitercertification_name:
                    cursor.execute("""
                        SELECT certification_id FROM arbiter_certification_types
                        WHERE certification_name = %s
                    """, (arbitercertification_name,))
                    result = cursor.fetchone()
                    if result:
                        cert_id = result[0]
                        cursor.execute("""
                            INSERT INTO arbiter_certifications (arbiter_id, certification_id)
                            VALUES (%s, %s)
                        """, (user_id, cert_id))

                print(f"Debug - Created arbiter {arbitername} {arbitersurname}, certification={arbitercertification_name}")  # Debug log
                


            
            conn.commit()
            flash('User created successfully', 'success')
            return redirect(url_for('db_manager.dashboard'))
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error in create_user: {err}")  # Enhanced error logging
            conn.rollback()
            return redirect(url_for('db_manager.dashboard'))
        finally:
            cursor.close()
            conn.close()
            
        # For GET requests, render the dashboard with coach certification options
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Fetch certification types
            cursor.execute("SELECT certification_name FROM coach_certification_types")
            coach_certification_types = [row['certification_name'] for row in cursor.fetchall()]
            cursor.execute("SELECT certification_name FROM arbiter_certification_types")
            arbiter_certification_types = [row['certification_name'] for row in cursor.fetchall()]

            # Fetch other dashboard data (as in the dashboard route)
            cursor.execute("SELECT h.*, COUNT(t.table_id) as table_count FROM halls h LEFT JOIN tables t ON h.hall_id = t.hall_id GROUP BY h.hall_id ORDER BY h.name")
            halls = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as hall_count, SUM(capacity) as total_capacity FROM halls")
            hall_stats = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) as match_count FROM matches")
            match_stats = cursor.fetchone()

            cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            user_counts = {row['role']: row['count'] for row in cursor.fetchall()}

            return render_template("db_manager_dashboard.html",
                                coach_certification_types=coach_certification_types,
                                arbiter_certification_types=arbiter_certification_types,
                                halls=halls,
                                hall_stats=hall_stats,
                                match_stats=match_stats,
                                user_counts=user_counts)

        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error in GET create_user: {err}")
            return redirect(url_for('db_manager.dashboard'))
        finally:
            cursor.close()
            conn.close()
    
    # For GET requests, redirect to dashboard where the form exists
    return redirect(url_for('db_manager.dashboard'))

@db_manager_bp.route('/halls')
@login_required
@manager_required
def halls():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all halls with table counts
        cursor.execute("""
            SELECT h.*, COUNT(t.table_id) as table_count
            FROM halls h
            LEFT JOIN tables t ON h.hall_id = t.hall_id
            GROUP BY h.hall_id
            ORDER BY h.name
        """)
        halls = cursor.fetchall()
        
        return render_template('db_manager/halls.html', halls=halls)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('db_manager.dashboard'))
    finally:
        cursor.close()
        conn.close()

@db_manager_bp.route('/rename_hall/<int:hall_id>', methods=['POST'])
@login_required
@manager_required
def rename_hall(hall_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        new_name = request.form.get('new_name')
        cursor.execute("UPDATE halls SET name = %s WHERE hall_id = %s", (new_name, hall_id))
        conn.commit()

        flash('Hall renamed successfully', 'success')
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error in rename_hall: {err}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('db_manager.dashboard'))