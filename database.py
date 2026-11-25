"""Connect to PostgreSQL, on this computer or online."""

import os

import certifi
import psycopg
from dotenv import load_dotenv


def connect(dbname=None, **options):
    # ENV_FILE chooses a different settings file, such as .env.production.
    load_dotenv(os.environ.get("ENV_FILE"))

    url = os.environ.get("DATABASE_URL")
    if url:
        # An online database must use encryption and prove who it is.
        return psycopg.connect(
            url,
            sslmode="verify-full",
            sslrootcert=certifi.where(),
            connect_timeout=10,
            **options,
        )

    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=5432,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=dbname or os.environ["POSTGRES_DB"],
        **options,
    )
