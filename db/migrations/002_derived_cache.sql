CREATE TABLE IF NOT EXISTS derived_cache (
    namespace TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (
        namespace,
        cache_key,
        model_version
    )
);

CREATE INDEX IF NOT EXISTS idx_derived_cache_expiry
ON derived_cache (
    expires_at
);
