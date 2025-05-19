from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from routes.auth import login_required, get_db_connection, hash_password

db_manager_bp = Blueprint('db_manager', __name__)

def manager_required(f):
    """Decorator to check if user is a database manager"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
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
        
        return render_template('db_manager_dashboard.html',
                             user_counts=user_counts,
                             halls=halls,
                             hall_stats=hall_stats,
                             match_stats=match_stats)
                             
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
                rating = request.form.get('rating', Config.INITIAL_ELO)
                cursor.execute("""
                    INSERT INTO players (user_id, elo_rating)
                    VALUES (%s, %s)
                """, (user_id, rating))
                print(f"Debug - Created player profile with rating: {rating}")  # Debug log
                
            elif user_type == 'coach':
                specialization = request.form.get('specialization', '')
                cursor.execute("""
                    INSERT INTO coaches (user_id, specialization)
                    VALUES (%s, %s)
                """, (user_id, specialization))
                print(f"Debug - Created coach profile with specialization: {specialization}")  # Debug log
                
            elif user_type == 'arbiter':
                certification = request.form.get('certification', 'national')
                cursor.execute("""
                    INSERT INTO arbiters (user_id, experience_level)
                    VALUES (%s, %s)
                """, (user_id, certification))
                print(f"Debug - Created arbiter profile with certification: {certification}")  # Debug log
            
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

@db_manager_bp.route('/halls/<int:hall_id>', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_hall(hall_id):
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Update hall
            cursor.execute("""
                UPDATE halls 
                SET name = %s,
                    capacity = %s
                WHERE hall_id = %s
            """, (
                request.form.get('name'),
                request.form.get('capacity'),
                hall_id
            ))
            
            conn.commit()
            flash('Hall updated successfully', 'success')
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('db_manager.halls'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get hall details
        cursor.execute("""
            SELECT h.*, COUNT(t.table_id) as table_count
            FROM halls h
            LEFT JOIN tables t ON h.hall_id = t.hall_id
            WHERE h.hall_id = %s
            GROUP BY h.hall_id
        """, (hall_id,))
        hall = cursor.fetchone()
        
        if not hall:
            flash('Hall not found', 'error')
            return redirect(url_for('db_manager.halls'))
        
        # Get tables in this hall
        cursor.execute("""
            SELECT t.*, COUNT(m.match_id) as match_count
            FROM tables t
            LEFT JOIN matches m ON t.table_id = m.table_id
            WHERE t.hall_id = %s
            GROUP BY t.table_id
            ORDER BY t.table_number
        """, (hall_id,))
        tables = cursor.fetchall()
        
        return render_template('db_manager/edit_hall.html',
                             hall=hall,
                             tables=tables)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('db_manager.halls'))
    finally:
        cursor.close()
        conn.close()

@db_manager_bp.route('/matches')
@login_required
@manager_required
def matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all matches with details
        cursor.execute("""
            SELECT m.*, 
                   p1.username as player1_username,
                   p2.username as player2_username,
                   a.username as arbiter_username,
                   h.name as hall_name,
                   t.table_number
            FROM matches m
            JOIN users p1 ON m.player1_id = p1.user_id
            JOIN users p2 ON m.player2_id = p2.user_id
            LEFT JOIN users a ON m.arbiter_id = a.user_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            ORDER BY m.date DESC
        """)
        matches = cursor.fetchall()
        
        return render_template('db_manager/matches.html', matches=matches)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('db_manager.dashboard'))
    finally:
        cursor.close()
        conn.close()

@db_manager_bp.route('/matches/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create_match():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Insert new match
            cursor.execute("""
                INSERT INTO matches (
                    player1_id, player2_id, arbiter_id,
                    hall_id, table_id, date, result, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                request.form.get('player1_id'),
                request.form.get('player2_id'),
                request.form.get('arbiter_id'),
                request.form.get('hall_id'),
                request.form.get('table_id'),
                request.form.get('date'),
                request.form.get('result'),
                request.form.get('notes')
            ))
            
            conn.commit()
            flash('Match created successfully', 'success')
            return redirect(url_for('db_manager.matches'))
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get available players
        cursor.execute("""
            SELECT u.user_id, u.username, p.elo_rating
            FROM users u
            JOIN players p ON u.user_id = p.user_id
            WHERE u.role = 'player'
            ORDER BY u.username
        """)
        players = cursor.fetchall()
        
        # Get available arbiters
        cursor.execute("""
            SELECT u.user_id, u.username
            FROM users u
            JOIN arbiters a ON u.user_id = a.user_id
            WHERE u.role = 'arbiter'
            ORDER BY u.username
        """)
        arbiters = cursor.fetchall()
        
        # Get available halls and tables
        cursor.execute("""
            SELECT h.hall_id, h.name, t.table_id, t.table_number
            FROM halls h
            JOIN tables t ON h.hall_id = t.hall_id
            ORDER BY h.name, t.table_number
        """)
        venues = {}
        for row in cursor.fetchall():
            if row['hall_id'] not in venues:
                venues[row['hall_id']] = {
                    'name': row['name'],
                    'tables': []
                }
            venues[row['hall_id']]['tables'].append({
                'id': row['table_id'],
                'number': row['table_number']
            })
        
        return render_template('db_manager/create_match.html',
                             players=players,
                             arbiters=arbiters,
                             venues=venues)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('db_manager.matches'))
    finally:
        cursor.close()
        conn.close() 