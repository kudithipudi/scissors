"""Game routes for the application."""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.services.game_service import GameService
from app.services.qr_service import QRService
from app.models import Game, Statistics
import uuid

bp = Blueprint('game', __name__)


@bp.route('/')
def index():
    """Landing page."""
    return render_template('index.html')


@bp.route('/device-test')
def device_test():
    """Device detection test page."""
    return render_template('device_test.html')


@bp.route('/device-simple-test')
def device_simple_test():
    """Simple device detection test page (no Alpine.js)."""
    return render_template('device_simple_test.html')


@bp.route('/game/create', methods=['POST'])
def create_game():
    """Create a new game."""
    # Ensure session has an ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    # Get request data
    data = request.get_json()
    best_of = data.get('best_of', 3)

    # Create game
    game, error = GameService.create_game(best_of, session['session_id'])

    if error:
        return jsonify({'error': error}), 400

    return jsonify({
        'success': True,
        'game_code': game['game_code'],
        'game_id': game['id']
    })


@bp.route('/game/<game_code>')
def view_game(game_code):
    """View game page."""
    # Ensure session has an ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    # Get game
    game = Game.get_by_code(game_code.upper())

    if not game:
        return render_template('error.html', error_code=404, message='Game not found'), 404

    # Check if user is a player
    session_id = session['session_id']
    is_player = GameService.is_player_in_game(game, session_id)
    player_role = GameService.get_player_role(game, session_id)

    # If game is waiting and user is not in game, they can join
    if game['status'] == 'waiting' and not is_player:
        # Auto-join as guest
        if not game.get('guest_session_id'):
            updated_game, error = GameService.join_game(game_code.upper(), session_id)
            if error:
                return render_template('error.html', error_code=400, message=error), 400
            game = updated_game
            player_role = 'guest'
            is_player = True

    # If user is not a player, they can't view the game
    if not is_player:
        return render_template('error.html', error_code=403, message='You are not a player in this game'), 403

    # Generate QR code if host and waiting
    qr_code = None
    join_url = None
    if game['status'] == 'waiting' and player_role == 'host':
        qr_code = QRService.generate_qr_code(game_code.upper())
        join_url = QRService.get_join_url(game_code.upper())

    return render_template(
        'game.html',
        game=game,
        player_role=player_role,
        qr_code=qr_code,
        join_url=join_url
    )


@bp.route('/game/<game_code>/cancel', methods=['POST'])
def cancel_game(game_code):
    """Cancel a game."""
    if 'session_id' not in session:
        return jsonify({'error': 'Invalid session'}), 401

    success, error = GameService.cancel_game(game_code.upper(), session['session_id'])

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'success': True})


@bp.route('/game/<game_code>/join', methods=['POST'])
def join_game(game_code):
    """Join a game as guest."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    game, error = GameService.join_game(game_code.upper(), session['session_id'])

    if error:
        return jsonify({'error': error}), 400

    return jsonify({
        'success': True,
        'game': game
    })
