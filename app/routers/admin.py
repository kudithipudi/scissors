"""Admin routes for the application."""
import secrets

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings
from app.models import Game, Round, Statistics
from app.templating import templates

router = APIRouter()
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """Require the admin password (username is ignored, matching prior behavior)."""
    if not secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Admin Access Required"'},
        )
    return True


@router.get("/", name="admin_dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _: bool = Depends(require_admin)):
    """Admin dashboard."""
    return templates.TemplateResponse(request, "admin.html")


@router.get("/games", name="admin_list_games")
async def list_games(
    status: str | None = None,
    limit: int = Query(100),
    offset: int = Query(0),
    _: bool = Depends(require_admin),
):
    """List all games with filters."""
    games = await Game.get_all_with_filters(status, limit, offset)

    return {
        'success': True,
        'games': games,
    }


@router.get("/game/{game_id}", name="admin_view_game")
async def view_game(game_id: str, _: bool = Depends(require_admin)):
    """View game details."""
    game = await Game.get_by_id(game_id)

    if not game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    rounds = await Round.get_all_by_game(game_id)

    return {
        'success': True,
        'game': game,
        'rounds': rounds,
    }


@router.get("/stats", name="admin_stats")
async def get_stats(_: bool = Depends(require_admin)):
    """Get admin statistics."""
    stats = {
        'total_games': await Statistics.get_game_count(),
        'active_games': await Statistics.get_active_game_count(),
        'completed_games': await Statistics.get_completed_game_count(),
        'game_modes': await Statistics.get_game_mode_stats(),
    }

    return {
        'success': True,
        'stats': stats,
    }
