"""Application configuration management."""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class."""

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Session Configuration
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')

    # Admin Configuration
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')

    # Mailjet Configuration
    MAILJET_API_KEY = os.getenv('MAILJET_API_KEY')
    MAILJET_API_SECRET = os.getenv('MAILJET_API_SECRET')

    # Game Configuration
    GAME_TIMEOUT_MINUTES = int(os.getenv('GAME_TIMEOUT_MINUTES', '2'))
    MAX_GAMES_PER_IP_PER_HOUR = int(os.getenv('MAX_GAMES_PER_IP_PER_HOUR', '10'))
    SHAKE_THRESHOLD = 15  # m/s²
    REQUIRED_SHAKES = 3
    SHAKE_TIMEOUT_MS = 2000

    # Cache Configuration
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 120

    # QR Code Configuration
    QR_BOX_SIZE = 10
    QR_BORDER = 4


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SESSION_COOKIE_SECURE = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on FLASK_ENV environment variable."""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
