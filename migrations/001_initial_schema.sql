-- Rock Paper Scissors Database Schema
-- All tables prefixed with vs_ (vs = versus/scissors)

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Games table
CREATE TABLE vs_games (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_code VARCHAR(8) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('waiting', 'active', 'completed', 'cancelled')),
    best_of INTEGER NOT NULL CHECK (best_of IN (1, 3, 5)),
    host_session_id VARCHAR(255) NOT NULL,
    guest_session_id VARCHAR(255),
    winner VARCHAR(10) CHECK (winner IN ('host', 'guest', 'tie')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Rounds table
CREATE TABLE vs_rounds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id UUID REFERENCES vs_games(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    host_choice VARCHAR(10) CHECK (host_choice IN ('rock', 'paper', 'scissors')),
    guest_choice VARCHAR(10) CHECK (guest_choice IN ('rock', 'paper', 'scissors')),
    host_shakes INTEGER DEFAULT 0 CHECK (host_shakes >= 0 AND host_shakes <= 3),
    guest_shakes INTEGER DEFAULT 0 CHECK (guest_shakes >= 0 AND guest_shakes <= 3),
    winner VARCHAR(10) CHECK (winner IN ('host', 'guest', 'tie')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_vs_games_status ON vs_games(status);
CREATE INDEX idx_vs_games_game_code ON vs_games(game_code);
CREATE INDEX idx_vs_games_created_at ON vs_games(created_at DESC);
CREATE INDEX idx_vs_games_expires_at ON vs_games(expires_at);
CREATE INDEX idx_vs_rounds_game_id ON vs_rounds(game_id);
CREATE INDEX idx_vs_rounds_game_round ON vs_rounds(game_id, round_number);

-- Comments for documentation
COMMENT ON TABLE vs_games IS 'Stores rock-paper-scissors game sessions';
COMMENT ON TABLE vs_rounds IS 'Stores individual rounds within games';
COMMENT ON COLUMN vs_games.game_code IS 'Unique 6-8 character code for joining games';
COMMENT ON COLUMN vs_games.status IS 'Game status: waiting, active, completed, or cancelled';
COMMENT ON COLUMN vs_games.best_of IS 'Number of rounds needed to win: 1, 3, or 5';
COMMENT ON COLUMN vs_games.expires_at IS 'When waiting games expire and get cancelled';
COMMENT ON COLUMN vs_rounds.host_shakes IS 'Number of shakes detected for host (0-3)';
COMMENT ON COLUMN vs_rounds.guest_shakes IS 'Number of shakes detected for guest (0-3)';
