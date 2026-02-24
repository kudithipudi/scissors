"""Application entry point."""
from app import create_app
import os

# Create Flask app instance
app = create_app()

if __name__ == '__main__':
    # Development server
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=debug
    )
