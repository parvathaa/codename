"""Codename's web API."""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel

from database import connect
from lookup import normalize
from naming import decode, likely_vendor, meaning_from
from rate_limit import RateLimiter
from signature import is_signed

app = FastAPI(
    title="Codename",
    description=(
        "Look up a hacker group by any of its names.\n\n"
        "© 2026 The MITRE Corporation. This work is reproduced and distributed "
        "with the permission of The MITRE Corporation."
    ),
)


limiter = RateLimiter()


@app.middleware("http")
async def protect(request: Request, call_next):
    # Render's health check comes straight to us and touches nothing.
    if request.url.path == "/alive":
        return await call_next(request)

    # Online, only requests signed by our Netlify site are allowed.
    secret = os.environ.get("API_SIGNATURE_TOKEN")
    if secret and not is_signed(request.headers.get("x-nf-sign", ""), secret):
        return JSONResponse({"detail": "Not allowed."}, status_code=403)

    if not limiter.allow():
        return JSONResponse(
            {"detail": "Too many requests. Try again in a minute."},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


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
    suggestions: list[str]
    readings: list["Reading"]


class Vendor(BaseModel):
    name: str
    source: Source


class Reading(BaseModel):
    vendor: str
    clue: str
    meaning: str
    source: Source


class Alias(BaseModel):
    name: str
    vendors: list[Vendor]
    likely_vendor: Vendor | None
    reading: Reading | None
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


def find_suggestions(connection, name):
    """Find up to five known names that look like a misspelled one."""
    if len(name) < 3:
        return []

    rows = connection.execute(
        """
        SELECT name FROM (
            SELECT MIN(name) AS name,
                   MAX(CASE
                       WHEN regexp_replace(normalized_name, '[^[:alnum:]]', '', 'g')
                          = regexp_replace(%(name)s, '[^[:alnum:]]', '', 'g')
                       THEN 2
                       ELSE GREATEST(
                           similarity(normalized_name, %(name)s),
                           word_similarity(%(name)s, normalized_name)
                       )
                   END) AS score,
                   MAX(similarity(normalized_name, %(name)s)) AS whole_score
            FROM aliases
            GROUP BY normalized_name
        ) AS scored
        WHERE score >= 0.43
        ORDER BY score DESC, whole_score DESC, name
        LIMIT 5
        """,
        {"name": name},
    ).fetchall()
    return [row["name"] for row in rows]


@app.get("/alive")
def alive() -> dict[str, str]:
    """Confirm that the API is running, without waking the database."""
    return {"status": "ok"}


@app.get("/health")
def health(connection: Connection) -> dict[str, str]:
    """Confirm that the API can reach its database."""
    connection.execute("SELECT 1")
    return {"status": "ok"}


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
    return {
        "query": q,
        "matches": [move_source(row) for row in rows],
        "suggestions": [] if rows else find_suggestions(connection, name),
        "readings": decode(name),
    }


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
        SELECT aliases.id, aliases.name,
               aliases.relationship, aliases.confidence,
               sources.title AS source_title, sources.url AS source_url
        FROM aliases
        JOIN sources ON sources.id = aliases.source_id
        WHERE aliases.group_id = %s
        ORDER BY aliases.name, aliases.id
        """,
        (group_id,),
    ).fetchall()

    claims = connection.execute(
        """
        SELECT alias_vendors.alias_id, vendors.name,
               sources.title AS source_title, sources.url AS source_url
        FROM alias_vendors
        JOIN aliases ON aliases.id = alias_vendors.alias_id
        JOIN vendors ON vendors.id = alias_vendors.vendor_id
        JOIN sources ON sources.id = alias_vendors.source_id
        WHERE aliases.group_id = %s
        ORDER BY vendors.name, sources.id
        """,
        (group_id,),
    ).fetchall()

    vendors = {}
    for claim in claims:
        alias_id = claim.pop("alias_id")
        vendors.setdefault(alias_id, []).append(move_source(claim))

    group = move_source(group)
    group["aliases"] = [move_source(alias) for alias in aliases]
    for alias in group["aliases"]:
        alias["vendors"] = vendors.get(alias.pop("id"), [])
        # Only guess when no source has told us.
        alias["likely_vendor"] = (
            None if alias["vendors"] else likely_vendor(alias["name"])
        )
        known = [vendor["name"] for vendor in alias["vendors"]]
        if alias["likely_vendor"]:
            known.append(alias["likely_vendor"]["name"])
        alias["reading"] = meaning_from(alias["name"], known)
    return group
