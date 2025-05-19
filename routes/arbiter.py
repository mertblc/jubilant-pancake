from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from routes.auth import login_required, get_db_connection

arbiter_bp = Blueprint('arbiter', __name__)

def arbiter_required(f):
    """Decorator to check if user is an arbiter"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'arbiter':
            flash('Access denied. Arbiter role required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@arbiter_bp.route('/dashboard')
@login_required
@arbiter_required
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get arbiter profile
        cursor.execute("""
            SELECT a.*, u.username, u.email,
                   GROUP_CONCAT(ac.certification_type) as certifications
            FROM arbiters a
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN arbiter_certifications ac ON a.user_id = ac.arbiter_id
            WHERE a.user_id = %s
            GROUP BY a.user_id
        """, (session['user_id'],))
        arbiter = cursor.fetchone()
        
        # Get assigned matches
        cursor.execute("""
            SELECT m.*, 
                   p1.username as player1_username,
                   p2.username as player2_username,
                   h.name as hall_name,
                   t.table_number
            FROM matches m
            JOIN users p1 ON m.player1_id = p1.user_id
            JOIN users p2 ON m.player2_id = p2.user_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            WHERE m.arbiter_id = %s
            ORDER BY m.date DESC
        """, (session['user_id'],))
        matches = cursor.fetchall()
        
        return render_template('arbiter_dashboard.html', 
                             arbiter=arbiter,
                             matches=matches)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        conn.close()

@arbiter_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@arbiter_required
def profile():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Update arbiter profile
            cursor.execute("""
                UPDATE arbiters 
                SET specialization = %s,
                    years_of_experience = %s
                WHERE user_id = %s
            """, (
                request.form.get('specialization'),
                request.form.get('years_of_experience'),
                session['user_id']
            ))
            
            # Update user email
            cursor.execute("""
                UPDATE users 
                SET email = %s
                WHERE user_id = %s
            """, (
                request.form.get('email'),
                session['user_id']
            ))
            
            # Update certifications
            if 'certifications' in request.form:
                # Delete existing certifications
                cursor.execute("""
                    DELETE FROM arbiter_certifications 
                    WHERE arbiter_id = %s
                """, (session['user_id'],))
                
                # Insert new certifications
                for cert in request.form.getlist('certifications'):
                    cursor.execute("""
                        INSERT INTO arbiter_certifications (arbiter_id, certification_type)
                        VALUES (%s, %s)
                    """, (session['user_id'], cert))
            
            conn.commit()
            flash('Profile updated successfully', 'success')
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('arbiter.profile'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get arbiter profile with certifications
        cursor.execute("""
            SELECT a.*, u.username, u.email,
                   GROUP_CONCAT(ac.certification_type) as certifications
            FROM arbiters a
            JOIN users u ON a.user_id = u.user_id
            LEFT JOIN arbiter_certifications ac ON a.user_id = ac.arbiter_id
            WHERE a.user_id = %s
            GROUP BY a.user_id
        """, (session['user_id'],))
        arbiter = cursor.fetchone()
        
        # Get all available certification types
        cursor.execute("""
            SELECT DISTINCT certification_type 
            FROM arbiter_certifications
        """)
        available_certifications = [row['certification_type'] for row in cursor.fetchall()]
        
        return render_template('arbiter_profile.html', 
                             arbiter=arbiter,
                             available_certifications=available_certifications)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('arbiter.dashboard'))
    finally:
        cursor.close()
        conn.close()

@arbiter_bp.route('/matches')
@login_required
@arbiter_required
def matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all matches assigned to this arbiter
        cursor.execute("""
            SELECT m.*, 
                   p1.username as player1_username,
                   p2.username as player2_username,
                   h.name as hall_name,
                   t.table_number
            FROM matches m
            JOIN users p1 ON m.player1_id = p1.user_id
            JOIN users p2 ON m.player2_id = p2.user_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            WHERE m.arbiter_id = %s
            ORDER BY m.date DESC
        """, (session['user_id'],))
        matches = cursor.fetchall()
        
        return render_template('arbiter_matches.html', matches=matches)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('arbiter.dashboard'))
    finally:
        cursor.close()
        conn.close()

@arbiter_bp.route('/match/<int:match_id>', methods=['GET', 'POST'])
@login_required
@arbiter_required
def match_details(match_id):
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verify arbiter has access to this match
            cursor.execute("""
                SELECT 1 FROM matches 
                WHERE match_id = %s AND arbiter_id = %s
            """, (match_id, session['user_id']))
            if not cursor.fetchone():
                flash('Access denied to this match', 'error')
                return redirect(url_for('arbiter.matches'))
            
            # Update match result
            cursor.execute("""
                UPDATE matches 
                SET result = %s,
                    notes = %s
                WHERE match_id = %s
            """, (
                request.form.get('result'),
                request.form.get('notes'),
                match_id
            ))
            
            conn.commit()
            flash('Match result updated successfully', 'success')
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('arbiter.match_details', match_id=match_id))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify arbiter has access to this match
        cursor.execute("""
            SELECT 1 FROM matches 
            WHERE match_id = %s AND arbiter_id = %s
        """, (match_id, session['user_id']))
        if not cursor.fetchone():
            flash('Access denied to this match', 'error')
            return redirect(url_for('arbiter.matches'))
        
        # Get match details
        cursor.execute("""
            SELECT m.*, 
                   p1.username as player1_username,
                   p2.username as player2_username,
                   h.name as hall_name,
                   t.table_number
            FROM matches m
            JOIN users p1 ON m.player1_id = p1.user_id
            JOIN users p2 ON m.player2_id = p2.user_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            WHERE m.match_id = %s
        """, (match_id,))
        match = cursor.fetchone()
        
        return render_template('arbiter_match_details.html', match=match)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('arbiter.matches'))
    finally:
        cursor.close()
        conn.close() 