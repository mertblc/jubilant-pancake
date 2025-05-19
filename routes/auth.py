from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
import hashlib

auth_bp = Blueprint('auth', __name__)

def get_db_connection():
    """Create and return database connection"""
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(str(password).encode()).hexdigest()

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            print(f"Attempting to connect to database with credentials:")
            print(f"Host: {Config.DB_HOST}")
            print(f"User: {Config.DB_USER}")
            print(f"Database: {Config.DB_NAME}")
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Check user credentials
            print(f"Checking credentials for user: {username}")
            cursor.execute("""
                SELECT user_id, username, role 
                FROM users 
                WHERE username = %s AND password_hash = %s
            """, (username, hash_password(password)))
            
            user = cursor.fetchone()
            
            if user:
                print(f"User found: {user}")
                session['username'] = user['username']
                session['user_id'] = user['user_id']
                session['role'] = user['role']
                
                
                # Redirect to appropriate dashboard
                if user['role'] == 'player':
                    return redirect(url_for('player.dashboard'))
                elif user['role'] == 'coach':
                    return redirect(url_for('coach.dashboard'))
                elif user['role'] == 'arbiter':
                    return redirect(url_for('arbiter.dashboard'))
                elif user['role'] == 'manager':
                    return redirect(url_for('db_manager.dashboard'))
            else:
                print(f"No user found with username: {username}")
            
            flash('Invalid username or password', 'error')
            
        except mysql.connector.Error as err:
            print(f"Database error details: {err}")
            print(f"Error code: {err.errno}")
            print(f"SQL state: {err.sqlstate}")
            print(f"Error message: {err.msg}")
            flash('Database error occurred', 'error')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'player')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if username exists
            cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                return render_template('register.html')
            
            # Insert new user
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (username, hash_password(password), role))
            
            user_id = cursor.lastrowid
            
            # Create role-specific profile
            if role == 'player':
                cursor.execute("""
                    INSERT INTO players (user_id, elo_rating)
                    VALUES (%s, %s)
                """, (user_id, Config.INITIAL_ELO))
            
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    return render_template('register.html') 