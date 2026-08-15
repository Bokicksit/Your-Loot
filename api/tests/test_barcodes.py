"""Is a barcode ever looked up twice?

On one household this is a small kindness. Shared by many people it is the
difference between a bill that grows with your users and one that grows with
the number of products that exist — and the second one stops, because there
are only so many PS2 games.

The provider is stubbed here rather than called. What is worth protecting is
that the second scan does not reach for it, and a test that actually went to
UPCitemdb would spend the very quota it exists to defend.

    docker compose -f compose.test.yaml run --rm tests
"""

import uuid

import pytest

from app import barcodes
from app.db import SessionLocal
from app.models import BarcodeCache


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def counted(monkeypatch):
    """The provider, replaced by something that counts and answers."""
    calls = []

    def fake(code):
        calls.append(code)
        return [{"title": f"Product {code}", "images": []}]

    monkeypatch.setattr(barcodes, "upc_lookup", fake)
    return calls


def _fresh(db, code):
    db.query(BarcodeCache).filter(BarcodeCache.code == code).delete()
    db.commit()


def test_the_same_barcode_is_only_ever_asked_once(db, counted):
    code = f"9{uuid.uuid4().int % 10**11:011d}"
    _fresh(db, code)
    try:
        first = barcodes.lookup(db, code)
        second = barcodes.lookup(db, code)
        third = barcodes.lookup(db, code)

        assert len(counted) == 1, f"asked the provider {len(counted)} times"
        assert first == second == third
    finally:
        _fresh(db, code)


def test_a_barcode_nobody_recognises_is_remembered_too(db, counted, monkeypatch):
    """A miss is an answer. Asking again this afternoon will not change it,
    and a shelf of unrecognised barcodes would otherwise burn the quota every
    time somebody opened the app."""
    code = f"8{uuid.uuid4().int % 10**11:011d}"
    monkeypatch.setattr(barcodes, "upc_lookup", lambda c: counted.append(c) or [])
    _fresh(db, code)
    try:
        assert barcodes.lookup(db, code) == []
        assert barcodes.lookup(db, code) == []
        assert len(counted) == 1, "a miss was asked twice"
        assert db.get(BarcodeCache, code).found is False
    finally:
        _fresh(db, code)


def test_a_failure_is_not_cached(db, monkeypatch):
    """A spent quota or a network blip is not an answer about the barcode.
    Caching it would turn a bad afternoon into a permanently wrong entry."""
    from app.integrations.upcitemdb import BarcodeError

    code = f"7{uuid.uuid4().int % 10**11:011d}"
    _fresh(db, code)
    calls = []

    def angry(c):
        calls.append(c)
        raise BarcodeError(429, "quota spent")

    monkeypatch.setattr(barcodes, "upc_lookup", angry)
    try:
        for _ in range(2):
            with pytest.raises(BarcodeError):
                barcodes.lookup(db, code)
        assert db.get(BarcodeCache, code) is None, "an error was written to the cache"
        assert len(calls) == 2, "a failure should be retried, not remembered"
    finally:
        _fresh(db, code)
