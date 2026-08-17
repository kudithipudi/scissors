"""Game routes for the application."""
import uuid

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.services.game_service import GameService
from app.services.qr_service import QRService
from app.models import Game
from app.templating import templates
from app.utils.rate_limit import is_rate_limited

router = APIRouter()


async def _get_json(request: Request) -> dict:
    """Parse the JSON body, mirroring Flask's request.get_json() 400 behavior."""
    try:
        return await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")


@router.get("/", name="index", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/device-test", name="device_test", response_class=HTMLResponse)
async def device_test(request: Request):
    """Device detection test page."""
    return templates.TemplateResponse(request, "device_test.html")


@router.get("/device-simple-test", name="device_simple_test", response_class=HTMLResponse)
async def device_simple_test(request: Request):
    """Simple device detection test page (no Alpine.js)."""
    return templates.TemplateResponse(request, "device_simple_test.html")


@router.post("/game/create", name="create_game")
async def create_game(request: Request):
    """Create a new game."""
    if await is_rate_limited(request):
        return JSONResponse(
            {'error': 'Too many games created from this IP. Please try again later.'},
            status_code=429,
        )

    if 'session_id' not in request.session:
        request.session['session_id'] = str(uuid.uuid4())

    data = await _get_json(request)
    best_of = data.get('best_of', 3)

    game, error = await GameService.create_game(best_of, request.session['session_id'])

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {
        'success': True,
        'game_code': game['game_code'],
        'game_id': game['id'],
    }


@router.get("/game/{game_code}", name="view_game", response_class=HTMLResponse)
async def view_game(request: Request, game_code: str):
    """View game page."""
    if 'session_id' not in request.session:
        request.session['session_id'] = str(uuid.uuid4())

    game = await Game.get_by_code(game_code.upper())

    if not game:
        return templates.TemplateResponse(
            request, "error.html", {"error_code": 404, "message": "Game not found"}, status_code=404
        )

    session_id = request.session['session_id']
    is_player = GameService.is_player_in_game(game, session_id)
    player_role = GameService.get_player_role(game, session_id)

    # If game is waiting and user is not in game, they can join
    if game['status'] == 'waiting' and not is_player:
        if not game.get('guest_session_id'):
            updated_game, error = await GameService.join_game(game_code.upper(), session_id)
            if error:
                return templates.TemplateResponse(
                    request, "error.html", {"error_code": 400, "message": error}, status_code=400
                )
            game = updated_game
            player_role = 'guest'
            is_player = True

    if not is_player:
        return templates.TemplateResponse(
            request, "error.html", {"error_code": 403, "message": "You are not a player in this game"}, status_code=403
        )

    # Generate QR code if host and waiting
    qr_code = None
    join_url = None
    if game['status'] == 'waiting' and player_role == 'host':
        qr_code = QRService.generate_qr_code(request, game_code.upper())
        join_url = QRService.get_join_url(request, game_code.upper())

    return templates.TemplateResponse(
        request,
        "game.html",
        {
            "game": game,
            "player_role": player_role,
            "qr_code": qr_code,
            "join_url": join_url,
        },
    )


@router.post("/game/{game_code}/cancel", name="cancel_game")
async def cancel_game(request: Request, game_code: str):
    """Cancel a game."""
    if 'session_id' not in request.session:
        return JSONResponse({'error': 'Invalid session'}, status_code=401)

    success, error = await GameService.cancel_game(game_code.upper(), request.session['session_id'])

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {'success': True}


@router.post("/game/{game_code}/join", name="join_game")
async def join_game(request: Request, game_code: str):
    """Join a game as guest."""
    if 'session_id' not in request.session:
        request.session['session_id'] = str(uuid.uuid4())

    game, error = await GameService.join_game(game_code.upper(), request.session['session_id'])

    if error:
        return JSONResponse({'error': error}, status_code=400)

    return {
        'success': True,
        'game': game,
    }
