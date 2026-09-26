CREATE TABLE IF NOT EXISTS historical_player_gameweeks (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    gameweek_id INTEGER NOT NULL,
    fpl_element_id INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT,
    team_name TEXT,
    total_points INTEGER NOT NULL DEFAULT 0,
    minutes INTEGER NOT NULL DEFAULT 0,
    starts INTEGER NOT NULL DEFAULT 0,
    value INTEGER,
    selected INTEGER,
    fixture_rows INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    source_updated_at TEXT,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    FOREIGN KEY (gameweek_id)
        REFERENCES gameweeks(id)
        ON DELETE CASCADE,
    UNIQUE (
        season_id,
        gameweek_id,
        fpl_element_id
    )
);

CREATE INDEX IF NOT EXISTS idx_historical_player_gw
ON historical_player_gameweeks (
    season_id,
    gameweek_id
);

CREATE INDEX IF NOT EXISTS idx_historical_player_element
ON historical_player_gameweeks (
    season_id,
    fpl_element_id,
    gameweek_id
);
