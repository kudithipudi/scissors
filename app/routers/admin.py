"""Admin routes for the application."""
import secrets

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import settings
from app.models import Game, Round, Statistics
from app.templating import templates

router = APIRouter()


def _is_admin(request: Request) -> bool:
    """Check the session for an authenticated admin."""
    return bool(request.session.get("is_admin"))


def require_admin(request: Request) -> bool:
    """Require an authenticated admin session for protected actions."""
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized — log in at /admin/login")
    return True


@router.get("/login", name="admin_login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the admin login form."""
    if _is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "admin_login.html", {"error": False})


@router.post("/login", name="admin_login_submit", response_class=HTMLResponse)
async def login_submit(request: Request):
    """Check the admin password and start a session."""
    form = await request.form()
    password = (form.get("password") or "").strip()
    if secrets.compare_digest(password, settings.ADMIN_PASSWORD):
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request, "admin_login.html", {"error": True}, status_code=401
    )


@router.post("/logout", name="admin_logout")
async def logout(request: Request):
    """Clear the admin session."""
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@router.get("/", name="admin_dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Admin dashboard."""
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
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