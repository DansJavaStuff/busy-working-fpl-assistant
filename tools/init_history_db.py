from history_store import (
    database_status,
    ensure_database,
)


def main():
    path = ensure_database()
    status = database_status()

    print(
        "Historical data store ready"
    )
    print(
        f"Database: {path}"
    )
    print(
        "Schema version: "
        f"{status['schema_version']}"
    )


if __name__ == "__main__":
    main()
