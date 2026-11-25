-- One row per claim that a vendor created a name. A name can have several.
CREATE TABLE IF NOT EXISTS alias_vendors (
    alias_id   INTEGER NOT NULL REFERENCES aliases (id) ON DELETE CASCADE,
    vendor_id  INTEGER NOT NULL REFERENCES vendors (id),
    source_id  INTEGER NOT NULL REFERENCES sources (id),
    PRIMARY KEY (alias_id, vendor_id, source_id)
);

-- Let the API's read-only login see the new table, if that login exists.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'codename_reader') THEN
        GRANT SELECT ON public.alias_vendors TO codename_reader;
    END IF;
END
$$;
