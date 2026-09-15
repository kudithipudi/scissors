"""API routes for real-time game operations."""
import time

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.services import game_events
from app.services.game_service import GameService, COMPUTER_PLAYER_ID
from app.models import Game, Statistics
from app.utils.rate_limit import is_rate_limited

router = APIRouter()

# Reactions are ephemeral cosmetics: never stored, only fanned out over the
# game's WebSocket channel. Fixed allowlist so the channel can't be used to
# push arbitrary text at the other player.
ALLOWED_REACTIONS = {"😤", "😂", "👀", "🔥", "😱", "🤝"}

# In-memory anti-spam guard, (game_code, player_role) -> last send monotonic ts.
# Not persisted and not a security control (one worker, ephemeral games) —
# just enough to stop a player hammering the button.
REACTION_COOLDOWN_SECONDS = 2.0
_last_reaction: dict = {}


def _reaction_rate_limited(game_code: str, player_role: str) -> bool:
    """Return True if this player reacted too recently; records the send if not."""
    key = (game_code, player_role)
    now = time.monotonic()
    last = _last_reaction.get(key)
    if last is not None and (now - last) < REACTION_COOLDOWN_SECONDS:
        return True
    _last_reaction[key] = now

    # Opportunistic cleanup so finished games don't accumulate forever.
    if len(_last_reaction) > 512:
        cutoff = now - 600
        for stale in [k for k, v in _last_reaction.items() if v < cutoff]:
            _last_reaction.pop(stale, None)
    return False


async def _get_json(request: Request) -> dict:
    """Parse the JSON body, mirroring Flask's request.get_json() 400 behavior."""
    try:
        return await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")


@router.get("/stats", name="api_stats")
async def get_stats():
    """Get public statistics."""
    return {
        'active_games': await Statistics.get_active_game_count(),
        'total_games': await Statistics.get_game_count(),
    }


@router.get("/game/{game_code}/state", name="api_game_state")
async def get_game_state(request: Request, game_code: str):
    """Get current game state."""
    state = await GameService.get_game_state(game_code.upper())

    if not state:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    # Don't reveal opponent's choice until both have chosen
    session_id = request.session.get('session_id')
    if session_id:
        player_role = GameService.get_player_role(state['game'], session_id)
        if player_role and state['rounds']:
            current_round = state['rounds'][-1]
            if not current_round.get('completed_at'):
                if player_role == 'host' and current_round.get('guest_choice'):
                    state['rounds'][-1]['guest_choice'] = None
                elif player_role == 'guest' and current_round.get('host_choice'):
                    state['rounds'][-1]['host_choice'] = None

    return state


@router.post("/game/{game_code}/shake", name="api_record_shake")
async def record_shake(request: Request, game_code: str):
    """Record shake count for player."""
    if 'session_id' not in request.session:
        return JSONResponse({'error': 'Invalid session'}, status_code=401)

    data = await _get_json(request)
    shake_count = data.get('shake_count', 0)

    game = await Game.get_by_code(game_code.upper())
    if not game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    player_role = GameService.get_player_role(game, request.session['session_id'])
    if not player_role:
        return JSONResponse({'error': 'Not a player in this game'}, status_code=403)

    success, error = await GameService.record_shake(game_code.upper(), player_role, shake_count)

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {'success': True, 'shake_count': shake_count}


@router.post("/game/{game_code}/choice", name="api_submit_choice")
async def submit_choice(request: Request, game_code: str):
    """Submit player choice."""
    if 'session_id' not in request.session:
        return JSONResponse({'error': 'Invalid session'}, status_code=401)

    data = await _get_json(request)
    choice = data.get('choice')

    game = await Game.get_by_code(game_code.upper())
    if not game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    player_role = GameService.get_player_role(game, request.session['session_id'])
    if not player_role:
        return JSONResponse({'error': 'Not a player in this game'}, status_code=403)

    round_result, error = await GameService.submit_choice(game_code.upper(), player_role, choice)

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {
        'success': True,
        'round': round_result,
    }


@router.post("/game/{game_code}/react", name="api_react")
async def react(request: Request, game_code: str):
    """Send an ephemeral emoji reaction to the other player.

    Nothing is written to the database — the reaction is fanned out over the
    game's WebSocket channel and forgotten.
    """
    if 'session_id' not in request.session:
        return JSONResponse({'error': 'Invalid session'}, status_code=401)

    data = await _get_json(request)
    emoji = data.get('emoji')

    if emoji not in ALLOWED_REACTIONS:
        return JSONResponse({'error': 'Invalid reaction'}, status_code=400)

    code = game_code.upper()
    game = await Game.get_by_code(code)
    if not game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    player_role = GameService.get_player_role(game, request.session['session_id'])
    if not player_role:
        return JSONResponse({'error': 'Not a player in this game'}, status_code=403)

    if _reaction_rate_limited(code, player_role):
        return JSONResponse({'error': 'Slow down a little'}, status_code=429)

    game_events.publish(code, {'type': 'reaction', 'from': player_role, 'emoji': emoji})

    return {'success': True}


@router.post("/game/{game_code}/play-again", name="api_play_again")
async def play_again(request: Request, game_code: str):
    """Start a new game (play again)."""
    if 'session_id' not in request.session:
        return JSONResponse({'error': 'Invalid session'}, status_code=401)

    if await is_rate_limited(request):
        return JSONResponse(
            {'error': 'Too many games created from this IP. Please try again later.'},
            status_code=429,
        )

    old_game = await Game.get_by_code(game_code.upper())
    if not old_game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    if old_game['host_session_id'] != request.session['session_id']:
        return JSONResponse({'error': 'Only host can start new game'}, status_code=403)

    vs_computer = old_game.get('guest_session_id') == COMPUTER_PLAYER_ID
    new_game, error = await GameService.create_game(
        old_game['best_of'], request.session['session_id'], vs_computer=vs_computer
    )

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {
        'success': True,
        'game_code': new_game['game_code'],
    }
