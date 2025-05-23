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
        # Get player's matches with results
        # Fetch all matches where the current player participated
        cursor.execute("""
            SELECT 
                m.match_id,
                m.date,
                m.hall_id,
                m.table_id,
                h.name AS hall_name,
                t.table_number,
                mp.result,
                u_arb.username AS arbiter_username,
                r.rating_value AS elo_change,
                -- Determine opponent's username
                CASE
                    WHEN mp.white_player = %(user_id)s THEN u_black.username
                    ELSE u_white.username
                END AS opponent_name,
                -- Determine match result
                CASE
                    WHEN mp.result = 'draw' THEN 'Draw'
                    WHEN (mp.white_player = %(user_id)s AND mp.result = 'white') OR
                        (mp.black_player = %(user_id)s AND mp.result = 'black') THEN 'Won'
                    WHEN (mp.white_player = %(user_id)s AND mp.result = 'black') OR
                        (mp.black_player = %(user_id)s AND mp.result = 'white') THEN 'Lost'
                    ELSE 'Pending'
                END AS match_result
            FROM match_players mp
            JOIN matches m ON mp.match_id = m.match_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            JOIN users u_white ON mp.white_player = u_white.user_id
            JOIN users u_black ON mp.black_player = u_black.user_id
            LEFT JOIN users u_arb ON m.arbiter_id = u_arb.user_id
            LEFT JOIN ratings r ON m.match_id = r.match_id
            WHERE mp.white_player = %(user_id)s OR mp.black_player = %(user_id)s
            ORDER BY m.date DESC
        """, {"user_id": session['user_id']})

        matches = cursor.fetchall()
        print(matches)
        
        # Calculate statistics
        total_matches = len(matches)
        if total_matches > 0:
            wins = sum(1 for m in matches if m['match_result'] == 'Won')
            win_rate = (wins / total_matches) * 100
        else:
            win_rate = 0
            
        # Get recent opponents (last 5 matches)
        recent_opponents = matches[:5] if matches else []
        
        # Inside dashboard()
        cursor.execute("""
            WITH opponent_data AS (
                SELECT 
                    CASE 
                        WHEN mp.white_player = %(user_id)s THEN mp.black_player
                        ELSE mp.white_player
                    END AS opponent_id,
                    m.date
                FROM match_players mp
                JOIN matches m ON m.match_id = mp.match_id
                WHERE mp.white_player = %(user_id)s OR mp.black_player = %(user_id)s
            )
            SELECT 
                u.username AS opponent_name,
                p.elo_rating AS current_elo,
                od.opponent_id,
                COUNT(*) AS games_played,
                MAX(od.date) AS last_played
            FROM opponent_data od
            JOIN players p ON od.opponent_id = p.user_id
            JOIN users u ON u.user_id = od.opponent_id
            GROUP BY od.opponent_id, u.username, p.elo_rating
            HAVING games_played >= 1
            ORDER BY games_played DESC, last_played DESC
            LIMIT 5
        """, {"user_id": session['user_id']})

        frequent_opponents = cursor.fetchall()
        
        # Step 2: Compute average ELO of the most frequent opponents (if any)
        if frequent_opponents:
            max_games = max(op['games_played'] for op in frequent_opponents)
            max_opponents = [op for op in frequent_opponents if op['games_played'] == max_games]
            avg_elo = sum(op['current_elo'] for op in max_opponents) / len(max_opponents)
            print(max_games)
        else:
            avg_elo = None
        average_elo=round(avg_elo, 1) if avg_elo else "N/A"


        # Get player's team
        cursor.execute("""
            SELECT t.*
            FROM teams t
            JOIN player_team_membership p ON t.team_id = p.team_id
            WHERE p.player_id = %s
        """, (session['user_id'],))
        team = cursor.fetchone()
        
        return render_template('player_dashboard.html', 
                             username=player['username'],
                             current_elo=player['elo_rating'],
                             games_played=total_matches,
                             win_rate=round(win_rate, 1),
                             recent_opponents=recent_opponents,
                             frequent_opponents=frequent_opponents,
                             average_elo=average_elo,
                             team=team)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
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

        # Fetch all matches where the current player participated
        cursor.execute("""
            SELECT 
                m.match_id,
                m.date,
                m.hall_id,
                m.table_id,
                h.name AS hall_name,
                t.table_number,
                mp.white_player,
                mp.black_player,
                mp.result,
                u_white.username AS player1_username,
                u_black.username AS player2_username,
                u_arb.username AS arbiter_username,
                r.rating_value AS elo_change
            FROM match_players mp
            JOIN matches m ON mp.match_id = m.match_id
            JOIN halls h ON m.hall_id = h.hall_id
            JOIN tables t ON m.table_id = t.table_id
            JOIN users u_white ON mp.white_player = u_white.user_id
            JOIN users u_black ON mp.black_player = u_black.user_id
            LEFT JOIN users u_arb ON m.arbiter_id = u_arb.user_id
            LEFT JOIN ratings r ON m.match_id = r.match_id
            WHERE mp.white_player = %s OR mp.black_player = %s
            ORDER BY m.date DESC
        """, (session['user_id'], session['user_id']))

        matches = cursor.fetchall()

        return render_template('player_matches.html', matches=matches)
    
    except mysql.connector.Error as err:
        flash("Database error occurred while loading matches.", "error")
        print(f"Database error: {err}")
        return redirect(url_for('player.dashboard'))
    
    finally:
        cursor.close()
        conn.close()

@player_bp.route('/frequent-opponents')
@login_required
@player_required
def frequent_opponents():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        user_id = session['user_id']

        # Step 1: Get all matches involving the user and determine their opponent
        cursor.execute("""
            WITH opponent_data AS (
                SELECT 
                    CASE 
                        WHEN mp.white_player = %(user_id)s THEN mp.black_player
                        ELSE mp.white_player
                    END AS opponent_id,
                    m.date
                FROM match_players mp
                JOIN matches m ON m.match_id = mp.match_id
                WHERE mp.white_player = %(user_id)s OR mp.black_player = %(user_id)s
            )
            SELECT 
                u.username AS opponent_name,
                p.elo_rating AS current_elo,
                od.opponent_id,
                COUNT(*) AS games_played,
                MAX(od.date) AS last_played
            FROM opponent_data od
            JOIN players p ON od.opponent_id = p.user_id
            JOIN users u ON u.user_id = od.opponent_id
            GROUP BY od.opponent_id, u.username, p.elo_rating
            HAVING games_played > 1
            ORDER BY games_played DESC, last_played DESC
            LIMIT 5
        """, {"user_id": user_id})

        frequent_opponents = cursor.fetchall()
        print(frequent_opponents)
        # Step 2: Compute average ELO of the most frequent opponents (if any)
        if frequent_opponents:
            max_games = max(op['games_played'] for op in frequent_opponents)
            max_opponents = [op for op in frequent_opponents if op['games_played'] == max_games]
            avg_elo = sum(op['current_elo'] for op in max_opponents) / len(max_opponents)
            print(max_games)
        else:
            avg_elo = None

        return render_template(
            'player_dashboard.html',
            frequent_opponents=frequent_opponents,
            average_elo=round(avg_elo, 1) if avg_elo else "N/A"
        )

    except mysql.connector.Error as err:
        flash('Database error while loading frequent opponents.', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('player.dashboard'))

    finally:
        cursor.close()
        conn.close()