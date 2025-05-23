from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from utils.auth import (
    username_exists, create_user,
    login_required, role_required, get_db_connection
)
from config import Config
from routes.auth import auth_bp
from routes.player import player_bp
from routes.coach import coach_bp
from routes.arbiter import arbiter_bp
from routes.db_manager import db_manager_bp

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(player_bp, url_prefix='/player')
app.register_blueprint(coach_bp, url_prefix='/coach')
app.register_blueprint(arbiter_bp, url_prefix='/arbiter')
app.register_blueprint(db_manager_bp, url_prefix='/manager')

@app.route('/')
def home():
    """Redirect to login page"""
    if 'username' in session:
        if session['role'] == 'player':
            return redirect(url_for('player.dashboard'))
        elif session['role'] == 'coach':
            return redirect(url_for('coach.dashboard'))
        elif session['role'] == 'arbiter':
            return redirect(url_for('arbiter.dashboard'))
        elif session['role'] == 'manager':
            return redirect(url_for('db_manager.dashboard'))
    return redirect(url_for('auth.login'))

@app.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard/<role>')
@login_required
@role_required(['player', 'coach', 'arbiter', 'db_manager'])
def dashboard(role):
    """Render the appropriate dashboard based on user role"""
    if role != session['role']:
        return redirect(url_for('dashboard', role=session['role']))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if role == 'arbiter':
            # Get arbiter's matches and statistics
            cursor.execute("""
                SELECT COUNT(*) as total_rated 
                FROM matches 
                WHERE arbiter_id = %s AND rating IS NOT NULL
            """, (session['user_id'],))
            total_rated = cursor.fetchone()['total_rated']
            
            cursor.execute("""
                SELECT AVG(rating) as avg_rating 
                FROM matches 
                WHERE arbiter_id = %s AND rating IS NOT NULL
            """, (session['user_id'],))
            avg_rating = cursor.fetchone()['avg_rating'] or 0
            
            cursor.execute("""
                SELECT COUNT(*) as pending 
                FROM matches 
                WHERE arbiter_id = %s AND is_completed = 1 AND rating IS NULL
            """, (session['user_id'],))
            pending_ratings = cursor.fetchone()['pending']
            
            cursor.execute("""
                SELECT m.*, 
                    p1.username as player1_name, 
                    p2.username as player2_name
                FROM matches m
                JOIN players p1 ON m.player1_id = p1.id
                JOIN players p2 ON m.player2_id = p2.id
                WHERE m.arbiter_id = %s
                ORDER BY m.date DESC
            """, (session['user_id'],))
            matches = cursor.fetchall()
            
            return render_template('arbiter_dashboard.html',
                                total_rated_matches=total_rated,
                                average_rating=avg_rating,
                                pending_ratings=pending_ratings,
                                matches=matches)
            
        elif role == 'db_manager':
            # Get all halls for management
            cursor.execute("SELECT * FROM halls ORDER BY hall_id")
            halls = cursor.fetchall()
            
            # Get hall statistics
            cursor.execute("""
                SELECT COUNT(*) as hall_count,
                       SUM(capacity) as total_capacity
                FROM halls
            """)
            hall_stats = cursor.fetchone()
            
            return render_template('db_manager_dashboard.html', 
                                halls=halls,
                                hall_stats=hall_stats)
            
        # Add other role-specific dashboard logic here
        # For now, return a simple message for other roles
        return f"Dashboard for {role} (to be implemented)"
        
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash('Database error occurred', 'error')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True)
