-- Rock Paper Scissors SQLite schema
-- All tables prefixed with vs_ (vs = versus/scissors)
-- Applied idempotently on startup (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS vs_games (
    id TEXT PRIMARY KEY,
    game_code TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('waiting', 'active', 'completed', 'cancelled')),
    best_of INTEGER NOT NULL CHECK (best_of IN (1, 3, 5)),
    host_session_id TEXT NOT NULL,
    guest_session_id TEXT,
    winner TEXT CHECK (winner IN ('host', 'guest', 'tie')),
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vs_rounds (
    id TEXT PRIMARY KEY,
    game_id TEXT NOT NULL REFERENCES vs_games(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    host_choice TEXT CHECK (host_choice IN ('rock', 'paper', 'scissors')),
    guest_choice TEXT CHECK (guest_choice IN ('rock', 'paper', 'scissors')),
    host_shakes INTEGER NOT NULL DEFAULT 0 CHECK (host_shakes >= 0 AND host_shakes <= 3),
    guest_shakes INTEGER NOT NULL DEFAULT 0 CHECK (guest_shakes >= 0 AND guest_shakes <= 3),
    winner TEXT CHECK (winner IN ('host', 'guest', 'tie')),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- Indexes for performance (mirrors the original Postgres/Supabase schema)
CREATE INDEX IF NOT EXISTS idx_vs_games_status ON vs_games(status);
CREATE INDEX IF NOT EXISTS idx_vs_games_game_code ON vs_games(game_code);
CREATE INDEX IF NOT EXISTS idx_vs_games_created_at ON vs_games(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vs_games_expires_at ON vs_games(expires_at);
CREATE INDEX IF NOT EXISTS idx_vs_rounds_game_id ON vs_rounds(game_id);
CREATE INDEX IF NOT EXISTS idx_vs_rounds_game_round ON vs_rounds(game_id, round_number);
