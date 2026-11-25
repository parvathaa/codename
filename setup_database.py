"""Create or update the tables. Safe to run again."""

import sys
from pathlib import Path

from database import connect

DB_FOLDER = Path(__file__).parent / "db"


def update_tables(connection):
    """Run the SQL files that are needed, in order. Returns their names."""
    files = sorted(DB_FOLDER.glob("[0-9]*.sql"))
    exists = connection.execute("SELECT to_regclass('public.groups')").fetchone()[0]
    if exists:
        files = [file for file in files if not file.name.startswith("001_")]

    for file in files:
        connection.execute(file.read_text(encoding="utf-8"))
    return [file.name for file in files]


def main():
    with connect(autocommit=True) as connection:
        for name in update_tables(connection):
            print(f"Applied {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
