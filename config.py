"""
Configuration settings for the ChessDB application.
For a school project, we'll keep it simple with direct values.
In a real production environment, these would be environment variables.
"""

import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    # Database settings
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '3946471')
    DB_NAME = os.getenv('DB_NAME', 'chessdb')
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = True  # Set to False in production
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # ELO settings
    K_FACTOR = 32  # K-factor for ELO calculations
    INITIAL_ELO = 1000  # Initial ELO rating for new players 