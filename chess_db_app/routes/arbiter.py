from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from routes.auth import login_required, get_db_connection

arbiter_bp = Blueprint('arbiter', __name__)

def arbiter_required(f):
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

        # Get arbiter profile info
        cursor.execute("""
            SELECT a.*, u.username
            FROM arbiters a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.user_id = %s
        """, (session['user_id'],))
        arbiter = cursor.fetchone()

        # Get all matches assigned to this arbiter
        cursor.execute("""
            SELECT m.*, 
                h.name AS hall_name, 
                t.table_number,
                r.rating_value AS rating,
                team1.name AS team1_name,
                team2.name AS team2_name
            FROM matches m
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            LEFT JOIN ratings r ON m.match_id = r.match_id
            LEFT JOIN teams team1 ON m.team1_id = team1.team_id
            LEFT JOIN teams team2 ON m.team2_id = team2.team_id
            WHERE m.arbiter_id = %s
            ORDER BY m.date DESC, m.time_slot
        """, (session['user_id'],))
        matches = cursor.fetchall()

        # Calculate average rating given by arbiter
        cursor.execute("""
            SELECT AVG(rating_value) AS avg_rating
            FROM ratings
            WHERE arbiter_id = %s
        """, (session['user_id'],))
        result = cursor.fetchone()
        avg_rating = round(result['avg_rating'], 2) if result['avg_rating'] else "N/A"
        print(matches)
        return render_template(
            'arbiter_dashboard.html',
            arbiter=arbiter,
            matches=matches,
            avg_rating=avg_rating
        )

    except mysql.connector.Error as err:
        flash('Database error occurred.', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        conn.close()

@arbiter_bp.route('/rate_match/<int:match_id>', methods=['POST'])
@login_required
@arbiter_required
def rate_match(match_id):
    rating_value = request.form.get('rating')
    if not rating_value:
        flash('Rating value is required.', 'error')
        return redirect(url_for('arbiter.dashboard'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if match is already rated
        cursor.execute("SELECT 1 FROM ratings WHERE match_id = %s", (match_id,))
        if cursor.fetchone():
            flash('Match already rated.', 'warning')
            return redirect(url_for('arbiter.dashboard'))

        # Insert new rating
        cursor.execute("""
            INSERT INTO ratings (match_id, arbiter_id, rating_value)
            VALUES (%s, %s, %s)
        """, (match_id, session['user_id'], rating_value))

        conn.commit()
        flash('Rating submitted successfully.', 'success')

    except mysql.connector.Error as err:
        flash('Database error occurred during rating.', 'error')
        print(f"Database error: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('arbiter.dashboard'))