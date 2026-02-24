"""Flask application factory."""
from flask import Flask
from flask_caching import Cache
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import get_config
import secrets

# Initialize extensions
cache = Cache()


def create_app(config_name=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load configuration
    config_class = get_config()
    app.config.from_object(config_class)

    # Ensure secret key is set
    if app.config['SECRET_KEY'] == 'dev-secret-key-change-in-production':
        app.config['SECRET_KEY'] = secrets.token_hex(32)

    # Handle proxy headers for subpath hosting
    # This allows Flask to work correctly when hosted at /scissors/ or any subpath
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1
    )

    # Initialize extensions
    cache.init_app(app)

    # Register blueprints
    from app.routes import game, admin, api

    app.register_blueprint(game.bp)
    app.register_blueprint(admin.bp, url_prefix='/admin')
    app.register_blueprint(api.bp, url_prefix='/api')

    # Register error handlers
    register_error_handlers(app)

    # Start background jobs
    if not app.config['TESTING']:
        from app.utils.scheduler import start_scheduler
        start_scheduler(app)

    return app


def register_error_handlers(app):
    """Register error handlers for the application."""

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('error.html', error_code=404, message='Page not found'), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('error.html', error_code=500, message='Internal server error'), 500

    @app.errorhandler(403)
    def forbidden(error):
        from flask import render_template
        return render_template('error.html', error_code=403, message='Access forbidden'), 403
