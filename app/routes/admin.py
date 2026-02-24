"""Admin routes for the application."""
from flask import Blueprint, render_template, request, jsonify, current_app, make_response
from functools import wraps
from app.models import Game, Round, Statistics

bp = Blueprint('admin', __name__)


def require_admin(f):
    """Decorator to require admin password."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        admin_password = current_app.config['ADMIN_PASSWORD']

        if not auth or auth.password != admin_password:
            # Return 401 with WWW-Authenticate header to trigger browser login dialog
            response = make_response(jsonify({'error': 'Unauthorized'}), 401)
            response.headers['WWW-Authenticate'] = 'Basic realm="Admin Access Required"'
            return response

        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@require_admin
def dashboard():
    """Admin dashboard."""
    return render_template('admin.html')


@bp.route('/games')
@require_admin
def list_games():
    """List all games with filters."""
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    games = Game.get_all_with_filters(status, limit, offset)

    return jsonify({
        'success': True,
        'games': games
    })


@bp.route('/game/<game_id>')
@require_admin
def view_game(game_id):
    """View game details."""
    game = Game.get_by_id(game_id)

    if not game:
        return jsonify({'error': 'Game not found'}), 404

    rounds = Round.get_all_by_game(game_id)

    return jsonify({
        'success': True,
        'game': game,
        'rounds': rounds
    })


@bp.route('/stats')
@require_admin
def get_stats():
    """Get admin statistics."""
    stats = {
        'total_games': Statistics.get_game_count(),
        'active_games': Statistics.get_active_game_count(),
        'completed_games': Statistics.get_completed_game_count(),
        'game_modes': Statistics.get_game_mode_stats()
    }

    return jsonify({
        'success': True,
        'stats': stats
    })
