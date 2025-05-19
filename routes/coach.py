from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from functools import wraps
import mysql.connector
from config import Config
from routes.auth import login_required, get_db_connection

coach_bp = Blueprint('coach', __name__)

def coach_required(f):
    """Decorator to check if user is a coach"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'coach':
            flash('Access denied. Coach role required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@coach_bp.route('/dashboard')
@login_required
@coach_required
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get coach profile
        cursor.execute("""
            SELECT c.*, u.username, u.email,
                   GROUP_CONCAT(cc.certification_type) as certifications
            FROM coaches c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN coach_certifications cc ON c.user_id = cc.coach_id
            WHERE c.user_id = %s
            GROUP BY c.user_id
        """, (session['user_id'],))
        coach = cursor.fetchone()
        
        # Get coached teams
        cursor.execute("""
            SELECT t.*, s.name as sponsor_name,
                   COUNT(ptm.player_id) as player_count
            FROM teams t
            LEFT JOIN sponsors s ON t.sponsor_id = s.sponsor_id
            LEFT JOIN player_team_membership ptm ON t.team_id = ptm.team_id
            WHERE t.coach_id = %s AND ptm.end_date IS NULL
            GROUP BY t.team_id
        """, (session['user_id'],))
        teams = cursor.fetchall()
        
        return render_template('coach_dashboard.html', 
                             coach=coach,
                             teams=teams)
                             
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('auth.login'))
    finally:
        cursor.close()
        conn.close()

@coach_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@coach_required
def profile():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Update coach profile
            cursor.execute("""
                UPDATE coaches 
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
                    DELETE FROM coach_certifications 
                    WHERE coach_id = %s
                """, (session['user_id'],))
                
                # Insert new certifications
                for cert in request.form.getlist('certifications'):
                    cursor.execute("""
                        INSERT INTO coach_certifications (coach_id, certification_type)
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
            
        return redirect(url_for('coach.profile'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get coach profile with certifications
        cursor.execute("""
            SELECT c.*, u.username, u.email,
                   GROUP_CONCAT(cc.certification_type) as certifications
            FROM coaches c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN coach_certifications cc ON c.user_id = cc.coach_id
            WHERE c.user_id = %s
            GROUP BY c.user_id
        """, (session['user_id'],))
        coach = cursor.fetchone()
        
        # Get all available certification types
        cursor.execute("""
            SELECT DISTINCT certification_type 
            FROM coach_certifications
        """)
        available_certifications = [row['certification_type'] for row in cursor.fetchall()]
        
        return render_template('coach/profile.html', 
                             coach=coach,
                             available_certifications=available_certifications)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('coach.dashboard'))
    finally:
        cursor.close()
        conn.close()

@coach_bp.route('/teams')
@login_required
@coach_required
def teams():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all teams coached by this coach
        cursor.execute("""
            SELECT t.*, s.name as sponsor_name,
                   COUNT(ptm.player_id) as player_count
            FROM teams t
            LEFT JOIN sponsors s ON t.sponsor_id = s.sponsor_id
            LEFT JOIN player_team_membership ptm ON t.team_id = ptm.team_id
            WHERE t.coach_id = %s AND ptm.end_date IS NULL
            GROUP BY t.team_id
        """, (session['user_id'],))
        teams = cursor.fetchall()
        
        for team in teams:
            # Get team members for each team
            cursor.execute("""
                SELECT u.username, p.elo_rating, p.nationality,
                       ptm.start_date, ptm.end_date
                FROM player_team_membership ptm
                JOIN users u ON ptm.player_id = u.user_id
                JOIN players p ON u.user_id = p.user_id
                WHERE ptm.team_id = %s AND ptm.end_date IS NULL
            """, (team['team_id'],))
            team['members'] = cursor.fetchall()
        
        return render_template('coach/teams.html', teams=teams)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('coach.dashboard'))
    finally:
        cursor.close()
        conn.close()

@coach_bp.route('/team/<int:team_id>')
@login_required
@coach_required
def team_details(team_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify coach has access to this team
        cursor.execute("""
            SELECT 1 FROM teams 
            WHERE team_id = %s AND coach_id = %s
        """, (team_id, session['user_id']))
        if not cursor.fetchone():
            flash('Access denied to this team', 'error')
            return redirect(url_for('coach.teams'))
        
        # Get team details
        cursor.execute("""
            SELECT t.*, s.name as sponsor_name,
                   u.username as coach_username
            FROM teams t
            LEFT JOIN sponsors s ON t.sponsor_id = s.sponsor_id
            LEFT JOIN users u ON t.coach_id = u.user_id
            WHERE t.team_id = %s
        """, (team_id,))
        team = cursor.fetchone()
        
        # Get team members
        cursor.execute("""
            SELECT u.username, p.elo_rating, p.nationality,
                   ptm.start_date, ptm.end_date
            FROM player_team_membership ptm
            JOIN users u ON ptm.player_id = u.user_id
            JOIN players p ON u.user_id = p.user_id
            WHERE ptm.team_id = %s AND ptm.end_date IS NULL
        """, (team_id,))
        team['members'] = cursor.fetchall()
        
        # Get team's matches
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
            JOIN player_team_membership ptm1 ON m.player1_id = ptm1.player_id
            JOIN player_team_membership ptm2 ON m.player2_id = ptm2.player_id
            WHERE (ptm1.team_id = %s OR ptm2.team_id = %s)
            AND ptm1.end_date IS NULL AND ptm2.end_date IS NULL
            ORDER BY m.date DESC
        """, (team_id, team_id))
        team['matches'] = cursor.fetchall()
        
        return render_template('coach/team_details.html', team=team)
        
    except mysql.connector.Error as err:
        flash('Database error occurred', 'error')
        print(f"Database error: {err}")
        return redirect(url_for('coach.teams'))
    finally:
        cursor.close()
        conn.close() 