from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime
from config import Config
from routes.auth import login_required
from functools import wraps

coach_bp = Blueprint('coach', __name__)

def coach_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'coach':
            flash('Access denied. Coach role required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper

def get_db_connection():
    return mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME
    )


@coach_bp.route('/dashboard')
@login_required
@coach_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    coach_id = session['user_id']

    # 1. Get coach info and current team
# 1. Get coach info and current team
    cursor.execute("""
        SELECT 
            c.name, c.surname, c.nationality,
            u.username,
            t.team_id,
            t.name AS team_name
        FROM coaches c
        JOIN users u ON c.user_id = u.user_id
        LEFT JOIN contracts con ON con.coach_id = c.user_id 
        LEFT JOIN teams t ON con.team_id = t.team_id
        WHERE c.user_id = %s
    """, (coach_id,))
    coach = cursor.fetchone()
   
    team_id = coach['team_id']

    # 2. Matches created for their team
    # Matches created by this coach (joined via created table)
    cursor.execute("""
        SELECT 
            m.*, 
            mp.white_player, mp.black_player,
            u_white.username AS white_player_name,
            u_black.username AS black_player_name,
            h.name AS hall_name, 
            t.table_number, 
            u_arb.username AS arbiter_username,
            team1.name AS team1_name,
            team2.name AS team2_name
        FROM matches m
        JOIN halls h ON m.hall_id = h.hall_id
        JOIN tables t ON m.table_id = t.table_id
        LEFT JOIN match_players mp ON m.match_id = mp.match_id
        LEFT JOIN users u_arb ON m.arbiter_id = u_arb.user_id
        LEFT JOIN users u_white ON mp.white_player = u_white.user_id
        LEFT JOIN users u_black ON mp.black_player = u_black.user_id
        LEFT JOIN teams team1 ON m.team1_id = team1.team_id
        LEFT JOIN teams team2 ON m.team2_id = team2.team_id
        JOIN created c ON m.match_id = c.match_id
        WHERE (m.team1_id = %s OR m.team2_id = %s) AND c.coach_id = %s
        ORDER BY m.date DESC, m.time_slot ASC
    """, (team_id, team_id, coach_id))

    matches_created_by_me = cursor.fetchall()


    # Matches created by other coaches (but involve this coach's team)
    cursor.execute("""
        SELECT 
            m.*, 
            mp.white_player, mp.black_player,
            u_white.username AS white_player_name,
            u_black.username AS black_player_name,
            h.name AS hall_name, 
            t.table_number, 
            u_arb.username AS arbiter_username,
            team1.name AS team1_name,
            team2.name AS team2_name
        FROM matches m
        JOIN halls h ON m.hall_id = h.hall_id
        JOIN tables t ON m.table_id = t.table_id
        LEFT JOIN match_players mp ON m.match_id = mp.match_id
        LEFT JOIN users u_arb ON m.arbiter_id = u_arb.user_id
        LEFT JOIN users u_white ON mp.white_player = u_white.user_id
        LEFT JOIN users u_black ON mp.black_player = u_black.user_id
        LEFT JOIN teams team1 ON m.team1_id = team1.team_id
        LEFT JOIN teams team2 ON m.team2_id = team2.team_id
        JOIN created c ON m.match_id = c.match_id
        WHERE (m.team1_id = %s OR m.team2_id = %s) AND c.coach_id != %s
        ORDER BY m.date DESC, m.time_slot ASC
    """, (team_id, team_id, coach_id))
    matches_created_by_others = cursor.fetchall()
   


    # Matches that were not recorded in `created` table at all (possibly imported or system-generated)
    cursor.execute("""
        SELECT 
            m.*, 
            h.name AS hall_name, 
            t.table_number, 
            u.username AS arbiter_username,
            team1.name AS team1_name,
            team2.name AS team2_name
        FROM matches m
        JOIN halls h ON m.hall_id = h.hall_id
        JOIN tables t ON m.table_id = t.table_id
        LEFT JOIN users u ON m.arbiter_id = u.user_id
        LEFT JOIN teams team1 ON m.team1_id = team1.team_id
        LEFT JOIN teams team2 ON m.team2_id = team2.team_id
        LEFT JOIN created c ON m.match_id = c.match_id
        WHERE (m.team1_id = %s OR m.team2_id = %s) AND c.match_id IS NULL
        ORDER BY m.date DESC, m.time_slot ASC
    """, (team_id, team_id))
    previous_matches = cursor.fetchall()
    
    cursor.execute("""
        SELECT p.user_id, p.name, p.surname
        FROM players p
        JOIN player_team_membership ptm ON p.user_id = ptm.player_id
        WHERE ptm.team_id = %s
    """, (team_id,))
    team_players = cursor.fetchall()


    conn.close()

    return render_template('coach_dashboard.html',
                           coach=coach,
                           matches_created_by_me=matches_created_by_me,
                           matches_created_by_others=matches_created_by_others,
                           previous_matches=previous_matches,
                           team_players=team_players,)
@coach_bp.route('/create-match', methods=['GET', 'POST'])
@login_required
@coach_required
def create_match():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    coach_id = session['user_id']

    # Get coach's team from current contract
    cursor.execute("""
        SELECT team_id FROM contracts 
        WHERE coach_id = %s 
    """, (coach_id,))
    team_result = cursor.fetchone()

    if not team_result:
        flash("You don't have an active contract.", "error")
        return redirect(url_for('coach.dashboard'))
    my_team_id = team_result['team_id']

    # Load data for dropdowns
    cursor.execute("SELECT team_id, name FROM teams")
    all_teams = cursor.fetchall()

    cursor.execute("SELECT hall_id, name, country, capacity FROM halls")
    halls = cursor.fetchall()

    cursor.execute("SELECT t.table_id, t.hall_id, t.table_number, h.name AS hall_name FROM tables t JOIN halls h ON t.hall_id = h.hall_id")
    tables = cursor.fetchall()

    cursor.execute("SELECT u.user_id,u.username,a.name,a.surname,a.experience_level FROM users u JOIN arbiters a ON u.user_id = a.user_id")
    all_arbiters = cursor.fetchall()

    if request.method == 'POST':
        print(request.form.to_dict())
        try:
            match_date = request.form['match_date']
            time_slot = int(request.form['time_slot'])
            hall_id = int(request.form['hall_id'])
            table_id = int(request.form['table_id'])
            team1_id = int(request.form['white_team'])
            team2_id = int(request.form['black_team'])
            arbiter_id = int(request.form['arbiter_id'])

            # Validations
            if team1_id == team2_id:
                flash("A team cannot play against itself.", "error")
                return redirect(request.url)

            if team1_id != my_team_id and team2_id != my_team_id:
                print(my_team_id)
                flash("You can only create matches involving your own team.", "error")
                return redirect(request.url)
            if time_slot == 4:
                flash("Time slot 4 is unavailable, match duration is 2 slots.", "error")
                return redirect(request.url)
            # check if table belongs to the selected hall
            cursor.execute("""SELECT 1 FROM tables WHERE table_id = %s AND hall_id = %s""", (table_id, hall_id))
            if not cursor.fetchone():
                flash("Selected table does not belong to the selected hall.", "error")
                return redirect(request.url)
            
            # Check table availability (block slots ±1 due to 2-slot duration)
            cursor.execute("""
                SELECT 1 FROM matches
                WHERE table_id = %s AND date = %s AND (
                    %s BETWEEN time_slot AND time_slot + 1 OR
                    time_slot BETWEEN %s AND %s + 1
                )
            """, (table_id, match_date, time_slot, time_slot, time_slot))
            if cursor.fetchone():
                flash("Selected table is already booked around that time.", "error")
                return redirect(request.url)

            # Check arbiter availability
            cursor.execute("""
                SELECT 1 FROM matches
                WHERE arbiter_id = %s AND date = %s AND (
                    %s BETWEEN time_slot AND time_slot + 1 OR
                    time_slot BETWEEN %s AND %s + 1
                )
            """, (arbiter_id, match_date, time_slot, time_slot, time_slot))
            if cursor.fetchone():
                flash("Arbiter is not available at that time.", "error")
                return redirect(request.url)

            # Create the match
            cursor.execute("""
                INSERT INTO matches (date, time_slot, hall_id, table_id, team1_id, team2_id, arbiter_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (match_date, time_slot, hall_id, table_id, team1_id, team2_id, arbiter_id))
            match_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO match_players (match_id, white_player, black_player, result)
                VALUES (%s, %s, %s, %s)
            """, (match_id, None, None, None))
                        
            cursor.execute("""
                INSERT INTO created (coach_id, match_id)
                VALUES (%s, %s)
            """, (coach_id, match_id))
            conn.commit()
            flash("Match successfully created.", "success")
            

        except Exception as e:
            conn.rollback()
            flash(f"Error creating match: {str(e)}", "error")
    
    return render_template('create_match.html',
                           halls=halls,
                           tables=tables,
                           all_teams=all_teams,
                           all_arbiters=all_arbiters,
                           my_team_id=my_team_id)
    
@coach_bp.route('/assign-player/<int:match_id>', methods=['POST'])
@login_required
@coach_required
def assign_player(match_id):
    player_id = int(request.form['player_id'])
    role = request.form['role']  # Expecting 'white' or 'black'

    if role not in ['white', 'black']:
        flash("Invalid role provided.", "error")
        return redirect(url_for('coach.dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Get the match date and time slot
        cursor.execute("SELECT date, time_slot FROM matches WHERE match_id = %s", (match_id,))
        match = cursor.fetchone()
        match_date = match['date']
        match_slot = match['time_slot']

        # 2. Get all matches this player is already assigned to
        cursor.execute("""
            SELECT m.time_slot
            FROM match_players mp
            JOIN matches m ON mp.match_id = m.match_id
            WHERE (mp.white_player = %s OR mp.black_player = %s) AND m.date = %s
        """, (player_id, player_id, match_date))
        player_matches = cursor.fetchall()

        # 3. Compute unavailable slots due to match duration of 2 slots
        unavailable_slots = set()
        for pm in player_matches:
            slot = pm['time_slot']
            if slot == 1:
                unavailable_slots.update([1, 2,4])
            elif slot == 2:
                unavailable_slots.update([1, 2, 3,4])
            elif slot == 3:
                unavailable_slots.update([2, 3, 4])
            elif slot == 4:
                unavailable_slots.update([3, 4])

        if match_slot in unavailable_slots:
            flash("Player is not available at this time slot due to another match.", "error")
            return redirect(url_for('coach.dashboard'))

        # 4. Perform the assignment
        if role == 'white':
            cursor.execute("""
                UPDATE match_players
                SET white_player = %s
                WHERE match_id = %s
            """, (player_id, match_id))
        elif role == 'black':
            cursor.execute("""
                UPDATE match_players
                SET black_player = %s
                WHERE match_id = %s
            """, (player_id, match_id))

        conn.commit()
        flash("Player assigned successfully.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Database error: {str(e)}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('coach.dashboard'))


@coach_bp.route('/delete-match/<int:match_id>', methods=['POST'])
@login_required
@coach_required
def delete_match(match_id):
    print("Form data received:", request.form.to_dict())
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete from match_players first (foreign key)
        cursor.execute("DELETE FROM match_players WHERE match_id = %s", (match_id,))
        # Delete from created table
        cursor.execute("DELETE FROM created WHERE match_id = %s", (match_id,))
        # Delete from matches table
        cursor.execute("DELETE FROM matches WHERE match_id = %s", (match_id,))
        # Delete from ratings table
        cursor.execute("DELETE FROM ratings WHERE match_id = %s", (match_id,))
        
        conn.commit()
        flash("Match deleted successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting match: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('coach.dashboard'))