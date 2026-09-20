# Rock Paper Scissors Fix Tickets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship RPS-01 through RPS-06, RPS-10, and RPS-04 from the fix-tickets doc. RPS-07/08/09 are excluded — code inspection found their described mechanisms don't exist in the current codebase (no "Next round" button; reveal and aria-live already derive from one shared state transition), so there's nothing to fix.

**Architecture:** Small, additive changes to the existing FastAPI + aiosqlite app. No new endpoints. Extends existing service-layer methods (`GameService`, `Game`, `Round`) and the two Alpine.js pages (`index.html`, `game.html`). One schema addition (`vs_rounds.forfeited_by`) applied to the live production DB via an idempotent `ALTER TABLE` in `init_db()`, since `CREATE TABLE IF NOT EXISTS` is a no-op against the already-created table.

**Tech Stack:** FastAPI, aiosqlite (SQLite, WAL mode), Jinja2 + Alpine.js 3.14.9, pytest + pytest-asyncio + httpx `AsyncClient`.

**Spec:** the ticket doc pasted into this session (RPS-01 through RPS-10), plus two decisions made before planning:
- RPS-04 ships with suggested defaults: 120s one-sided-inactivity round forfeit, measured from the round's existing `created_at` (no new timer column needed). A forfeited round counts as a normal round win for `calculate_game_winner`, so match-end falls out of the existing win-threshold logic — no separate "2 forfeits = match loss" rule.
- RPS-03's endpoint-level expiry guard is paired with an `expires_at` renewal: whenever a game goes active or a new round is created, `expires_at` is pushed forward by `GAME_TIMEOUT_MINUTES` from now. Without this, the live `GAME_TIMEOUT_MINUTES=2` setting would kill every real match mid-game once expiry is actually enforced.

## Global Constraints

- Never touch `data/scissors.db` destructively. It's the live production DB (31 real games as of 2026-09-20). Schema changes are additive and idempotent.
- Match existing code style: services return `(data, error)` tuples; routers translate `error` strings to HTTP status codes; model methods are `@staticmethod`s on plain classes over `aiosqlite`.
- Tests follow the existing patterns in `tests/`: `@patch('app.routers.api.X')` / `@patch('app.services.game_service.X')` with `AsyncMock`, the `client`/`set_session` fixtures from `tests/conftest.py`. Use `.get(...)` (not `[...]`) when reading dicts that existing tests mock only partially.
- Run `source venv/bin/activate && pytest` (or the project's configured pytest invocation) after every task; all existing tests must keep passing alongside the new ones.
- No new abstractions beyond what a task needs (YAGNI) — e.g. no generic "error code" framework; keep using the existing string-matching-in-the-router pattern already used for statuses like `"Only host can cancel the game."`.

---

### Task 1: RPS-02 — Server-side move lock-in

**Files:**
- Modify: `app/services/game_service.py` (`GameService.submit_choice`, ~line 178-256)
- Modify: `app/routers/api.py` (`submit_choice` handler, ~line 108-133)
- Test: `tests/test_game_service.py` (`TestSubmitChoice`)
- Test: `tests/test_api.py` (`TestChoiceAPI`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `GameService.submit_choice` now returns `(None, "Choice already locked")` when the calling player already has a non-null choice for the current round. `api.submit_choice` maps that exact string to HTTP 409; every other error string still maps to 400 (unchanged).

- [ ] **Step 1: Write the failing service-layer test**

```python
# tests/test_game_service.py, inside class TestSubmitChoice
    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_submit_choice_already_locked(self, mock_round, mock_game):
        """A player who already locked a choice this round can't overwrite it."""
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id', 'status': 'active', 'best_of': 3
        })
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {'id': 'round-id', 'round_number': 1, 'host_choice': 'rock', 'guest_choice': None}
        ])
        mock_round.set_choice = AsyncMock()

        result, error = await GameService.submit_choice('ABC123', 'host', 'paper')

        assert result is None
        assert error == "Choice already locked"
        mock_round.set_choice.assert_not_called()
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `pytest tests/test_game_service.py::TestSubmitChoice::test_submit_choice_already_locked -v`
Expected: FAIL — `mock_round.set_choice` gets called (current code overwrites), or `error` is `None`.

- [ ] **Step 3: Add the lock-in guard**

In `app/services/game_service.py`, inside `submit_choice`, right after `current_round = rounds[-1]` and the existing "round already completed" guard, before `await Round.set_choice(...)`:

```python
        current_round = rounds[-1]

        # Guard: if this round is already completed, don't process again
        if current_round.get('winner') is not None or current_round.get('completed_at'):
            return current_round, None

        # Guard: don't let a second submission overwrite this player's
        # already-locked choice for this round.
        if current_round.get(f'{player}_choice') is not None:
            return None, "Choice already locked"

        # Set choice
        await Round.set_choice(current_round['id'], player, choice)
```

- [ ] **Step 4: Run it, confirm it passes**

Run: `pytest tests/test_game_service.py::TestSubmitChoice -v`
Expected: PASS (all `TestSubmitChoice` tests, including the new one).

- [ ] **Step 5: Write the failing API-layer test**

```python
# tests/test_api.py, inside class TestChoiceAPI
    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_submit_choice_already_locked(self, mock_game, mock_service, client, set_session):
        """Test double-submitting a choice returns 409, not 400."""
        set_session(client, session_id='host-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id',
                'status': 'active',
                'host_session_id': 'host-id',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.get_player_role.return_value = 'host'

        async def fake_submit_choice(code, role, choice):
            return None, "Choice already locked"
        mock_service.submit_choice = fake_submit_choice

        response = await client.post(
            '/api/game/ABC123/choice',
            json={'choice': 'paper'}
        )

        assert response.status_code == 409
        assert response.json()['error'] == "Choice already locked"
```

- [ ] **Step 6: Run it, confirm it fails**

Run: `pytest tests/test_api.py::TestChoiceAPI::test_submit_choice_already_locked -v`
Expected: FAIL — current code returns 400 for every error.

- [ ] **Step 7: Map the error to 409 in the router**

In `app/routers/api.py`, `submit_choice` handler:

```python
    round_result, error = await GameService.submit_choice(game_code.upper(), player_role, choice)

    if error:
        status_code = 409 if error == "Choice already locked" else 400
        return JSONResponse({'error': error}, status_code=status_code)
```

- [ ] **Step 8: Run it, confirm it passes**

Run: `pytest tests/test_api.py::TestChoiceAPI -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/services/game_service.py app/routers/api.py tests/test_game_service.py tests/test_api.py
git commit -m "$(cat <<'EOF'
Enforce move lock-in server-side (RPS-02)

A player resubmitting a choice mid-round silently overwrote their first
move. Reject a second submission with 409 instead of letting it stand.
EOF
)"
```

---

### Task 2: RPS-10 — Exclude expired active games from the active-game count

**Files:**
- Modify: `app/models.py` (`Statistics.get_active_game_count`, ~line 245-253)
- Test: `tests/test_integration.py` or a new focused test in `tests/test_api.py` (`TestStatsAPI`) — use the real DB via the `app`/`client` fixtures since this is a query-shape change, not something worth mocking around.

**Interfaces:**
- Consumes: nothing new.
- Produces: `Statistics.get_active_game_count()` now excludes rows where `expires_at` has already passed, even if `status` is still `'waiting'` or `'active'` (the periodic sweeper only cleans up `'waiting'` rows — see `app/utils/scheduler.py` — so stale `'active'` rows currently inflate this count).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py, inside class TestStatsAPI
    async def test_active_count_excludes_expired_active_games(self, client):
        """An 'active' game whose expires_at has passed shouldn't count as active
        — only the 'waiting' sweeper (app/utils/scheduler.py) cleans up status,
        so a stale active game must be excluded by the count query itself."""
        from datetime import datetime, timedelta, timezone
        from app.models import Game, Round

        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

        stale = await Game.create('STALE1', 3, 'host-a', timeout_minutes=2)
        await Game.update(stale['id'], {'expires_at': past, 'status': 'active', 'guest_session_id': 'guest-a'})

        fresh = await Game.create('FRESH1', 3, 'host-b', timeout_minutes=2)
        await Game.update(fresh['id'], {'expires_at': future, 'status': 'active', 'guest_session_id': 'guest-b'})

        response = await client.get('/api/stats')

        assert response.status_code == 200
        assert response.json()['active_games'] == 1
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `pytest tests/test_api.py::TestStatsAPI::test_active_count_excludes_expired_active_games -v`
Expected: FAIL — count is 2, not 1.

- [ ] **Step 3: Fix the query**

In `app/models.py`, `Statistics.get_active_game_count`:

```python
    @staticmethod
    async def get_active_game_count() -> int:
        """Get active game count — excludes rows whose expires_at has already
        passed. The periodic sweeper (app/utils/scheduler.py) only cleans up
        'waiting' rows, so a stale 'active' game can otherwise sit in this
        count indefinitely; filtering here is cheaper and always correct."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS c FROM vs_games"
                " WHERE status IN ('waiting', 'active') AND expires_at >= ?",
                (now_iso(),),
            )
            row = await cursor.fetchone()
        return row['c'] if row else 0
```

- [ ] **Step 4: Run it, confirm it passes**

Run: `pytest tests/test_api.py::TestStatsAPI -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_api.py
git commit -m "$(cat <<'EOF'
Exclude expired active games from the active-game count (RPS-10)

cleanup_expired() only sweeps 'waiting' games, so a stalled 'active'
game (no periodic cleanup) inflated /api/stats indefinitely. Filter by
expires_at in the count query itself instead of relying on the sweeper.
EOF
)"
```

---

### Task 3: RPS-03 — Enforce `expires_at`, with renewal so real matches don't die mid-game

**Files:**
- Modify: `app/models.py` (add `Game.renew_expiry`)
- Modify: `app/services/game_service.py` (add `GameService.is_expired`, `_parse_iso`; wire expiry into `join_game`; extract `_advance_after_round` from `submit_choice` and renew expiry there)
- Modify: `app/routers/api.py` (`get_game_state`, `submit_choice`, `play_again` handlers)
- Modify: `app/routers/game.py` (`join_game` handler)
- Test: `tests/test_game_service.py`, `tests/test_api.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `GameService.is_expired(game: dict) -> bool` — pure function, used by every router below.
  - `Game.renew_expiry(game_id: str, timeout_minutes: int) -> dict` — pushes `expires_at` to `now + timeout_minutes`.
  - `GameService.join_game` returns `(None, "Game expired.")` for an expired room (checked before the existing status/occupancy checks).
  - `GameService._advance_after_round(game_code: str) -> None` — shared tail of "a round just completed": re-fetch game, check for match completion, else ensure the next round exists and renew `expires_at`, then publish. Task 6 (RPS-04) reuses this exact method.

- [ ] **Step 1: Write the failing service tests**

```python
# tests/test_game_service.py — new class
class TestExpiry:
    """Test expiry helpers."""

    def test_is_expired_true_when_past(self):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        assert GameService.is_expired({'expires_at': past}) is True

    def test_is_expired_false_when_future(self):
        from datetime import datetime, timedelta, timezone
        future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
        assert GameService.is_expired({'expires_at': future}) is False

    def test_is_expired_false_when_missing(self):
        assert GameService.is_expired({}) is False


class TestJoinGameExpiry:
    @patch('app.services.game_service.Game')
    async def test_join_expired_game(self, mock_game):
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        mock_game.get_by_code = AsyncMock(return_value={
            'id': 'game-id', 'status': 'waiting', 'host_session_id': 'host-id',
            'guest_session_id': None, 'expires_at': past,
        })

        game, error = await GameService.join_game('ABC123', 'guest-id')

        assert game is None
        assert error == "Game expired."
```

- [ ] **Step 2: Run, confirm failure**

Run: `pytest tests/test_game_service.py::TestExpiry tests/test_game_service.py::TestJoinGameExpiry -v`
Expected: FAIL — `GameService.is_expired` doesn't exist yet; `join_game` doesn't check expiry.

- [ ] **Step 3: Add `is_expired` / `_parse_iso` and wire the `join_game` check**

In `app/services/game_service.py`, add the import and helpers near the top, and the check inside `join_game`:

```python
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
```

```python
def _parse_iso(timestamp: Optional[str]):
    """Parse an ISO-8601 timestamp (as produced by app.db.now_iso) into an
    aware UTC datetime, or None if missing/unparseable."""
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
```

Inside the `GameService` class, alongside the other `@staticmethod`s:

```python
    @staticmethod
    def is_expired(game: Dict[str, Any]) -> bool:
        """Whether this game's room has passed its expires_at."""
        expires = _parse_iso(game.get('expires_at'))
        return expires is not None and datetime.now(timezone.utc) > expires
```

In `join_game`, right after the "Game not found." check:

```python
        game = await Game.get_by_code(game_code)
        if not game:
            return None, "Game not found."

        if GameService.is_expired(game):
            return None, "Game expired."

        # Check game status
```

- [ ] **Step 4: Run, confirm pass**

Run: `pytest tests/test_game_service.py::TestExpiry tests/test_game_service.py::TestJoinGameExpiry -v`
Expected: PASS.

- [ ] **Step 5: Add `Game.renew_expiry` and extract `_advance_after_round`**

In `app/models.py`, add alongside `Game.complete_game`:

```python
    @staticmethod
    async def renew_expiry(game_id: str, timeout_minutes: int) -> Optional[Dict[str, Any]]:
        """Push expires_at forward from now. Called on genuine round
        activity (a new round starting) so an actively-played match never
        hits the abandonment timeout mid-game — only a truly idle room
        does."""
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)).isoformat()
        return await Game.update(game_id, {'expires_at': expires_at})
```

In `app/services/game_service.py`, replace the tail of `submit_choice` (everything from `if host_choice and guest_choice:` through the final `return updated_round, None`) with a call to a new shared method:

```python
        if host_choice and guest_choice:
            # Guard: re-check if round was already completed by concurrent request
            if updated_round.get('winner') is not None or updated_round.get('completed_at'):
                return updated_round, None

            # Determine round winner
            winner = determine_winner(host_choice, guest_choice)
            await Round.complete_round(updated_round['id'], winner)
            await GameService._advance_after_round(game_code)
            return updated_round, None

        return updated_round, None

    @staticmethod
    async def _advance_after_round(game_code: str) -> None:
        """Shared tail of round resolution (normal completion or a lazy
        forfeit — see resolve_forfeits): re-fetch the game, check whether
        the match is won, else ensure the next round exists and renew the
        game's expiry, then publish. Published last so a client that
        refetches on this event always sees the settled state."""
        game = await Game.get_by_code(game_code)
        if game['status'] == 'completed':
            game_events.publish(game_code, {"type": "state"})
            return

        all_rounds = await Round.get_all_by_game(game['id'])
        game_winner = calculate_game_winner(all_rounds, game['best_of'])

        if game_winner:
            await Game.complete_game(game['id'], game_winner)
        else:
            has_pending_round = any(
                r.get('winner') is None and not r.get('completed_at')
                for r in all_rounds
            )
            if not has_pending_round:
                next_round_number = max(r['round_number'] for r in all_rounds) + 1
                await Round.create(game['id'], next_round_number)
                await Game.renew_expiry(game['id'], settings.GAME_TIMEOUT_MINUTES)

        game_events.publish(game_code, {"type": "state"})
```

Also renew expiry when a game goes active. In `join_game`, after the successful join:

```python
        # Join game
        updated_game = await Game.join_game(game['id'], guest_session_id)

        if not updated_game:
            return None, "Failed to join game."

        updated_game = await Game.renew_expiry(updated_game['id'], settings.GAME_TIMEOUT_MINUTES)
```

- [ ] **Step 6: Run the full existing suite to confirm the refactor didn't change behavior**

Run: `pytest tests/test_game_service.py -v`
Expected: PASS — `TestSubmitChoice::test_submit_choice_both_players_determines_winner` and friends behave identically; only the code location moved.

- [ ] **Step 7: Write the failing router-level expiry tests**

```python
# tests/test_api.py, inside TestGameStateAPI
    @patch('app.routers.api.GameService')
    async def test_get_game_state_expired(self, mock_service, client):
        """Test getting state of an expired game returns 410."""
        async def fake_get_game_state(code):
            from datetime import datetime, timedelta, timezone
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            return {
                'game': {'id': 'game-id', 'status': 'active', 'expires_at': past},
                'rounds': [],
                'current_round': 1,
            }
        mock_service.get_game_state = fake_get_game_state
        mock_service.is_expired = GameService.is_expired

        response = await client.get('/api/game/ABC123/state')

        assert response.status_code == 410
        assert response.json() == {'error': 'Game expired', 'status': 'expired'}
```

```python
# tests/test_api.py, inside TestChoiceAPI
    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_submit_choice_expired(self, mock_game, mock_service, client, set_session):
        """Test submitting a choice to an expired game returns 410."""
        from datetime import datetime, timedelta, timezone
        set_session(client, session_id='host-id')
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

        async def fake_get_by_code(code):
            return {'id': 'game-id', 'status': 'active', 'host_session_id': 'host-id', 'expires_at': past}
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_expired = GameService.is_expired

        response = await client.post('/api/game/ABC123/choice', json={'choice': 'rock'})

        assert response.status_code == 410
        assert response.json() == {'error': 'Game expired', 'status': 'expired'}
        mock_service.submit_choice.assert_not_called()
```

```python
# tests/test_api.py, inside TestPlayAgainAPI
    @patch('app.routers.api.GameService')
    @patch('app.routers.api.Game')
    async def test_play_again_expired(self, mock_game, mock_service, client, set_session):
        """Test starting a rematch from an expired game returns 410."""
        from datetime import datetime, timedelta, timezone
        set_session(client, session_id='host-id')
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

        async def fake_get_by_code(code):
            return {'id': 'old-game-id', 'status': 'completed', 'best_of': 3, 'host_session_id': 'host-id', 'expires_at': past}
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_expired = GameService.is_expired

        response = await client.post('/api/game/ABC123/play-again')

        assert response.status_code == 410
        mock_service.create_game.assert_not_called()
```

```python
# tests/test_routes.py, inside TestViewGameRoute — join-route expiry
class TestJoinGameRoute:
    @patch('app.routers.game.GameService')
    async def test_join_expired_game(self, mock_service, client, set_session):
        set_session(client, session_id='guest-id')

        async def fake_join_game(code, session_id):
            return None, "Game expired."
        mock_service.join_game = fake_join_game

        response = await client.post('/game/ABC123/join')

        assert response.status_code == 410
        assert response.json() == {'error': 'Game expired', 'status': 'expired'}
```

- [ ] **Step 8: Run, confirm failure**

Run: `pytest tests/test_api.py tests/test_routes.py -v -k expired`
Expected: FAIL — routers don't check expiry yet, and don't special-case `"Game expired."`.

- [ ] **Step 9: Add the router-level guards**

In `app/routers/api.py`, `get_game_state`:

```python
@router.get("/game/{game_code}/state", name="api_game_state")
async def get_game_state(request: Request, game_code: str):
    """Get current game state."""
    state = await GameService.get_game_state(game_code.upper())

    if not state:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    if GameService.is_expired(state['game']):
        return JSONResponse({'error': 'Game expired', 'status': 'expired'}, status_code=410)

    # Don't reveal opponent's choice until both have chosen
```

In `submit_choice`, right after the "Game not found" check:

```python
    game = await Game.get_by_code(game_code.upper())
    if not game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    if GameService.is_expired(game):
        return JSONResponse({'error': 'Game expired', 'status': 'expired'}, status_code=410)

    player_role = GameService.get_player_role(game, request.session['session_id'])
```

In `play_again`, right after the "Game not found" check:

```python
    old_game = await Game.get_by_code(game_code.upper())
    if not old_game:
        return JSONResponse({'error': 'Game not found'}, status_code=404)

    if GameService.is_expired(old_game):
        return JSONResponse({'error': 'Game expired', 'status': 'expired'}, status_code=410)

    if old_game['host_session_id'] != request.session['session_id']:
```

In `app/routers/game.py`, `join_game` handler, map the new error string:

```python
    game, error = await GameService.join_game(game_code.upper(), request.session['session_id'])

    if error == "Game expired.":
        return JSONResponse({'error': 'Game expired', 'status': 'expired'}, status_code=410)
    if error:
        return JSONResponse({'error': error}, status_code=400)
```

- [ ] **Step 10: Run, confirm pass**

Run: `pytest tests/test_api.py tests/test_routes.py -v`
Expected: PASS — full files, not just `-k expired`, to catch any regressions.

- [ ] **Step 11: Commit**

```bash
git add app/models.py app/services/game_service.py app/routers/api.py app/routers/game.py tests/test_game_service.py tests/test_api.py tests/test_routes.py
git commit -m "$(cat <<'EOF'
Enforce expires_at on room-scoped endpoints, with renewal (RPS-03)

state/choice/play-again/join now return 410 once a room's expires_at has
passed, instead of silently continuing to serve/mutate a dead room.

Paired with expiry renewal: expires_at is pushed forward whenever a game
goes active or a new round starts. Without this, the live
GAME_TIMEOUT_MINUTES=2 setting would kill every real multi-round match
mid-game now that expiry is actually enforced — previously nothing
enforced it on active games, which was the bug.
EOF
)"
```

---

### Task 4: RPS-05 + RPS-06 — `view_game` route: friendly full-room and cancelled handling

**Files:**
- Modify: `app/routers/game.py` (`view_game`, ~line 71-127)
- Modify: `app/templates/error.html` (accept an optional `game_code` for the 404 cleanup script — reused by Task 5 too)
- Test: `tests/test_routes.py` (`TestViewGameRoute`)

**Interfaces:**
- Consumes: `GameService.is_expired` (Task 3), `GameService.join_game`'s existing error strings including the new `"Game expired."` and the reordered `"Room is full."`.
- Produces: `view_game` never returns a bare 403 for a full or cancelled room. Cancelled rooms render the existing `game.html` cancelled block (already present client-side) for any viewer, host or stranger, at 200. A full room gets a 409 friendly page. An expired room gets a 410 friendly page.

- [ ] **Step 1: Reorder `join_game`'s occupancy check ahead of the generic status check**

In `app/services/game_service.py`, `join_game`, swap the order so "full" is detected specifically instead of being masked by the generic status message:

```python
        if GameService.is_expired(game):
            return None, "Game expired."

        # Check if game is full (checked before the generic status check so
        # a full room gets a specific, actionable error instead of the
        # generic "Game is active. Cannot join.")
        if game.get('guest_session_id'):
            return None, "Room is full."

        # Check game status
        if game['status'] != 'waiting':
            return None, f"Game is {game['status']}. Cannot join."

        # Check if user is the host
        if game['host_session_id'] == guest_session_id:
            return None, "You are the host. Cannot join as guest."
```

- [ ] **Step 2: Write the failing service test**

```python
# tests/test_game_service.py, inside class TestJoinGame
    @patch('app.services.game_service.Game')
    async def test_join_full_game(self, mock_game):
        """Test joining a game that already has two players."""
        mock_game.get_by_code = AsyncMock(return_value={
            'status': 'active',
            'host_session_id': 'host-id',
            'guest_session_id': 'other-guest',
        })

        game, error = await GameService.join_game('ABC123', 'guest-id')

        assert game is None
        assert error == "Room is full."
```

- [ ] **Step 3: Run, confirm pass (this test also validates Step 1)**

Run: `pytest tests/test_game_service.py::TestJoinGame -v`
Expected: PASS for the whole class, including the existing `test_join_active_game` (still hits the generic status branch, since it has no `guest_session_id` set) and the new full-room test.

- [ ] **Step 4: Restructure `view_game`**

In `app/routers/game.py`, replace the body of `view_game` from the `game = await Game.get_by_code(...)` line through the `qr_code` block's start:

```python
@router.get("/game/{game_code}", name="view_game", response_class=HTMLResponse)
async def view_game(request: Request, game_code: str):
    """View game page."""
    if 'session_id' not in request.session:
        request.session['session_id'] = str(uuid.uuid4())

    code = game_code.upper()
    game = await Game.get_by_code(code)

    if not game:
        return templates.TemplateResponse(
            request, "error.html",
            {"error_code": 404, "message": "Game not found", "game_code": code},
            status_code=404,
        )

    if GameService.is_expired(game):
        return templates.TemplateResponse(
            request, "error.html",
            {"error_code": 410, "message": "This game has expired", "game_code": code},
            status_code=410,
        )

    session_id = request.session['session_id']
    is_player = GameService.is_player_in_game(game, session_id)
    player_role = GameService.get_player_role(game, session_id)

    # A cancelled room is informational, not an error — anyone with the
    # link (host, guest, or a stranger) can see it closed. game.html
    # already has a client-side 'cancelled' UI block for this.
    if game['status'] == 'cancelled':
        return templates.TemplateResponse(
            request, "game.html",
            {
                "game": game,
                "player_role": player_role,
                "qr_code": None,
                "join_url": None,
                "vs_computer": game.get('guest_session_id') == COMPUTER_PLAYER_ID,
                "shake_threshold": settings.SHAKE_THRESHOLD,
                "shake_timeout_ms": settings.SHAKE_TIMEOUT_MS,
                "required_shakes": settings.REQUIRED_SHAKES,
            },
        )

    # If game is waiting and user is not in game, they can join
    if game['status'] == 'waiting' and not is_player:
        updated_game, error = await GameService.join_game(code, session_id)
        if error == "Room is full.":
            return templates.TemplateResponse(
                request, "error.html",
                {"error_code": 409, "message": "This room already has two players.", "game_code": code},
                status_code=409,
            )
        if error:
            return templates.TemplateResponse(
                request, "error.html", {"error_code": 400, "message": error}, status_code=400
            )
        game = updated_game
        player_role = 'guest'
        is_player = True

    if not is_player:
        if game.get('host_session_id') and game.get('guest_session_id'):
            return templates.TemplateResponse(
                request, "error.html",
                {"error_code": 409, "message": "This room already has two players.", "game_code": code},
                status_code=409,
            )
        return templates.TemplateResponse(
            request, "error.html", {"error_code": 403, "message": "You are not a player in this game"}, status_code=403
        )
```

The rest of the function (QR generation and the final `TemplateResponse` for the normal case) is unchanged, except `game_code.upper()` calls further down should use the already-computed `code` variable for consistency — leave any remaining ones as `game_code.upper()` if touching them isn't necessary for this task; don't do a drive-by rename beyond what's already being edited.

- [ ] **Step 5: Add `game_code` handling to `error.html`**

In `app/templates/error.html`, add a script block that clears a stale rejoin entry when this 404 is specifically "Game not found" for a code the user just tried:

```html
{% block content %}
<div class="card text-center" style="max-width: 600px; margin: 0 auto;">
    <div class="card-body">
        <h1 style="font-size: 4rem; color: var(--color-danger);">{{ error_code }}</h1>
        <h2>{{ message }}</h2>
        <p class="text-muted">
            {% if error_code == 404 %}
            The page you're looking for doesn't exist.
            {% elif error_code == 403 %}
            You don't have permission to access this resource.
            {% elif error_code == 409 %}
            {% elif error_code == 410 %}
            {% else %}
            Something went wrong on our end. Please try again later.
            {% endif %}
        </p>
        <a href="{{ url_for('index') }}" class="btn btn-primary btn-lg mt-2">Go Home</a>
    </div>
</div>
{% if game_code %}
<script>
    // Stop inviting a rejoin into a room that turned out not to exist,
    // expired, or filled up before this page could join it.
    try {
        if (localStorage.getItem('rps-last-game') === '{{ game_code }}') {
            localStorage.removeItem('rps-last-game');
        }
    } catch (e) { /* private mode */ }
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Write the failing route tests**

```python
# tests/test_routes.py, inside TestViewGameRoute
    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_view_game_full_room_third_session(self, mock_game, mock_service, client, set_session):
        """A stranger opening an already-full active room gets a friendly 409, not a bare 403."""
        set_session(client, session_id='stranger-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id', 'game_code': 'ABC123', 'status': 'active',
                'host_session_id': 'host-id', 'guest_session_id': 'guest-id', 'best_of': 3,
                'expires_at': '2099-01-01T00:00:00+00:00',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_expired = GameService.is_expired
        mock_service.is_player_in_game.return_value = False
        mock_service.get_player_role.return_value = None

        response = await client.get('/game/ABC123')

        assert response.status_code == 409
        assert b'already has two players' in response.content

    @patch('app.routers.game.GameService')
    @patch('app.routers.game.Game')
    async def test_view_game_cancelled_room_any_viewer(self, mock_game, mock_service, client, set_session):
        """A cancelled room renders the friendly cancelled screen, never a 403 — even for a stranger."""
        set_session(client, session_id='stranger-id')

        async def fake_get_by_code(code):
            return {
                'id': 'game-id', 'game_code': 'ABC123', 'status': 'cancelled',
                'host_session_id': 'host-id', 'guest_session_id': 'guest-id', 'best_of': 3,
                'expires_at': '2099-01-01T00:00:00+00:00',
            }
        mock_game.get_by_code = fake_get_by_code
        mock_service.is_expired = GameService.is_expired
        mock_service.is_player_in_game.return_value = False
        mock_service.get_player_role.return_value = None

        response = await client.get('/game/ABC123')

        assert response.status_code == 200
        assert b'Game Cancelled' in response.content

    @patch('app.routers.game.Game')
    async def test_view_game_not_found_clears_rejoin(self, mock_game, client):
        """A 404 game page carries the code so the client can clear a stale rejoin entry."""
        async def fake_get_by_code(code):
            return None
        mock_game.get_by_code = fake_get_by_code

        response = await client.get('/game/ZZZZZZ')

        assert response.status_code == 404
        assert b"localStorage.getItem('rps-last-game') === 'ZZZZZZ'" in response.content
```

- [ ] **Step 7: Run, confirm failure then fix iteratively**

Run: `pytest tests/test_routes.py::TestViewGameRoute -v`
Expected: the three new tests FAIL before Steps 4-5, then PASS after.

- [ ] **Step 8: Run the full route + service suites**

Run: `pytest tests/test_routes.py tests/test_game_service.py -v`
Expected: PASS, including pre-existing tests like `test_view_game_not_found` (still 404) and `test_view_game_as_host` / `test_view_game_auto_join` (unaffected — still take the normal path).

- [ ] **Step 9: Commit**

```bash
git add app/routers/game.py app/templates/error.html tests/test_routes.py tests/test_game_service.py
git commit -m "$(cat <<'EOF'
Friendly full-room and cancelled-room handling on the game page (RPS-05, RPS-06)

A third session opening an already-full room got a bare 403 with no
explanation; a cancelled room 403'd even though its state API already
returned 200 + status:cancelled. Both now render the game page's
existing friendly UI (409 for full, 200 for cancelled) instead of a
generic permission error, for any viewer, not just recognized players.
EOF
)"
```

---

### Task 5: RPS-01 — Validate join code before navigating

**Files:**
- Modify: `app/templates/index.html` (`joinGame()`, ~line 330-349)
- Test: `tests/test_routes.py` (`TestIndexRoute`) — the join flow itself is client-side JS with no server round-trip to unit-test directly; verify the rendered page wires the right endpoint, and rely on Task 4's `view_game`/`error.html` tests for the server side of "invalid code" behavior. Add one focused test asserting the state-check fetch is present in the rendered script.

**Interfaces:**
- Consumes: the existing `GET /api/game/{code}/state` endpoint (already returns 404 for an unknown code — see `app/routers/api.py::get_game_state`).
- Produces: `joinGame()` no longer writes to `localStorage` or navigates until the state check confirms the room exists.

- [ ] **Step 1: Update `joinGame()`**

In `app/templates/index.html`, replace the `joinGame` method:

```javascript
            async joinGame() {
                const code = (this.gameCode || '').toUpperCase().trim();
                if (!code) {
                    this.codeError = 'Please enter a game code';
                    return;
                }
                if (code.length !== 6) {
                    this.codeError = 'Codes are exactly 6 characters';
                    return;
                }

                if (window.Effects) Effects.play('lock');
                this.loading = true;
                try {
                    const stateUrl = '{{ url_for("api_game_state", game_code="PLACEHOLDER") }}'.replace('PLACEHOLDER', code);
                    const response = await fetch(stateUrl);

                    if (response.status === 404) {
                        this.codeError = 'Room not found — check the code and try again.';
                        return;
                    }
                    if (!response.ok) {
                        this.codeError = 'Could not check that code — try again.';
                        return;
                    }

                    try { localStorage.setItem('rps-last-game', code); } catch (e) {}
                    window.location.href = '{{ url_for("view_game", game_code="PLACEHOLDER") }}'.replace('PLACEHOLDER', code);
                } catch (error) {
                    this.codeError = 'Network error. Please try again.';
                } finally {
                    this.loading = false;
                }
            }
```

Note this drops the previous `setTimeout(() => { this.loading = false; }, 2000)` hack (it existed only because the old code navigated away immediately without ever awaiting anything, so `loading` had to be force-reset after a fixed delay) — the `finally` block now does that naturally since there's a real `await` to finish.

- [ ] **Step 2: Write the test**

```python
# tests/test_routes.py, inside class TestIndexRoute
    async def test_join_flow_validates_via_state_endpoint(self, client):
        """The Join form must check room existence via the state API before
        navigating, instead of blindly navigating on any 6-character code."""
        response = await client.get('/')
        assert response.status_code == 200
        assert b"fetch(stateUrl)" in response.content
        assert b"Room not found" in response.content
```

- [ ] **Step 3: Run, confirm pass**

Run: `pytest tests/test_routes.py::TestIndexRoute -v`
Expected: PASS.

- [ ] **Step 4: Manual verification (this is client JS with no server round-trip in the test suite)**

Run: use the `run` skill (or manually start the dev server per project convention) and in a browser: enter `ZZZZZZ` in Join and submit. Confirm: stays on the Join screen, shows "Room not found — check the code and try again.", and `localStorage.getItem('rps-last-game')` is unchanged. Then join a real game code end-to-end and confirm it still navigates normally.

- [ ] **Step 5: Commit**

```bash
git add app/templates/index.html tests/test_routes.py
git commit -m "$(cat <<'EOF'
Validate join code via the state API before navigating (RPS-01)

Joining with a bogus code used to navigate straight to a generic 404
and persist the bad code for "Rejoin your last game". Check
/api/game/{code}/state first; only persist and navigate on success.
EOF
)"
```

---

### Task 6: RPS-04 — Abandonment forfeit (120s one-sided inactivity)

**Files:**
- Modify: `db/schema.sql` (`vs_rounds` gets `forfeited_by`)
- Modify: `app/db.py` (idempotent migration for the live DB)
- Modify: `app/models.py` (`_ROUND_COLUMNS`, new `Round.forfeit`)
- Modify: `app/services/game_service.py` (new `resolve_forfeits`, wire into `get_game_state`)
- Modify: `app/templates/game.html` (surface forfeit in the reveal, and fix the reveal-trigger condition so a forfeited round — where the idle player's choice stays `null` forever — still triggers the reveal for the player who's waiting)
- Test: `tests/test_helpers.py` or a new `tests/test_db.py` for the migration; `tests/test_game_service.py` for forfeit resolution.

**Interfaces:**
- Consumes: `GameService._advance_after_round` (Task 3).
- Produces: `Round.forfeit(round_id, winner, forfeited_by) -> dict`. `GameService.resolve_forfeits(game_code, game, rounds) -> list[dict]` — lazily forfeits the current round if exactly one player has moved and the round has been open more than 120s, then returns the (possibly refreshed) rounds list. `GameService.get_game_state` calls this on every read, so any poll can trigger resolution — no separate sweeper needed. A forfeited round's `winner` is set exactly like a normal round win, so `calculate_game_winner` and `_advance_after_round` need no changes to reach match completion via forfeits.

- [ ] **Step 1: Add the schema column**

In `db/schema.sql`, `vs_rounds`:

```sql
CREATE TABLE IF NOT EXISTS vs_rounds (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES vs_games(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    host_choice TEXT CHECK (host_choice IN ('rock', 'paper', 'scissors')),
    guest_choice TEXT CHECK (guest_choice IN ('rock', 'paper', 'scissors')),
    host_shakes INTEGER NOT NULL DEFAULT 0 CHECK (host_shakes >= 0 AND host_shakes <= 3),
    guest_shakes INTEGER NOT NULL DEFAULT 0 CHECK (guest_shakes >= 0 AND guest_shakes <= 3),
    winner TEXT CHECK (winner IN ('host', 'guest', 'tie')),
    forfeited_by TEXT CHECK (forfeited_by IN ('host', 'guest')),
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

- [ ] **Step 2: Write the failing migration test**

```python
# tests/test_db.py (new file)
"""Test idempotent schema migrations against a pre-existing (old-schema) DB."""
import aiosqlite
import pytest

from app.config import settings
from app.db import init_db


OLD_SCHEMA = """
CREATE TABLE vs_games (
    id TEXT PRIMARY KEY, game_code TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
    best_of INTEGER NOT NULL, host_session_id TEXT NOT NULL, guest_session_id TEXT,
    winner TEXT, created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
    expires_at TEXT NOT NULL
);
CREATE TABLE vs_rounds (
    id TEXT PRIMARY KEY, game_id TEXT NOT NULL, round_number INTEGER NOT NULL,
    host_choice TEXT, guest_choice TEXT, host_shakes INTEGER NOT NULL DEFAULT 0,
    guest_shakes INTEGER NOT NULL DEFAULT 0, winner TEXT,
    created_at TEXT NOT NULL, completed_at TEXT
);
"""


async def test_init_db_adds_forfeited_by_to_existing_table(tmp_path):
    """A DB created before forfeited_by existed must get it added in place —
    CREATE TABLE IF NOT EXISTS is a no-op against an already-created table."""
    db_path = tmp_path / 'legacy.db'
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(OLD_SCHEMA)
        await conn.commit()

    settings.DB_PATH = str(db_path)
    await init_db()

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA table_info(vs_rounds)")
        columns = {row[1] for row in await cursor.fetchall()}

    assert 'forfeited_by' in columns
```

- [ ] **Step 3: Run, confirm failure**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `init_db()` doesn't migrate yet.

- [ ] **Step 4: Add the idempotent migration**

In `app/db.py`:

```python
async def init_db() -> None:
    """Create the data directory and apply the schema (idempotent)."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.executescript(SCHEMA_PATH.read_text())
        await _migrate_schema(conn)
        await conn.commit()


async def _migrate_schema(conn: aiosqlite.Connection) -> None:
    """Idempotent ALTER TABLE additions for columns introduced after the
    initial schema. CREATE TABLE IF NOT EXISTS above is a no-op against an
    already-created table, so a new column needs an explicit, guarded ALTER
    — this runs on every startup and is a no-op once the column exists."""
    cursor = await conn.execute("PRAGMA table_info(vs_rounds)")
    columns = {row[1] for row in await cursor.fetchall()}
    if 'forfeited_by' not in columns:
        await conn.execute(
            "ALTER TABLE vs_rounds ADD COLUMN forfeited_by TEXT"
            " CHECK (forfeited_by IN ('host', 'guest'))"
        )
```

- [ ] **Step 5: Run, confirm pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 6: Add `Round.forfeit` and whitelist the column**

In `app/models.py`, add `'forfeited_by'` to `_ROUND_COLUMNS`:

```python
_ROUND_COLUMNS = {
    'game_id', 'round_number', 'host_choice', 'guest_choice', 'host_shakes',
    'guest_shakes', 'winner', 'forfeited_by', 'created_at', 'completed_at',
}
```

Add the method next to `Round.complete_round`:

```python
    @staticmethod
    async def forfeit(round_id: str, winner: str, forfeited_by: str) -> Optional[Dict[str, Any]]:
        """Complete a round via inactivity forfeit. `winner` is set exactly
        like a normal round win so calculate_game_winner treats it the same."""
        updates = {
            'winner': winner,
            'forfeited_by': forfeited_by,
            'completed_at': now_iso(),
        }
        return await Round.update(round_id, updates)
```

- [ ] **Step 7: Write the failing forfeit-resolution tests**

```python
# tests/test_game_service.py — new class
class TestResolveForfeits:
    """Test lazy round-forfeit resolution (RPS-04)."""

    @patch('app.services.game_service.game_events')
    @patch('app.services.game_service.Game')
    @patch('app.services.game_service.Round')
    async def test_forfeits_stale_one_sided_round(self, mock_round, mock_game, mock_events):
        """One player moved, the other never did, 120s+ have passed: the
        round is forfeited to the player who moved."""
        from datetime import datetime, timedelta, timezone
        stale = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()

        game = {'id': 'game-id', 'status': 'active', 'best_of': 3}
        rounds = [{
            'id': 'round-id', 'round_number': 1, 'host_choice': 'rock',
            'guest_choice': None, 'winner': None, 'completed_at': None,
            'created_at': stale,
        }]

        mock_round.forfeit = AsyncMock()
        mock_round.get_all_by_game = AsyncMock(return_value=[
            {**rounds[0], 'winner': 'host', 'completed_at': 'now', 'forfeited_by': 'guest'}
        ])
        mock_game.get_by_code = AsyncMock(return_value=game)

        result = await GameService.resolve_forfeits('ABC123', game, rounds)

        mock_round.forfeit.assert_called_once_with('round-id', 'host', 'guest')
        assert result[-1]['forfeited_by'] == 'guest'

    @patch('app.services.game_service.Round')
    async def test_no_forfeit_when_round_is_fresh(self, mock_round):
        """Under the 120s deadline, nothing happens."""
        from datetime import datetime, timezone
        fresh = datetime.now(timezone.utc).isoformat()
        game = {'id': 'game-id', 'status': 'active', 'best_of': 3}
        rounds = [{
            'id': 'round-id', 'round_number': 1, 'host_choice': 'rock',
            'guest_choice': None, 'winner': None, 'completed_at': None,
            'created_at': fresh,
        }]

        result = await GameService.resolve_forfeits('ABC123', game, rounds)

        mock_round.forfeit.assert_not_called()
        assert result == rounds

    @patch('app.services.game_service.Round')
    async def test_no_forfeit_when_neither_or_both_moved(self, mock_round):
        from datetime import datetime, timedelta, timezone
        stale = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
        game = {'id': 'game-id', 'status': 'active', 'best_of': 3}

        neither = [{
            'id': 'r1', 'round_number': 1, 'host_choice': None, 'guest_choice': None,
            'winner': None, 'completed_at': None, 'created_at': stale,
        }]
        both = [{
            'id': 'r1', 'round_number': 1, 'host_choice': 'rock', 'guest_choice': 'paper',
            'winner': None, 'completed_at': None, 'created_at': stale,
        }]

        assert await GameService.resolve_forfeits('ABC123', game, neither) == neither
        assert await GameService.resolve_forfeits('ABC123', game, both) == both
        mock_round.forfeit.assert_not_called()
```

- [ ] **Step 8: Run, confirm failure**

Run: `pytest tests/test_game_service.py::TestResolveForfeits -v`
Expected: FAIL — `resolve_forfeits` doesn't exist yet.

- [ ] **Step 9: Implement `resolve_forfeits` and wire it into `get_game_state`**

In `app/services/game_service.py`, add the constant near the top:

```python
# One-sided inactivity: if only one player has moved and this many seconds
# have passed since the round started, the idle player forfeits the round.
# Measured from the round's created_at (round start) rather than a separate
# "first choice" timestamp, to avoid a schema column purely for this.
FORFEIT_DEADLINE_SECONDS = 120
```

Add the method:

```python
    @staticmethod
    async def resolve_forfeits(game_code: str, game: Dict[str, Any], rounds: list) -> list:
        """Lazily forfeit a stalled round: called on every get_game_state
        read (i.e. every poll), so no separate sweeper is needed — see
        FORFEIT_DEADLINE_SECONDS. If only one player has moved and the round
        has been open past the deadline, award it to the player who moved,
        exactly like a normal round win, and run the same advance-or-complete
        logic a normal completion uses."""
        if not rounds or game.get('status') != 'active':
            return rounds

        current = rounds[-1]
        if current.get('winner') is not None or current.get('completed_at'):
            return rounds

        host_choice = current.get('host_choice')
        guest_choice = current.get('guest_choice')
        if bool(host_choice) == bool(guest_choice):
            return rounds  # neither moved, or both moved (resolves normally)

        started = _parse_iso(current.get('created_at'))
        if started is None:
            return rounds
        age_seconds = (datetime.now(timezone.utc) - started).total_seconds()
        if age_seconds < FORFEIT_DEADLINE_SECONDS:
            return rounds

        winner, forfeited_by = ('host', 'guest') if host_choice else ('guest', 'host')
        await Round.forfeit(current['id'], winner, forfeited_by)
        await GameService._advance_after_round(game_code)

        return await Round.get_all_by_game(game['id'])
```

Wire it into `get_game_state`:

```python
    @staticmethod
    async def get_game_state(game_code: str) -> Optional[Dict[str, Any]]:
        """Get full game state including rounds."""
        game = await Game.get_by_code(game_code)
        if not game:
            return None

        rounds = await Round.get_all_by_game(game['id'])
        rounds = await GameService.resolve_forfeits(game_code, game, rounds)
        game = await Game.get_by_code(game_code)  # may have changed: a forfeit can end the match

        decisive_rounds = sum(1 for r in rounds if r.get('winner') in ('host', 'guest'))

        return {
            'game': game,
            'rounds': rounds,
            'current_round': min(decisive_rounds + 1, game['best_of'])
        }
```

- [ ] **Step 10: Run, confirm pass**

Run: `pytest tests/test_game_service.py -v`
Expected: PASS — the new `TestResolveForfeits` class and everything else, including `TestGetGameState` (re-check: those tests mock `Game.get_by_code` and `Round.get_all_by_game` with fixed `AsyncMock(return_value=...)`, so the extra calls this method now makes return the same fixed values — harmless).

- [ ] **Step 11: Surface forfeits client-side and fix the reveal trigger**

In `app/templates/game.html`, `applyState`, broaden the reveal trigger so a forfeited round (where the idle player's choice is `null` forever) still surfaces — the round is done once `completed_at` is set, whether both players chose or one forfeited:

```javascript
                if (this.awaitingOpponent && state.rounds) {
                    const round = state.rounds.find(r => r.round_number === this.currentRound);
                    if (round && round.completed_at) {
                        this.awaitingOpponent = false;
                        if (this.opponentPoll) {
                            clearInterval(this.opponentPoll);
                            this.opponentPoll = null;
                        }
                        this.showRoundResult(round, state);
                    }
                }
```

In `showRoundResult`, distinguish a forfeit from a normal result:

```javascript
            showRoundResult(round, state) {
                this.opponentChoice = this.playerRole === 'host' ? round.guest_choice : round.host_choice;

                if (round.winner === this.playerRole) this.roundWinner = 'you';
                else if (round.winner === 'tie') this.roundWinner = 'tie';
                else this.roundWinner = 'opponent';

                if (round.forfeited_by) {
                    const iForfeited = round.forfeited_by === this.playerRole;
                    this.roundResultText = iForfeited
                        ? '⏱️ You forfeited this round (inactivity)'
                        : '⏱️ Opponent forfeited the round';
                } else {
                    this.roundResultText =
                        this.roundWinner === 'you' ? '🎉 You win the round!' :
                        this.roundWinner === 'opponent' ? '😬 Opponent takes it' : '🤝 It\'s a draw';
                }
```

- [ ] **Step 12: Full-suite regression run**

Run: `pytest -v`
Expected: PASS, full suite.

- [ ] **Step 13: Commit**

```bash
git add db/schema.sql app/db.py app/models.py app/services/game_service.py app/templates/game.html tests/test_db.py tests/test_game_service.py
git commit -m "$(cat <<'EOF'
Add abandonment-timeout round forfeit (RPS-04)

A game with one idle player stayed active and unresolved indefinitely.
If only one player has moved and the round has been open 120s+, the
idle player now forfeits the round on the next state poll (lazy
resolution — no separate sweeper) — a forfeit counts as a normal round
win, so match completion falls out of the existing win-threshold logic.

Adds vs_rounds.forfeited_by via an idempotent ALTER TABLE in init_db(),
since CREATE TABLE IF NOT EXISTS is a no-op against the already-created
production table.
EOF
)"
```

---

### Task 7: Full regression pass and live-service sanity check

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

Run: `pytest -v`
Expected: all tests PASS (pre-existing + all tests added in Tasks 1-6).

- [ ] **Step 2: Confirm the live DB migration is safe to apply**

Run (read-only inspection, do not run against the live DB destructively):
```bash
sqlite3 data/scissors.db "PRAGMA table_info(vs_rounds);"
```
Expected: before restart, `forfeited_by` is absent. After the service restarts (which calls `init_db()`), re-run the same command and confirm `forfeited_by` is now present and the row count of `vs_games`/`vs_rounds` is unchanged (`SELECT COUNT(*) FROM vs_games;` / `SELECT COUNT(*) FROM vs_rounds;`) before and after.

- [ ] **Step 3: Manual smoke test of the join flow (RPS-01) and full/cancelled room pages (RPS-05/06)**

Per the `run` skill or the project's normal dev-server startup: play one solo best-of-1 game end to end; try joining a nonexistent code; try opening a completed two-player game's URL from a third, unrelated session; cancel a waiting game and reload its URL as a stranger session. Confirm each matches its ticket's acceptance criteria.

- [ ] **Step 4: Report back**

Summarize to the user: which tickets shipped (RPS-01, 02, 03, 04, 05, 06, 10), which were skipped and why (RPS-07, 08, 09 — not reproducible against current code), and flag that the live DB schema migration will apply automatically the next time the service restarts.
