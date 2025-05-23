"""
Utility functions for the ChessDB application.
This package contains authentication and database utilities.
"""

from .auth import (
    verify_credentials,
    username_exists,
    create_user,
    login_required,
    role_required,
    get_db_connection
)

# This makes these functions available when importing from utils
__all__ = [
    'verify_credentials',
    'username_exists',
    'create_user',
    'login_required',
    'role_required',
    'get_db_connection'
]
