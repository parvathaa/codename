"""Create a database login that can read Codename's data but not change it."""

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from psycopg import sql

from database import connect

READER = "codename_reader"
OUTPUT = Path(__file__).parent / ".env.reader"


def create_reader(connection, name, password):
    role = sql.Identifier(name)
    database = sql.Identifier(connection.info.dbname)
    commands = (
        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} CONNECTION LIMIT 50").format(
            role, sql.Literal(password)
        ),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role),
        sql.SQL(
            "GRANT SELECT ON public.groups, public.aliases, public.sources, "
            "public.vendors, public.alias_vendors TO {}"
        ).format(role),
        sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(role),
        sql.SQL("ALTER ROLE {} SET statement_timeout = '5s'").format(role),
    )
    for command in commands:
        connection.execute(command)


def reader_url(owner_url, name, password):
    """Copy the owner's address, swapping in the reader's name and password."""
    parts = urlsplit(owner_url)
    server = parts.netloc.rpartition("@")[2]
    login = f"{quote(name, safe='')}:{quote(password, safe='')}"
    return urlunsplit(parts._replace(netloc=f"{login}@{server}"))


def main():
    if not os.environ.get("ENV_FILE"):
        print("Set ENV_FILE=.env.production first.")
        return 1
    if OUTPUT.exists():
        print(f"{OUTPUT.name} already exists. Nothing changed.")
        return 1

    password = secrets.token_urlsafe(32)
    with connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (READER,)
        ).fetchone()
        if exists:
            print(f"{READER} already exists. Nothing changed.")
            return 1

        create_reader(connection, READER, password)
        url = reader_url(os.environ["DATABASE_URL"], READER, password)

        # Only the owner of this computer account can read the file.
        descriptor = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(f"DATABASE_URL='{url}'\n")

    print(f"Created {READER}. Its address is in {OUTPUT.name}; keep it secret.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
