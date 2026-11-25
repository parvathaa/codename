-- The first tables for Codename.
BEGIN;

-- Where a fact came from.
CREATE TABLE sources (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL UNIQUE,
    published  DATE
);

-- Companies that name hacker groups, such as Microsoft.
CREATE TABLE vendors (
    id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

-- One row per hacker group.
CREATE TABLE groups (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mitre_id          TEXT UNIQUE,
    main_name         TEXT NOT NULL,
    suspected_origin  TEXT,
    summary           TEXT,
    source_id         INTEGER NOT NULL REFERENCES sources (id)
);

-- One row per claim that a name refers to a group.
CREATE TABLE aliases (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id         INTEGER NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    vendor_id        INTEGER REFERENCES vendors (id),
    source_id        INTEGER NOT NULL REFERENCES sources (id),
    name             TEXT NOT NULL,
    normalized_name  TEXT NOT NULL,
    relationship     TEXT NOT NULL DEFAULT 'unknown'
                     CHECK (relationship IN ('same', 'overlaps', 'unknown')),
    confidence       TEXT NOT NULL DEFAULT 'unknown'
                     CHECK (confidence IN ('low', 'medium', 'high', 'unknown')),
    UNIQUE (group_id, normalized_name, source_id)
);

-- Makes searching by name fast.
CREATE INDEX aliases_normalized_name_idx ON aliases (normalized_name);

COMMIT;
