"""Create the tables in a new, empty database."""

import sys
from pathlib import Path

from database import connect

DB_FOLDER = Path(__file__).parent / "db"


def main():
    with connect() as connection:
        exists = connection.execute("SELECT to_regclass('public.groups')").fetchone()[0]

    if exists:
        print("The tables already exist. Nothing changed.")
        return 0

    with connect(autocommit=True) as connection:
        for filename in ("schema.sql", "002_fuzzy_search.sql"):
            connection.execute((DB_FOLDER / filename).read_text(encoding="utf-8"))

    print("Created the tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
