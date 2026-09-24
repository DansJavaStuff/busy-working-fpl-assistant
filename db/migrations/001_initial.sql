CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY,
    season_key TEXT NOT NULL UNIQUE,
    starts_year INTEGER,
    ends_year INTEGER,
    source TEXT NOT NULL DEFAULT 'local',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gameweeks (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    gameweek INTEGER NOT NULL,
    deadline_time TEXT,
    finished INTEGER,
    data_checked INTEGER,
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    UNIQUE (
        season_id,
        gameweek
    )
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    fpl_team_id INTEGER,
    name TEXT NOT NULL,
    short_name TEXT,
    source TEXT NOT NULL DEFAULT 'official_fpl',
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    UNIQUE (
        season_id,
        fpl_team_id
    )
);

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    fpl_fixture_id INTEGER,
    gameweek_id INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    kickoff_time TEXT,
    home_difficulty INTEGER,
    away_difficulty INTEGER,
    home_score INTEGER,
    away_score INTEGER,
    finished INTEGER,
    source TEXT NOT NULL DEFAULT 'official_fpl',
    source_updated_at TEXT,
    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    FOREIGN KEY (gameweek_id)
        REFERENCES gameweeks(id)
        ON DELETE SET NULL,
    FOREIGN KEY (home_team_id)
        REFERENCES teams(id)
        ON DELETE SET NULL,
    FOREIGN KEY (away_team_id)
        REFERENCES teams(id)
        ON DELETE SET NULL,
    UNIQUE (
        season_id,
        fpl_fixture_id
    )
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    gameweek_id INTEGER,
    entry_id INTEGER,
    snapshot_type TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    FOREIGN KEY (gameweek_id)
        REFERENCES gameweeks(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS
idx_snapshots_lookup
ON snapshots (
    season_id,
    gameweek_id,
    snapshot_type,
    captured_at
);

CREATE TABLE IF NOT EXISTS chip_opportunities (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    gameweek_id INTEGER NOT NULL,
    chip_name TEXT NOT NULL,
    projected_value REAL NOT NULL,
    recommendation TEXT NOT NULL,
    fixture_certainty TEXT NOT NULL,
    model_confidence TEXT NOT NULL,
    model_version TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    FOREIGN KEY (gameweek_id)
        REFERENCES gameweeks(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS
idx_chip_opportunities_lookup
ON chip_opportunities (
    season_id,
    gameweek_id,
    chip_name,
    created_at
);

CREATE TABLE IF NOT EXISTS chip_outcomes (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    gameweek_id INTEGER NOT NULL,
    entry_id INTEGER,
    chip_name TEXT NOT NULL,
    actual_value REAL NOT NULL,
    benchmark_value REAL,
    incremental_value REAL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    FOREIGN KEY (gameweek_id)
        REFERENCES gameweeks(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS
idx_chip_outcomes_lookup
ON chip_outcomes (
    season_id,
    gameweek_id,
    chip_name
);
