"""Copy MITRE ATT&CK groups and their names into PostgreSQL."""

import os
import re
import sys

import psycopg
from dotenv import load_dotenv

from lookup import DATA_FILE, load_groups, normalize


def connect():
    """Open a database connection using the settings in .env."""
    load_dotenv()
    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def clean_text(text):
    """Remove citation markers and turn [text](link) into plain text."""
    text = re.sub(r"\(Citation: [^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,\n])", r"\1", text)
    return text.strip()


def mitre_reference(group):
    """Return MITRE's ID and web page for a group."""
    for reference in group["external_references"]:
        if reference["source_name"] == "mitre-attack":
            return reference["external_id"], reference["url"]
    raise ValueError(f"No MITRE reference for {group['name']}")


def save_source(cursor, group, url):
    cursor.execute(
        """
        INSERT INTO sources (title, url)
        VALUES (%s, %s)
        ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title
        RETURNING id
        """,
        (f"MITRE ATT&CK: {group['name']}", url),
    )
    return cursor.fetchone()[0]


def save_group(cursor, group, mitre_id, source_id):
    cursor.execute(
        """
        INSERT INTO groups (mitre_id, main_name, summary, source_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (mitre_id) DO UPDATE SET
            main_name = EXCLUDED.main_name,
            summary = EXCLUDED.summary,
            source_id = EXCLUDED.source_id
        RETURNING id
        """,
        (
            mitre_id,
            group["name"],
            clean_text(group.get("description", "")),
            source_id,
        ),
    )
    return cursor.fetchone()[0]


def save_aliases(cursor, group, group_id, source_id):
    """Save this group's names and remove ones MITRE no longer lists."""
    names = {normalize(group["name"]): group["name"]}
    for alias in group.get("aliases", []):
        names.setdefault(normalize(alias), alias)

    cursor.execute(
        """
        DELETE FROM aliases
        WHERE group_id = %s AND source_id = %s
          AND NOT (normalized_name = ANY(%s))
        """,
        (group_id, source_id, list(names)),
    )

    main_name = normalize(group["name"])
    for normalized_name, name in names.items():
        relationship = "same" if normalized_name == main_name else "unknown"
        cursor.execute(
            """
            INSERT INTO aliases
                (group_id, source_id, name, normalized_name, relationship)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (group_id, normalized_name, source_id) DO UPDATE SET
                name = EXCLUDED.name,
                relationship = EXCLUDED.relationship
            """,
            (group_id, source_id, name, normalized_name, relationship),
        )
    return len(names)


def main():
    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        return 1

    groups = load_groups()
    alias_count = 0

    with connect() as connection:
        with connection.cursor() as cursor:
            for group in groups:
                mitre_id, url = mitre_reference(group)
                source_id = save_source(cursor, group, url)
                group_id = save_group(cursor, group, mitre_id, source_id)
                alias_count += save_aliases(cursor, group, group_id, source_id)

    print(f"Imported {len(groups)} groups and {alias_count} names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
