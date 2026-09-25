# Historical reference data

This directory is reserved for small, curated historical/reference datasets that should travel with the repository.

Large raw downloads, API snapshots, generated SQLite databases and disposable caches should not be committed here. Runtime historical data belongs under `data/runtime/` and is excluded from Git.

Where possible, committed reference data should be accompanied by the importer or derivation script used to reproduce it and a note describing its source and capture date.


## Historical FPL source

Historical fixture/team imports use the public `vaastav/Fantasy-Premier-League` dataset. The importer records the exact upstream commit used for each import instead of committing the downloaded CSV files here.

The upstream project's requested attribution should be retained in documentation if historical analysis is published or exposed outside this personal assistant.
