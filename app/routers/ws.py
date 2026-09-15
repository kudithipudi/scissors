"""WebSocket route that pushes "state changed" pokes to the two players.

This is a latency optimization layered on top of the existing polling, not a
replacement for it. The socket never carries authoritative game state: it only
tells a client "something changed, refetch", and the client re-reads
/api/game/{code}/state exactly as the poller does. If the socket never connects
or silently dies, the page keeps polling and everything still works.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models import Game
from app.services import game_events
from app.services.game_service import GameService

logger = logging.getLogger("scissors.ws")

router = APIRouter()

# Idle keepalive. Sent as a normal app-level message so intermediaries (nginx
# proxy_read_timeout) see traffic; the client ignores these.
PING_INTERVAL_SECONDS = 25

# Close code for "you are not a player in this game". 4000-4999 is the
# application-private range.
WS_CLOSE_NOT_A_PLAYER = 4403


@router.websocket("/ws/game/{game_code}", name="game_ws")
async def game_ws(websocket: WebSocket, game_code: str):
    """Subscribe a player of `game_code` to that game's change events."""
    code = game_code.upper()

    # SessionMiddleware populates .session on websocket scopes too.
    try:
        session_id = websocket.session.get('session_id')
    except (AssertionError, KeyError):  # pragma: no cover - middleware always installed
        session_id = None

    if not session_id:
        await websocket.close(code=WS_CLOSE_NOT_A_PLAYER)
        return

    game = await Game.get_by_code(code)
    if not game or not GameService.is_player_in_game(game, session_id):
        await websocket.close(code=WS_CLOSE_NOT_A_PLAYER)
        return

    await websocket.accept()
    queue = game_events.subscribe(code)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                # Idle — keepalive only, keep the loop running.
                await websocket.send_json({"type": "ping"})
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover - defensive; a dead socket is not an error
        logger.debug("game_ws loop ended for %s", code, exc_info=True)
    finally:
        game_events.unsubscribe(code, queue)
