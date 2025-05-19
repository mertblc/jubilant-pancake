from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from routes.auth import login_required, get_db_connection

player_bp = Blueprint('player', __name__)

def player_required(f):
    """Decorator to check if user is a player"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'player':
            flash('Access denied. Player role required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@player_bp.route('/dashboard')
@login_required
@player_required
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get player profile
        cursor.execute("""
            SELECT p.*, u.username
            FROM players p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id = %s
        """, (session['user_id'],))
        player = cursor.fetchone()
        
        # Get player's matches with results
        cursor.execute("""
            SELECT m.*, 
                   CASE 
                       WHEN m.player1_id = %s THEN p2.username
                       ELSE p1.username
                   END as opponent_name,
                   CASE
                       WHEN m.player1_id = %s THEN 
                           CASE m.result
                               WHEN 1 THEN 'Won'
                               WHEN 0 THEN 'Lost'
                               WHEN 0.5 THEN 'Draw'
                               ELSE 'Pending'
                           END
                       ELSE 
                           CASE m.result
                               WHEN 0 THEN 'Won'
                               WHEN 1 THEN 'Lost'
                               WHEN 0.5 THEN 'Draw'
                               ELSE 'Pending'
                           END
                   END as match_result,
                   CASE
                       WHEN m.player1_id = %s THEN m.player1_elo_change
                       ELSE m.player2_elo_change
                   END as elo_change,
                   a.username as arbiter_username
            FROM matches m
            JOIN users p1 ON m.player1_id = p1.user_id
            JOIN users p2 ON m.player2_id = p2.user_id
            LEFT JOIN users a ON m.arbiter_id = a.user_id
            WHERE m.player1_id = %s OR m.player2_id = %s
            ORDER BY m.date DESC
        """, (session['user_id'], session['user_id'], session['user_id'], 
              session['user_id'], session['user_id']))
        matches = cursor.fetchall()
        
        # Calculate statistics
        total_matches = len(matches)
        if total_matches > 0:
            wins = sum(1 for m in matches if m['match_result'] == 'Won')
            win_rate = (wins / total_matches) * 100
        else:
            win_rate = 0
            
        # Get recent opponents (last 5 matches)
        recent_opponents = matches[:5] if matches else []
        
        # Get frequent opponents
        cursor.execute("""
            WITH opponent_matches AS (
                SELECT 
                    CASE 
                        WHEN m.player1_id = %s THEN m.player2_id
                        ELSE m.player1_id
                    END as opponent_id,
                    CASE 
                        WHEN m.player1_id = %s THEN p2.username
                        ELSE p1.username
                    END as opponent_name,
                    m.date
                FROM matches m
                JOIN users p1 ON m.player1_id = p1.user_id
                JOIN users p2 ON m.player2_id = p2.user_id
                WHERE m.player1_id = %s OR m.player2_id = %s
            )
            SELECT 
                om.opponent_name,
                COUNT(*) as games_played,
                MAX(om.date) as last_played,
                p.elo_rating as current_elo
            FROM opponent_matches om
            JOIN players p ON om.opponent_id = p.user_id
            GROUP BY om.opponent_id, om.opponent_name, p.elo_rating
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, MAX(om.date) DESC
            LIMIT 5
        """, (session['user_id'], session['user_id'], session['user_id'], session['user_id']))
        frequent_opponents = cursor.fetchall()
        
        # Get player's team
        cursor.execute("""
            SELECT t.*, p.start_date, p.end_date
            FROM teams t
            JOIN player_team_membership p ON t.team_id = p.team_id
            WHERE p.player_id = %s AND p.end_date IS NULL
        """, (session['user_id'],))
        team = cursor.fetchone()
        
        return render_template('player_dashboard.html', 
                             username=player['username'],
                             current_elo=player['elo_rating'],
                             games_played=total_matches,
                             win_rate=round(win_rate, 1),
                             recent_opponents=recent_opponents,
                             frequent_opponents=frequent_opponents,
                             team=team)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        conn.close()

@player_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@player_required
def profile():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Update player profile
            cursor.execute("""
                UPDATE players 
                SET elo_rating = %s,
                    date_of_birth = %s,
                    nationality = %s
                WHERE user_id = %s
            """, (
                request.form.get('elo_rating'),
                request.form.get('date_of_birth'),
                request.form.get('nationality'),
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
            
            conn.commit()
            flash('Profile updated successfully', 'success')
            
        except mysql.connector.Error as err:
            flash('Database error occurred', 'error')
            print(f"Database error: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('player.profile'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get player profile
        cursor.execute("""
            SELECT p.*, u.username, u.email
            FROM players p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id = %s
        """, (session['user_id'],))
        player = cursor.fetchone()
        
        return render_template('player_profile.html', player=player)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('player.dashboard'))
    finally:
        cursor.close()
        conn.close()

@player_bp.route('/matches')
@login_required
@player_required
def matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all matches for the player
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
            WHERE m.player1_id = %s OR m.player2_id = %s
            ORDER BY m.date DESC
        """, (session['user_id'], session['user_id']))
        matches = cursor.fetchall()
        
        return render_template('player_matches.html', matches=matches)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('player.dashboard'))
    finally:
        cursor.close()
        conn.close()

@player_bp.route('/team')
@login_required
@player_required
def team():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current team membership
        cursor.execute("""
            SELECT t.*, p.start_date, p.end_date,
                   s.name as sponsor_name,
                   c.username as coach_username
            FROM teams t
            JOIN player_team_membership p ON t.team_id = p.team_id
            LEFT JOIN sponsors s ON t.sponsor_id = s.sponsor_id
            LEFT JOIN coaches c ON t.coach_id = c.user_id
            WHERE p.player_id = %s AND p.end_date IS NULL
        """, (session['user_id'],))
        team = cursor.fetchone()
        
        if team:
            # Get team members
            cursor.execute("""
                SELECT u.username, p.elo_rating, p.nationality,
                       ptm.start_date, ptm.end_date
                FROM player_team_membership ptm
                JOIN users u ON ptm.player_id = u.user_id
                JOIN players p ON u.user_id = p.user_id
                WHERE ptm.team_id = %s AND ptm.end_date IS NULL
            """, (team['team_id'],))
            team_members = cursor.fetchall()
        else:
            team_members = []
        
        return render_template('player_team.html', 
                             team=team,
                             team_members=team_members)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('player.dashboard'))
    finally:
        cursor.close()
        conn.close() 