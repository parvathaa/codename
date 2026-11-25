"""Codename's web API."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from psycopg.rows import dict_row
from pydantic import BaseModel

from database import connect
from lookup import normalize

app = FastAPI(
    title="Codename",
    description=(
        "Look up a hacker group by any of its names.\n\n"
        "© 2026 The MITRE Corporation. This work is reproduced and distributed "
        "with the permission of The MITRE Corporation."
    ),
)


class Source(BaseModel):
    title: str
    url: str


class Match(BaseModel):
    group_id: int
    main_name: str
    matched_name: str
    relationship: str
    confidence: str
    source: Source


class SearchResult(BaseModel):
    query: str
    matches: list[Match]


class Alias(BaseModel):
    name: str
    vendor: str | None
    relationship: str
    confidence: str
    source: Source


class Group(BaseModel):
    id: int
    mitre_id: str | None
    main_name: str
    suspected_origin: str | None
    summary: str | None
    source: Source
    aliases: list[Alias]


def get_connection():
    """Give one request a database connection, then close it."""
    with connect(row_factory=dict_row) as connection:
        yield connection


Connection = Annotated[object, Depends(get_connection)]


def move_source(row):
    """Put a row's source title and URL into their own object."""
    row["source"] = {"title": row.pop("source_title"), "url": row.pop("source_url")}
    return row


@app.get("/search")
def search(
    q: Annotated[str, Query(min_length=1, max_length=100)],
    connection: Connection,
) -> SearchResult:
    name = normalize(q)
    if not name or "\x00" in name:
        raise HTTPException(status_code=422, detail="Enter a group name.")

    rows = connection.execute(
        """
        SELECT groups.id AS group_id, groups.main_name,
               aliases.name AS matched_name,
               aliases.relationship, aliases.confidence,
               sources.title AS source_title, sources.url AS source_url
        FROM aliases
        JOIN groups ON groups.id = aliases.group_id
        JOIN sources ON sources.id = aliases.source_id
        WHERE aliases.normalized_name = %s
        ORDER BY groups.main_name, aliases.id
        """,
        (name,),
    ).fetchall()
    return {"query": q, "matches": [move_source(row) for row in rows]}


@app.get("/groups/{group_id}")
def get_group(
    group_id: Annotated[int, Path(ge=1, le=2147483647)],
    connection: Connection,
) -> Group:
    group = connection.execute(
        """
        SELECT groups.id, groups.mitre_id, groups.main_name,
               groups.suspected_origin, groups.summary,
               sources.title AS source_title, sources.url AS source_url
        FROM groups
        JOIN sources ON sources.id = groups.source_id
        WHERE groups.id = %s
        """,
        (group_id,),
    ).fetchone()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")

    aliases = connection.execute(
        """
        SELECT aliases.name, vendors.name AS vendor,
               aliases.relationship, aliases.confidence,
               sources.title AS source_title, sources.url AS source_url
        FROM aliases
        JOIN sources ON sources.id = aliases.source_id
        LEFT JOIN vendors ON vendors.id = aliases.vendor_id
        WHERE aliases.group_id = %s
        ORDER BY aliases.name, aliases.id
        """,
        (group_id,),
    ).fetchall()

    group = move_source(group)
    group["aliases"] = [move_source(alias) for alias in aliases]
    return group
