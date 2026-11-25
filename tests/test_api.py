"""Test the API with a small temporary database."""

import os

# Never let the tests touch an online database.
os.environ["DATABASE_URL"] = ""
os.environ.pop("ENV_FILE", None)

from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

import api
from api import app, get_connection
from database import connect
from rate_limit import RateLimiter

TEST_DB = "codename_test"
DB_FOLDER = Path(__file__).parent.parent / "db"

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
"""


@pytest.fixture(scope="session")
def client():
    with connect(dbname="postgres", autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB}")

    with connect(dbname=TEST_DB, autocommit=True) as connection:
        for filename in ("schema.sql", "002_fuzzy_search.sql"):
            connection.execute((DB_FOLDER / filename).read_text(encoding="utf-8"))
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


def test_one_visitor_is_limited(client, monkeypatch):
    monkeypatch.setattr(api, "limiter", RateLimiter(per_visitor=2, everyone=100))
    headers = {"X-Forwarded-For": "192.0.2.1"}
    statuses = [
        client.get("/search?q=apt29", headers=headers).status_code for _ in range(3)
    ]
    assert statuses == [200, 200, 429]

    other = client.get("/search?q=apt29", headers={"X-Forwarded-For": "192.0.2.2"})
    assert other.status_code == 200
    assert client.get("/health", headers=headers).status_code == 200


def test_everyone_together_is_limited_even_with_fake_addresses(client, monkeypatch):
    monkeypatch.setattr(api, "limiter", RateLimiter(per_visitor=100, everyone=2))
    statuses = [
        client.get(
            "/search?q=apt29", headers={"X-Forwarded-For": f"192.0.2.{n}"}
        ).status_code
        for n in range(3)
    ]
    assert statuses == [200, 200, 429]


def test_limit_resets_each_minute():
    now = [0]
    limiter = RateLimiter(per_visitor=1, everyone=10, clock=lambda: now[0])
    assert limiter.allow("a")
    assert not limiter.allow("a")
    now[0] = 60
    assert limiter.allow("a")


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
