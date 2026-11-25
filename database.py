"""Connect to PostgreSQL using the settings in .env."""

import os

import psycopg
from dotenv import load_dotenv


def connect(dbname=None, **options):
    load_dotenv()
    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=dbname or os.environ["POSTGRES_DB"],
        **options,
    )
