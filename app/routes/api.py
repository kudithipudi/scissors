"""API routes for real-time game operations."""
from flask import Blueprint, request, jsonify, session
from app.services.game_service import GameService
from app.models import Game, Round, Statistics
import random

bp = Blueprint('api', __name__)


@bp.route('/stats')
def get_stats():
    """Get public statistics."""
    stats = {
        'active_games': Statistics.get_active_game_count(),
        'total_games': Statistics.get_game_count()
    }
    return jsonify(stats)


@bp.route('/game/<game_code>/state')
def get_game_state(game_code):
    """Get current game state."""
    state = GameService.get_game_state(game_code.upper())

    if not state:
        return jsonify({'error': 'Game not found'}), 404

    # Don't reveal opponent's choice until both have chosen
    if 'session_id' in session:
        player_role = GameService.get_player_role(state['game'], session['session_id'])
        if player_role and state['rounds']:
            current_round = state['rounds'][-1]
            if not current_round.get('completed_at'):
                # Hide opponent's choice
                if player_role == 'host' and current_round.get('guest_choice'):
                    state['rounds'][-1]['guest_choice'] = None
                elif player_role == 'guest' and current_round.get('host_choice'):
                    state['rounds'][-1]['host_choice'] = None

    return jsonify(state)


@bp.route('/game/<game_code>/shake', methods=['POST'])
def record_shake(game_code):
    """Record shake count for player."""
    if 'session_id' not in session:
        return jsonify({'error': 'Invalid session'}), 401

    data = request.get_json()
    shake_count = data.get('shake_count', 0)

    # Get game and determine player role
    game = Game.get_by_code(game_code.upper())
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    player_role = GameService.get_player_role(game, session['session_id'])
    if not player_role:
        return jsonify({'error': 'Not a player in this game'}), 403

    success, error = GameService.record_shake(game_code.upper(), player_role, shake_count)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({'success': True, 'shake_count': shake_count})


@bp.route('/game/<game_code>/choice', methods=['POST'])
def submit_choice(game_code):
    """Submit player choice."""
    if 'session_id' not in session:
        return jsonify({'error': 'Invalid session'}), 401

    data = request.get_json()
    choice = data.get('choice')

    # Get game and determine player role
    game = Game.get_by_code(game_code.upper())
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    player_role = GameService.get_player_role(game, session['session_id'])
    if not player_role:
        return jsonify({'error': 'Not a player in this game'}), 403

    round_result, error = GameService.submit_choice(game_code.upper(), player_role, choice)

    if error:
        return jsonify({'error': error}), 400

    return jsonify({
        'success': True,
        'round': round_result
    })


@bp.route('/game/<game_code>/play-again', methods=['POST'])
def play_again(game_code):
    """Start a new game (play again)."""
    if 'session_id' not in session:
        return jsonify({'error': 'Invalid session'}), 401

    # Get current game
    old_game = Game.get_by_code(game_code.upper())
    if not old_game:
        return jsonify({'error': 'Game not found'}), 404

    # Check if user is host
    if old_game['host_session_id'] != session['session_id']:
        return jsonify({'error': 'Only host can start new game'}), 403

    # Create new game with same settings
    new_game, error = GameService.create_game(old_game['best_of'], session['session_id'])

    if error:
        return jsonify({'error': error}), 400

    return jsonify({
        'success': True,
        'game_code': new_game['game_code']
    })
