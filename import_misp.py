"""Record which vendor created each name, using MISP Galaxy data."""

import json
import sys
from collections import defaultdict
from pathlib import Path

from database import connect
from lookup import normalize

DATA_FOLDER = Path(__file__).parent / "data"
ACTORS_FILE = DATA_FOLDER / "misp-threat-actor.json"
PRODUCERS_FILE = DATA_FOLDER / "misp-producer.json"

SOURCE_TITLE = "MISP Galaxy: threat actors"
SOURCE_URL = "https://github.com/MISP/misp-galaxy/blob/main/clusters/threat-actor.json"


def read_values(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)["values"]


def vendors_by_name(actors, producers):
    """Map each normalized name to the vendors said to have created it."""
    vendor_names = {producer["uuid"]: producer["value"] for producer in producers}
    vendors = defaultdict(set)
    for actor in actors:
        for entry in actor.get("meta", {}).get("name-attribution", []):
            name, _, vendor_id = entry.rpartition(":")
            if name and vendor_id in vendor_names:
                vendors[normalize(name)].add(vendor_names[vendor_id])
    return vendors


def save_vendors(connection, vendors):
    """Replace what MISP says about our names. Returns how many names matched."""
    source_id = connection.execute(
        """
        INSERT INTO sources (title, url) VALUES (%s, %s)
        ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title
        RETURNING id
        """,
        (SOURCE_TITLE, SOURCE_URL),
    ).fetchone()[0]

    connection.execute("DELETE FROM alias_vendors WHERE source_id = %s", (source_id,))

    aliases = connection.execute("SELECT id, normalized_name FROM aliases").fetchall()
    claims = [
        (alias_id, vendor)
        for alias_id, name in aliases
        for vendor in sorted(vendors.get(name, ()))
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO vendors (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(vendor,) for vendor in sorted({vendor for _, vendor in claims})],
        )
        cursor.executemany(
            """
            INSERT INTO alias_vendors (alias_id, vendor_id, source_id)
            SELECT %s, id, %s FROM vendors WHERE name = %s
            """,
            [(alias_id, source_id, vendor) for alias_id, vendor in claims],
        )

    matched = {alias_id for alias_id, _ in claims}
    return len({name for alias_id, name in aliases if alias_id in matched})


def main():
    for path in (ACTORS_FILE, PRODUCERS_FILE):
        if not path.exists():
            print(f"Data file not found: {path}")
            return 1

    vendors = vendors_by_name(read_values(ACTORS_FILE), read_values(PRODUCERS_FILE))
    if not vendors:
        print("MISP's files have no vendor names. Nothing changed.")
        return 1

    with connect() as connection:
        count = save_vendors(connection, vendors)

    print(f"MISP names a vendor for {count} of our names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
