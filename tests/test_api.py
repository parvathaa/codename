"""Test the API with a small temporary database."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from api import app, get_connection
from database import connect

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
