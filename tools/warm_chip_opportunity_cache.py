from chip_planner import (
    build_chip_opportunity,
)


def main():
    result = build_chip_opportunity()

    cache = result.get(
        "cache",
        {},
    )

    print(
        "Chip opportunity cache ready."
    )
    print(
        "Cache hit:",
        cache.get(
            "hit",
            False,
        ),
    )


if __name__ == "__main__":
    main()
