CREATE TABLE IF NOT EXISTS collector_state (
    collector_name TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    gameweek INTEGER,
    seconds_remaining INTEGER,
    message TEXT
);
