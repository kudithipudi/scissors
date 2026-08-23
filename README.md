# Rock Paper Scissors - Real-time Multiplayer Game

## What it is

A real-time multiplayer Rock Paper Scissors web app with phone shake
detection (gyroscope). One player hosts a game and shares a code or QR
code; the other joins from their phone. Both players shake to make a
choice (or use the manual fallback buttons), and the app plays out a
best-of-1/3/5 match with live polling for game state.

## Stack

- **Backend**: FastAPI (async), served by Gunicorn + `uvicorn.workers.UvicornWorker`
- **Database**: SQLite (`data/scissors.db`), accessed via `aiosqlite`, WAL mode
- **Frontend**: Jinja2 templates, Alpine.js (vendored at `app/static/js/alpine.min.js`, pinned 3.14.9), custom CSS
- **Deviation from lab standard**: hand-rolled CSS instead of Tailwind — kept its existing visual identity per the lab's UI standard for purposefully-styled apps; migration to the standard Tailwind standalone-CLI setup is deferred
- **Sessions**: Starlette `SessionMiddleware` (signed cookie, itsdangerous)
- **Background jobs**: APScheduler (`AsyncIOScheduler`) — cleans up expired "waiting" games every minute
- **QR codes**: `qrcode` + Pillow, generated on the fly (no external storage)
- **Tests**: pytest + pytest-asyncio + httpx `ASGITransport`/`AsyncClient`

Previously Flask + gevent + Supabase (Postgres via PostgREST); migrated to
FastAPI + SQLite (see Migration notes below).

## Architecture

```
/var/www/scissors/
├── app/
│   ├── main.py               # FastAPI app, middleware, routers, error handlers
│   ├── config.py              # pydantic-settings Settings, reads .env
│   ├── db.py                   # aiosqlite connection helper + schema init
│   ├── models.py               # Game / Round / Statistics (raw SQL)
│   ├── templating.py           # Jinja2Templates + ROOT_PATH-aware url_for()
│   ├── routers/
│   │   ├── game.py             # Page routes: index, create/view/cancel/join game
│   │   ├── api.py              # JSON API: stats, game state, shake, choice, play-again
│   │   └── admin.py            # HTTP Basic-protected admin dashboard + JSON endpoints
│   ├── services/
│   │   ├── game_service.py     # Core game rules (round/game winner logic)
│   │   └── qr_service.py       # QR code + join URL generation
│   ├── utils/
│   │   ├── helpers.py          # Game code gen, winner logic, formatting
│   │   ├── rate_limit.py       # SQLite sliding-window rate limiter (game creation)
│   │   └── scheduler.py        # APScheduler setup (expired-game cleanup)
│   ├── static/                 # css/, js/ (shake.js, admin.js, alpine.min.js), images/
│   ├── logs/                   # access.log + app.log at runtime (.gitkeep tracked)
│   └── templates/              # base.html + page templates
├── data/                        # scissors.db (gitignored, www-data writable)
├── db/schema.sql                 # canonical SQLite schema (checked in)
├── tests/                        # pytest suite (77 tests)
├── gunicorn.conf.py
├── requirements.txt              # fully pinned
├── .env / .env.example
└── .gitignore
```

## Run locally

```bash
cd /var/www/scissors
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # then edit SECRET_KEY / ADMIN_PASSWORD

# Dev server (auto-reload)
venv/bin/uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/`. The SQLite DB is created automatically
(schema applied idempotently) at `data/scissors.db` on first startup.

### Run tests

```bash
venv/bin/python -m pytest
```

91 tests cover routes, the API, game logic, rate limiting, security
headers, device/shake detection behavior, and a full integration game
flow against a real (throwaway) SQLite database per test.
## Deploy

Runs under Gunicorn (`gunicorn.conf.py`, 1 `UvicornWorker`) bound to a unix
socket, managed by systemd (`scissors.service`), reverse-proxied by nginx
at `https://lab.kudithipudi.org/scissors/` (nginx strips the `/scissors`
prefix before proxying; `app/templating.py` puts it back for outgoing links).

```bash
sudo systemctl restart scissors
sudo systemctl status scissors
curl -s -o /dev/null -w '%{http_code}' https://lab.kudithipudi.org/scissors/   # -> 200
curl -s https://lab.kudithipudi.org/scissors/health                            # -> {"status":"ok"}
```

## Logs

Files under `app/logs/`, not journald:

- `app/logs/access.log` — gunicorn access log (one line per HTTP request)
- `app/logs/app.log` — gunicorn error/boot log plus app output via `logging`

Set `LOG_LEVEL=debug` in `.env` to flip verbosity without code changes.

## Env vars

| Var | Purpose | Default |
|---|---|---|
| `APP_NAME` | App display name (OpenAPI title) | `Rock Paper Scissors` |
| `ROOT_PATH` | URL prefix this app is mounted under (used to build browser-facing links; nginx already strips it from incoming paths) | `/scissors` |
| `DEBUG` | Debug flag | `false` |
| `SECRET_KEY` | Session cookie signing key | dev placeholder — **set a real one in prod** |
| `SESSION_COOKIE_SECURE` | Require HTTPS for the session cookie | `true` |
| `SESSION_COOKIE_MAX_AGE` | Session cookie lifetime, seconds | `86400` (24 h) |
| `DB_PATH` | Path to the SQLite database file | `data/scissors.db` |
| `ADMIN_PASSWORD` | Password for `/admin/*` (HTTP Basic; any username accepted) | dev placeholder — **set a real one in prod** |
| `GAME_TIMEOUT_MINUTES` | Minutes before an unjoined "waiting" game expires | `2` |
| `MAX_GAMES_PER_IP_PER_HOUR` | Game-creation rate limit per client IP (sliding window, honors `X-Forwarded-For`) | `10` |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit sliding window length, seconds | `3600` |
| `SHAKE_THRESHOLD` | Accelerometer magnitude (m/s²) counted as a shake | `15` |
| `REQUIRED_SHAKES` | Shakes needed to lock in a choice | `3` |
| `SHAKE_TIMEOUT_MS` | Window to complete the required shakes, ms | `2000` |
| `QR_BOX_SIZE` | QR code box size (px per module) | `10` |
| `QR_BORDER` | QR code border (modules) | `4` |
| `LOG_LEVEL` | App + gunicorn log level (`debug`/`info`/...) | `info` |

## Game flow

1. **Host creates a game** — picks best of 1/3/5, gets a game code + QR code, waits for a guest.
2. **Guest joins** via QR code or game code — game becomes "active".
3. **Gameplay** — both players pick a move: tap ✊/✋/✌️ (or keyboard `1/2/3`, `R/P/S` on desktop) for a deliberate choice, or shake the phone 3× to let fate pick at random. Choices are revealed once both are in; round winner is computed server-side.
4. **Game completion** — once one side reaches the required round wins, the game is marked "completed"; the host can start a rematch with the same settings.

Background cleanup (APScheduler, every minute) cancels "waiting" games
that expired before a guest joined.

## Security & reliability

- **Rate limiting** — game creation (`/game/create` and the "play again"
  endpoint) is limited to `MAX_GAMES_PER_IP_PER_HOUR` games per IP per
  `RATE_LIMIT_WINDOW_SECONDS` (sliding window, SQLite-backed). Returns `429`.
- **Security headers** — every response carries `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  strict-origin-when-cross-origin`, and a locked-down `Permissions-Policy`
  that still allows `accelerometer`/`gyroscope`/`magnetometer` for the app's
  own origin so shake detection keeps working.
- **SQLite concurrency** — connections set `PRAGMA busy_timeout = 5000` (and
  use a 10s connect timeout) to avoid `database is locked` errors when both
  players submit around the same time.

## Admin dashboard

`https://lab.kudithipudi.org/scissors/admin/`, protected by HTTP Basic
auth using `ADMIN_PASSWORD`. Shows live stats, a filterable game list, and
per-game round detail.

## Device detection & motion sensors

Unchanged from the original design — see `app/static/js/shake.js` and the
`/device-test` / `/device-simple-test` diagnostic pages. iOS 13+ requires
an explicit user-gesture-triggered permission prompt for
`DeviceMotionEvent`; Android auto-grants. Desktop and denied/unsupported
devices fall back to tap-to-choose buttons, which are always available as
the deliberate way to play (and double as an accessibility fallback).

## UX details

- **Dark mode** — automatic via `prefers-color-scheme`; theme-color meta
  follows the scheme.
- **Sound & haptics** — tiny WebAudio-synthesized effects (no assets) plus
  vibration where supported; toggleable from the header (🔊), persisted in
  `localStorage`.
- **Confetti** — canvas confetti celebrates a match win; all motion respects
  `prefers-reduced-motion`.
- **Resilience** — a "Reconnecting…" pill appears if state polling fails
  repeatedly; the tab title tracks game status.

## Migration notes (Flask+Supabase -> FastAPI+SQLite)

- All Supabase/Postgres usage (2 tables: `vs_games`, `vs_rounds`) was
  replaced with SQLite (`db/schema.sql`), accessed via a single async
  `app/db.py` module. UUIDs are now generated in Python; timestamps are
  UTC ISO-8601 strings generated in Python (not DB defaults).
- Flask blueprints -> FastAPI `APIRouter`s; Flask sessions -> Starlette
  `SessionMiddleware` (same itsdangerous-signed-cookie approach).
  `Flask-Caching` was unused in the original code (never actually
  decorated any route) and was dropped rather than replaced.
- Gunicorn now runs a `uvicorn.workers.UvicornWorker` instead of `gevent`.
- No production Supabase data was migrated: games are short-lived by
  design (2-minute join window; completed/cancelled games aren't kept
  for anything besides admin stats), and the Supabase project's hostname
  was unreachable from this deploy host at migration time (stale/expired
  project — also the cause of recurring `cleanup_expired_games` errors in
  the old logs), so there was nothing to safely pull over.
