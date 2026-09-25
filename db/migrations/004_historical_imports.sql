ALTER TABLE teams
ADD COLUMN strength INTEGER;

ALTER TABLE teams
ADD COLUMN strength_overall_home INTEGER;

ALTER TABLE teams
ADD COLUMN strength_overall_away INTEGER;

ALTER TABLE teams
ADD COLUMN strength_attack_home INTEGER;

ALTER TABLE teams
ADD COLUMN strength_attack_away INTEGER;

ALTER TABLE teams
ADD COLUMN strength_defence_home INTEGER;

ALTER TABLE teams
ADD COLUMN strength_defence_away INTEGER;

CREATE TABLE IF NOT EXISTS historical_imports (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL,
    source_repo TEXT NOT NULL,
    requested_ref TEXT NOT NULL,
    resolved_commit TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    files_json TEXT NOT NULL,
    FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    UNIQUE (
        season_id,
        source_repo,
        resolved_commit
    )
);

CREATE INDEX IF NOT EXISTS idx_historical_imports_season
ON historical_imports (
    season_id,
    imported_at
);
