"""Test the API with a small temporary database."""

import os
import time

# Never let the tests touch an online database.
os.environ["DATABASE_URL"] = ""
os.environ.pop("ENV_FILE", None)
os.environ["API_SIGNATURE_TOKEN"] = ""

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

import api
from api import app, get_connection
from create_reader import create_reader, reader_url
from database import connect
from import_misp import save_vendors, vendors_by_name
from naming import FIRST_WORDS, LAST_WORDS, decode, likely_vendor, meaning_from
from rate_limit import RateLimiter
from setup_database import update_tables

TEST_DB = "codename_test"

SAMPLE_DATA = """
INSERT INTO sources (title, url) VALUES ('Test source', 'https://example.test');
INSERT INTO groups (mitre_id, main_name, summary, source_id) VALUES
    ('T1', 'APT29', 'A test summary.', 1),
    ('T2', 'Saint Bear', 'Another summary.', 1),
    ('T3', 'Ember Bear', 'A third summary.', 1);
INSERT INTO aliases (group_id, source_id, name, normalized_name, relationship) VALUES
    (1, 1, 'APT29', 'apt29', 'same'),
    (1, 1, 'Cozy Bear', 'cozy bear', 'unknown'),
    (2, 1, 'UAC-0056', 'uac-0056', 'unknown'),
    (3, 1, 'UAC-0056', 'uac-0056', 'unknown');
INSERT INTO vendors (name) VALUES ('Mandiant'), ('Another Vendor');
INSERT INTO alias_vendors (alias_id, vendor_id, source_id) VALUES
    (1, 1, 1), (1, 2, 1);
"""


@pytest.fixture(scope="session")
def client():
    with connect(dbname="postgres", autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB}")

    with connect(dbname=TEST_DB, autocommit=True) as connection:
        update_tables(connection)
        connection.execute(SAMPLE_DATA)

    def use_test_database():
        with connect(dbname=TEST_DB, row_factory=dict_row) as connection:
            yield connection

    app.dependency_overrides[get_connection] = use_test_database
    yield TestClient(app)
    app.dependency_overrides.clear()

    with connect(dbname="postgres", autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {TEST_DB}")


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.setattr(api, "limiter", RateLimiter())


def test_alive_does_not_need_the_database(client):
    assert client.get("/alive").json() == {"status": "ok"}


def test_too_many_requests_are_refused(client, monkeypatch):
    monkeypatch.setattr(api, "limiter", RateLimiter(per_minute=2))
    statuses = [
        client.get(
            "/search?q=apt29", headers={"X-Forwarded-For": f"192.0.2.{n}"}
        ).status_code
        for n in range(3)
    ]
    assert statuses == [200, 200, 429]
    assert client.get("/health").status_code == 429
    assert client.get("/alive").status_code == 200


def test_limit_resets_each_minute():
    now = [0]
    limiter = RateLimiter(per_minute=1, clock=lambda: now[0])
    assert limiter.allow()
    assert not limiter.allow()
    now[0] = 60
    assert limiter.allow()


SECRET = "a-test-secret-that-is-long-enough-for-hs256"


def sign(secret=SECRET, algorithm="HS256", **changes):
    claims = {"iss": "netlify", "exp": int(time.time()) + 300, **changes}
    claims = {key: value for key, value in claims.items() if value is not None}
    return jwt.encode(claims, secret, algorithm=algorithm)


def test_signed_request_is_allowed(client, monkeypatch):
    monkeypatch.setenv("API_SIGNATURE_TOKEN", SECRET)
    response = client.get("/search?q=apt29", headers={"x-nf-sign": sign()})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        sign(secret="a-different-secret-that-is-also-long-enough"),
        sign(exp=1),
        sign(exp=None),
        sign(iss="someone-else"),
        sign(secret="", algorithm="none"),
    ],
    ids=["missing", "nonsense", "wrong-secret", "expired", "no-expiry", "issuer", "none"],
)
@pytest.mark.parametrize("path", ["/search?q=apt29", "/groups/1", "/health", "/docs"])
def test_unsigned_request_is_refused(client, monkeypatch, path, token):
    monkeypatch.setenv("API_SIGNATURE_TOKEN", SECRET)
    assert client.get(path, headers={"x-nf-sign": token}).status_code == 403
    assert client.get("/alive").status_code == 200


def test_refused_requests_do_not_use_up_the_limit(client, monkeypatch):
    monkeypatch.setenv("API_SIGNATURE_TOKEN", SECRET)
    monkeypatch.setattr(api, "limiter", RateLimiter(per_minute=1))
    for _ in range(5):
        assert client.get("/search?q=apt29").status_code == 403
    response = client.get("/search?q=apt29", headers={"x-nf-sign": sign()})
    assert response.status_code == 200


@pytest.fixture
def reader(client):
    name, password = "codename_test_reader", "only-for-this-test"
    with connect(dbname="postgres", autocommit=True) as admin:
        admin.execute(f"DROP ROLE IF EXISTS {name}")
    with connect(dbname=TEST_DB) as owner:
        create_reader(owner, name, password)

    settings = {"POSTGRES_USER": name, "POSTGRES_PASSWORD": password}
    with pytest.MonkeyPatch.context() as patch:
        for key, value in settings.items():
            patch.setenv(key, value)
        connection = connect(dbname=TEST_DB, autocommit=True, row_factory=dict_row)
    yield connection

    connection.close()
    with connect(dbname=TEST_DB, autocommit=True) as owner:
        owner.execute(f"DROP OWNED BY {name}")
        owner.execute(f"DROP ROLE {name}")


def test_group_page_shows_stated_likely_and_unknown_vendors(client):
    apt29, cozy_bear = client.get("/groups/1").json()["aliases"]
    assert [vendor["name"] for vendor in apt29["vendors"]] == [
        "Another Vendor",
        "Mandiant",
    ]
    assert apt29["vendors"][0]["source"]["url"] == "https://example.test"
    assert apt29["likely_vendor"] is None

    assert cozy_bear["vendors"] == []
    assert cozy_bear["likely_vendor"]["name"] == "CrowdStrike"

    uac = client.get("/groups/2").json()["aliases"][0]
    assert uac["vendors"] == [] and uac["likely_vendor"] is None


@pytest.mark.parametrize(
    ("name", "vendor"),
    [
        ("Cozy Bear", "CrowdStrike"),
        ("MIDNIGHT BLIZZARD", "Microsoft"),
        ("Cloaked Ursa", "Palo Alto"),
        ("APT29", None),
        ("Bear", None),
        ("Bear Group", None),
        ("IRON HEMLOCK", "Secureworks"),
        ("Lake Relic", "Google"),
        ("Iron Tiger", None),
        ("Silent Lynx", None),
        ("Cobalt Group", None),
        ("UNC2452", None),
        ("", None),
    ],
)
def test_name_patterns(name, vendor):
    guess = likely_vendor(name)
    assert (guess["name"] if guess else None) == vendor


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Turbo Panda", [("CrowdStrike", "Panda", "China")]),
        ("TYPHOON", [("Microsoft", "Typhoon", "China")]),
        ("Silent Lynx", [("CrowdStrike", "Lynx", "Georgia"), ("Palo Alto", "Lynx", "Belarus")]),
        ("bronze example", [("Secureworks", "Bronze", "China")]),
        ("Copper Typhoon", [("Microsoft", "Typhoon", "China")]),
        ("Cobalt Group", []),
        ("Panda Express", []),
        ("APT29", []),
        ("", []),
        ("   ", []),
    ],
)
def test_decoder(name, expected):
    found = [(r["vendor"], r["clue"], r["meaning"]) for r in decode(name)]
    assert found == expected


@pytest.mark.parametrize(
    ("name", "clue"),
    [("Storm-1234", "Storm"), ("storm1234", "Storm"), ("UNC9999", "UNC"), ("fin7", "FIN")],
)
def test_decoder_reads_numbered_names(name, clue):
    assert [r["clue"] for r in decode(name)] == [clue]


@pytest.mark.parametrize("name", ["Storm-12", "Storm-12345", "UNC", "FINISH", "FIN7x"])
def test_decoder_ignores_lookalike_numbers(name):
    assert decode(name) == []


def test_every_word_is_lowercase_and_has_a_secure_source():
    for vendor, (title, url), words in LAST_WORDS + FIRST_WORDS:
        assert vendor and title and url.startswith("https://")
        for word, meaning in words.items():
            assert word == word.lower() and word.isalpha() and meaning


def test_meaning_needs_the_matching_vendor():
    assert meaning_from("Cozy Bear", ["CrowdStrike"])["meaning"] == "Russia"
    assert meaning_from("Energetic Bear", ["Kaspersky"]) is None
    assert meaning_from("Lake Relic", ["Google Cloud Blog"])["meaning"] == "Russia"
    assert meaning_from("Silent Lynx", ["Palo Alto"])["meaning"] == "Belarus"
    assert meaning_from("Cozy Bear", []) is None


def test_search_decodes_an_unknown_name(client):
    result = client.get("/search", params={"q": " Turbo   PANDA "}).json()
    assert result["matches"] == []
    assert result["readings"][0]["meaning"] == "China"
    assert result["readings"][0]["source"]["url"].startswith("https://")


def test_search_for_a_plain_name_has_no_readings(client):
    result = client.get("/search", params={"q": "purple toaster"}).json()
    assert result["readings"] == []


def test_group_page_shows_a_meaning_only_for_the_matching_vendor(client):
    apt29, cozy_bear = client.get("/groups/1").json()["aliases"]
    assert apt29["reading"] is None
    assert cozy_bear["reading"]["meaning"] == "Russia"


def test_misp_entries_are_matched_to_vendors():
    actors = [
        {"meta": {"name-attribution": ["COZY  Bear:v1", "cozy bear:v2", "Odd:missing"]}},
        {"meta": {}},
        {},
    ]
    producers = [{"uuid": "v1", "value": "One"}, {"uuid": "v2", "value": "Two"}]
    assert vendors_by_name(actors, producers) == {"cozy bear": {"One", "Two"}}


def test_misp_import_can_run_again(client):
    with connect(dbname=TEST_DB) as connection:
        count = "SELECT count(*) FROM alias_vendors WHERE source_id <> 1"
        for vendors, expected in (
            ({"uac-0056": {"One", "Two"}, "not ours": {"Three"}}, 4),
            ({"uac-0056": {"One", "Two"}}, 4),
            ({"cozy bear": {"One"}}, 1),
        ):
            assert save_vendors(connection, vendors) == 1
            assert connection.execute(count).fetchone()[0] == expected
        extra = "SELECT count(*) FROM vendors WHERE name = 'Three'"
        assert connection.execute(extra).fetchone()[0] == 0
        connection.rollback()


def test_updating_tables_again_changes_nothing(client):
    with connect(dbname=TEST_DB, autocommit=True) as connection:
        assert "001_schema.sql" not in update_tables(connection)
        groups = connection.execute("SELECT count(*) FROM groups").fetchone()[0]
        assert groups == 3


def test_reader_can_do_everything_the_api_needs(reader):
    result = api.search(q="cosy bear", connection=reader)
    assert result["suggestions"][0] == "Cozy Bear"
    assert api.get_group(group_id=1, connection=reader)["main_name"] == "APT29"
    assert api.health(connection=reader) == {"status": "ok"}


@pytest.mark.parametrize(
    "command",
    [
        "DELETE FROM aliases",
        "UPDATE groups SET main_name = 'changed'",
        "INSERT INTO vendors (name) VALUES ('new')",
        "TRUNCATE sources CASCADE",
        "DROP TABLE aliases",
        "CREATE TABLE extra (id int)",
        "CREATE ROLE helper",
    ],
)
def test_reader_cannot_change_anything(reader, command):
    # Even after switching off the read-only default, it has no permission.
    reader.execute("SET default_transaction_read_only = off")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        reader.execute(command)


def test_reader_address_keeps_the_server_and_hides_special_characters():
    url = reader_url("postgresql://owner:old@host.test/db?sslmode=require", "r", "a@b/c")
    assert url == "postgresql://r:a%40b%2Fc@host.test/db?sslmode=require"


def test_online_database_must_be_encrypted(monkeypatch):
    user, password, name = (
        os.environ[key] for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    )
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql://{user}:{password}@localhost:5432/{name}?sslmode=disable"
    )
    with pytest.raises(psycopg.OperationalError, match="SSL"):
        connect()


def test_blank_online_settings_do_not_use_the_local_database(monkeypatch, tmp_path):
    blank = tmp_path / "blank.env"
    blank.write_text("DATABASE_URL=\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(blank))
    with pytest.raises(RuntimeError, match="DATABASE_URL is missing"):
        connect()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_finds_an_alias(client):
    response = client.get("/search", params={"q": "cozy bear"})
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["main_name"] == "APT29"
    assert match["matched_name"] == "Cozy Bear"
    assert match["source"]["url"] == "https://example.test"


def test_search_ignores_case_and_extra_spaces(client):
    response = client.get("/search", params={"q": "  COZY   Bear "})
    assert response.json()["matches"][0]["main_name"] == "APT29"


def test_search_returns_every_group_sharing_a_name(client):
    response = client.get("/search", params={"q": "uac-0056"})
    names = [match["main_name"] for match in response.json()["matches"]]
    assert names == ["Ember Bear", "Saint Bear"]


def test_unknown_name_returns_nothing(client):
    response = client.get("/search", params={"q": "purple toaster"})
    assert response.status_code == 200
    assert response.json()["matches"] == []
    assert response.json()["suggestions"] == []


@pytest.mark.parametrize(
    ("typo", "expected"),
    [("cosy bear", "Cozy Bear"), ("cozybear", "Cozy Bear"), ("apt 29", "APT29")],
)
def test_typo_suggests_the_right_name_first(client, typo, expected):
    result = client.get("/search", params={"q": typo}).json()
    assert result["matches"] == []
    assert result["suggestions"][0] == expected


def test_exact_match_has_no_suggestions(client):
    result = client.get("/search", params={"q": "apt29"}).json()
    assert result["suggestions"] == []


def test_very_short_search_has_no_suggestions(client):
    result = client.get("/search", params={"q": "a"}).json()
    assert result["suggestions"] == []


def test_shared_name_is_suggested_once(client):
    result = client.get("/search", params={"q": "uac 0056"}).json()
    assert result["suggestions"].count("UAC-0056") == 1


def test_symbols_only_search_is_safe(client):
    response = client.get("/search", params={"q": "%%% --- '"})
    assert response.status_code == 200
    assert response.json()["suggestions"] == []


@pytest.mark.parametrize("bad", ["", "   ", "x" * 101, "bad\x00name"])
def test_bad_search_is_rejected(client, bad):
    assert client.get("/search", params={"q": bad}).status_code == 422


def test_search_text_is_not_run_as_sql(client):
    attack = "'; DROP TABLE aliases; --"
    assert client.get("/search", params={"q": attack}).json()["matches"] == []
    assert client.get("/search", params={"q": "apt29"}).json()["matches"]


def test_group_page_has_aliases_and_sources(client):
    response = client.get("/groups/1")
    assert response.status_code == 200
    group = response.json()
    assert group["main_name"] == "APT29"
    assert group["source"]["title"] == "Test source"
    assert [alias["name"] for alias in group["aliases"]] == ["APT29", "Cozy Bear"]


@pytest.mark.parametrize(
    ("group_id", "status"),
    [("999", 404), ("0", 422), ("abc", 422), ("99999999999", 422)],
)
def test_bad_group_ids(client, group_id, status):
    assert client.get(f"/groups/{group_id}").status_code == status
