"""Can a migration be undone?

This is the test that matters most in the whole suite, and it is first for
that reason. Everything else here protects a feature; this protects somebody
else's collection. A bad migration on a stranger's NAS at midnight is the one
failure I cannot reach, cannot see and cannot fix, and "it worked on mine" is
not a plan.

It runs against a scratch database it creates and drops itself, so it is safe
anywhere — including against a live install, which is the point. The
destructive marker is for tests that eat the *real* database; this one never
touches it.
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app import config as app_config

SCRATCH = "loot_migration_scratch"

# Tables the app cannot lose. Not the whole schema on purpose — a list of
# every table would fail on every future migration and get deleted in
# annoyance. These are the ones holding what somebody typed in.
CORE_TABLES = {
    "collection_item", "owned", "wanted", "users", "settings",
    "card_attrs", "game_attrs", "item_override",
}


@pytest.fixture(scope="module")
def scratch_url():
    """A throwaway database beside the real one, dropped afterwards whatever
    happens."""
    live = make_url(app_config.settings.database_url)
    admin = create_engine(live.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}"'))
        c.execute(text(f'CREATE DATABASE "{SCRATCH}"'))
    url = live.set(database=SCRATCH)
    try:
        yield url
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="module")
def alembic(scratch_url):
    """alembic/env.py reads the URL off app settings rather than the ini, so
    pointing it somewhere else means pointing *that* somewhere else."""
    was = app_config.settings.database_url
    # str() on a URL masks the password as "***" — handy in a log, useless as
    # a connection string, and the failure is an auth error rather than
    # anything that points at this line.
    app_config.settings.database_url = scratch_url.render_as_string(hide_password=False)
    try:
        yield Config("alembic.ini")
    finally:
        app_config.settings.database_url = was


def _tables(url) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_builds_the_whole_schema(alembic, scratch_url):
    command.upgrade(alembic, "head")
    missing = CORE_TABLES - _tables(scratch_url)
    assert not missing, f"upgrade left these out: {sorted(missing)}"


def test_every_migration_reverses(alembic, scratch_url):
    """Down to nothing and back up, twice over.

    Once proves the downgrades run. Twice proves they left the database in a
    state the upgrades can actually build on again — which is where a
    half-written downgrade shows up, and not before.
    """
    command.upgrade(alembic, "head")
    for _ in range(2):
        command.downgrade(alembic, "base")
        left = _tables(scratch_url) - {"alembic_version"}
        assert not left, f"downgrade left tables behind: {sorted(left)}"
        command.upgrade(alembic, "head")
    assert CORE_TABLES <= _tables(scratch_url)


def test_data_survives_a_downgrade_and_re_upgrade(alembic, scratch_url):
    """The version people will actually hit: rolling back one release because
    something else broke, then rolling forward again once it's fixed."""
    command.upgrade(alembic, "head")

    engine = create_engine(scratch_url)
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO collection_item (id, module, title, source, external_id) "
            "VALUES (9001, 'games', 'Rollback Survivor', 'manual', 'rb-1')"
        ))
        c.execute(text(
            "INSERT INTO owned (item_id, condition) VALUES (9001, 'NM')"
        ))

    # back one, then forward again
    command.downgrade(alembic, "-1")
    command.upgrade(alembic, "head")

    with engine.connect() as c:
        title = c.execute(
            text("SELECT title FROM collection_item WHERE id = 9001")
        ).scalar()
        copies = c.execute(
            text("SELECT count(*) FROM owned WHERE item_id = 9001")
        ).scalar()
    engine.dispose()

    assert title == "Rollback Survivor", "the item did not survive the round trip"
    assert copies == 1, "the copy did not survive the round trip"
