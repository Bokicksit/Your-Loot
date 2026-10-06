"""The database URL always names the driver the image ships.

yourloot.app went down when a fresh build pulled in SQLAlchemy 2.1: Railway
hands over a bare `postgresql://` URL, and 2.1 reads that as psycopg 3, which
is not installed. These pin the rule that stops it happening again.

    docker compose -f compose.test.yaml run --rm tests
"""

from sqlalchemy.engine import make_url

from app.config import Settings, with_our_driver


def test_a_bare_url_gets_our_driver():
    assert with_our_driver("postgresql://u:p@h:5432/db") == "postgresql+psycopg2://u:p@h:5432/db"
    # Heroku's older spelling, still handed out by some hosts
    assert with_our_driver("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"


def test_a_url_that_names_a_driver_is_left_alone():
    for url in (
        "postgresql+psycopg2://u:p@h/db",
        "postgresql+psycopg://u:p@h/db",
        "sqlite:///x.db",
    ):
        assert with_our_driver(url) == url


def test_settings_apply_it_and_sqlalchemy_agrees(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    url = Settings().database_url
    assert url.startswith("postgresql+psycopg2://")
    # and the driver SQLAlchemy will load is the one that is installed
    assert make_url(url).get_dialect().driver == "psycopg2"
