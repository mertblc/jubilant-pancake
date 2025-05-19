from functools import wraps
from flask import session, redirect, url_for, flash
import hashlib
import mysql.connector
from typing import List, Optional, Dict, Any
from config import Config

# Use database configuration from config.py
db_config = {
    'host': Config.DB_HOST,
    'user': Config.DB_USER,
    'password': Config.DB_PASSWORD,
    'database': Config.DB_NAME
}

def get_db_connection():
    """Create and return a database connection"""
    return mysql.connector.connect(**db_config)

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verify user credentials against all user tables
    Returns user info if credentials are valid, None otherwise
    """
    hashed_password = hash_password(password)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check each user table
        tables = ['players', 'coaches', 'arbiters', 'db_managers']
        roles = ['player', 'coach', 'arbiter', 'db_manager']
        
        for table, role in zip(tables, roles):
            query = f"SELECT * FROM {table} WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashed_password))
            user = cursor.fetchone()
            
            if user:
                user['role'] = role
                return user
        
        return None
        
    except mysql.connector.Error as err:
        print(f"Database error in verify_credentials: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def username_exists(username: str) -> bool:
    """Check if username exists in any user table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        tables = ['players', 'coaches', 'arbiters', 'db_managers']
        for table in tables:
            cursor.execute(f"SELECT 1 FROM {table} WHERE username = %s", (username,))
            if cursor.fetchone():
                return True
        
        return False
        
    except mysql.connector.Error as err:
        print(f"Database error in username_exists: {err}")
        return True  # Return True on error to prevent duplicate usernames
    finally:
        cursor.close()
        conn.close()

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles: List[str]):
    """Decorator to check if user has the required role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in allowed_roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_user(username: str, password: str, user_type: str, **kwargs) -> bool:
    """
    Create a new user in the appropriate table
    Returns True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        hashed_password = hash_password(password)
        
        if user_type == 'player':
            rating = kwargs.get('rating', 1500)
            cursor.execute("""
                INSERT INTO players (username, password, rating)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, rating))
            
        elif user_type == 'coach':
            specialization = kwargs.get('specialization', '')
            cursor.execute("""
                INSERT INTO coaches (username, password, specialization)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, specialization))
            
        elif user_type == 'arbiter':
            certification = kwargs.get('certification', 'national')
            cursor.execute("""
                INSERT INTO arbiters (username, password, certification)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, certification))
            
        else:
            return False
            
        conn.commit()
        return True
        
    except mysql.connector.Error as err:
        print(f"Database error in create_user: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()
