# ChessDB

A web-based chess tournament management system built with Flask and MySQL.

## Features

- User authentication for different roles (Players, Coaches, Arbiters, Database Managers)
- Match management and rating system
- Hall management
- Role-specific dashboards

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd chess_db_app
```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the database:
- Create a MySQL database named 'chess_db'
- Update database credentials in `config.py`

5. Run the application:
```bash
python app.py
```

## Project Structure

```
chess_db_app/
├── app.py              # Main application file
├── config.py           # Configuration settings
├── requirements.txt    # Project dependencies
├── utils/             # Utility functions
│   ├── __init__.py
│   └── auth.py
├── templates/         # HTML templates
│   ├── login.html
│   ├── arbiter_dashboard.html
│   └── db_manager_dashboard.html
└── static/           # Static files
    └── style.css
```

## User Roles

1. **Players**
   - View their matches
   - Track their ratings

2. **Coaches**
   - Manage their students
   - View student progress

3. **Arbiters**
   - Manage assigned matches
   - Rate completed matches

4. **Database Managers**
   - Create new users
   - Manage tournament halls
   - System administration

## Database Schema

The system uses MySQL with the following main tables:
- players
- coaches
- arbiters
- db_managers
- matches
- halls

## Security

- Password hashing using SHA-256
- Role-based access control
- Session management
- SQL injection prevention

## Development

This is a school project developed for educational purposes.

## License

This project is for educational use only. 