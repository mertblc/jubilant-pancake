Here is a clean and informative README.md file for your project:

⸻


# Chess Tournament Management System

This is a Flask-based web application for managing chess tournaments, including players, coaches, arbiters, teams, match scheduling, rating, and assignment logic. It supports role-based dashboards and enforces logical constraints across all interactions.

---

## 🔧 Setup Instructions

To run the project locally, follow these steps:

1. Navigate to the application directory
   ```
   cd code/chess_db_app
   ```

2.	Create a Python 3.11 virtual environment
   ```
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3.	Install required dependencies
   ```
   pip install -r requirements.txt
   ```

4.	Import initial data into the database
   ```
   python import_data.py
   ```

5.	Run the Flask application
   ```
   python app.py
   ```

6.	Open the application in your browser
After launching, navigate to the local address shown in the terminal:
http://127.0.0.1:5000

⸻

👤 Roles Supported
-	Players: View opponents and ratings.
-	Coaches: Create matches, assign players, and view team details.
-	Arbiters: Rate matches, view assignments, and see their rating history.
-	Admins (optional): Manage all entities from the backend.

⸻

📂 Project Structure

code/chess_db_app/
│
├── app.py                # Main Flask application entry point
├── import_data.py        # CSV-based database importer
├── routes/               # Flask Blueprints (auth, coach, player, arbiter)
├── templates/            # HTML templates (Jinja2)
├── static/               # Static files (CSS)
├── config.py             # Database configuration
└── requirements.txt      # Python dependencies


⸻

🧪 Requirements
-	Python 3.11
-	MySQL or compatible RDBMS (ensure tables are created with correct constraints)

⸻

📋 Notes
- Dates are stored as YYYY-MM-DD in the database but formatted to DD-MM-YYYY on the frontend.
-	All logic constraints (contract periods, time slot overlaps, duplicate FIDE IDs, etc.) are enforced.

⸻

✅ License

This project is for educational purposes as part of a university course.

---