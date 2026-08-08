"""Whole-collection backup and restore.

A backup is a zip holding `database.json` (every application table, dumped
row-for-row) plus the uploaded images, so a restore reproduces the install
exactly — including the card catalog, which keeps the ids that `owned`,
`wanted` and the binder point at. Re-deriving those links against a freshly
seeded catalog would be guesswork; carrying the catalog costs a couple of MB
compressed and removes the question.

JSON rather than pg_dump: no postgres client tools in this image, and a plain
dump restores across postgres versions and stays readable if it ever has to be
repaired by hand.
"""

import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import Date, DateTime, text
from sqlalchemy.orm import Session

from app.config import settings as cfg
from app.auth import require_admin
from app.db import get_db
from app.models import Base
from app.version import VERSION

router = APIRouter(prefix="/api/backup", tags=["backup"])

FORMAT = "yourloot-backup"
# bump only for a change that older code couldn't read correctly
SCHEMA_VERSION = 1
MAX_UPLOAD = 500 * 1024 * 1024


def _encode(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def _decoder(column):
    """JSON has no date type, so datetimes come back as ISO strings."""
    if isinstance(column.type, DateTime):
        return lambda v: datetime.fromisoformat(v) if isinstance(v, str) else v
    if isinstance(column.type, Date):
        return lambda v: date.fromisoformat(v) if isinstance(v, str) else v
    return None


# Whole-server, not per-person: this is the disaster-recovery copy, and a
# restore replaces everything for everybody. Admin-only for that reason —
# a per-user export is a different feature and would need its own endpoint.
@router.get("")
def download_backup(db: Session = Depends(get_db), _=Depends(require_admin)):
    tables = {}
    for table in Base.metadata.sorted_tables:
        tables[table.name] = [
            {k: _encode(v) for k, v in row.items()}
            for row in db.execute(table.select()).mappings()
        ]

    payload = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "app_version": VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tables": tables,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("database.json", json.dumps(payload, separators=(",", ":")))
        image_dir = Path(cfg.image_dir)
        if image_dir.is_dir():
            for f in sorted(image_dir.iterdir()):
                if f.is_file():
                    z.write(f, f"images/{f.name}")

    stamp = datetime.now().strftime("%Y-%m-%d")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="yourloot-backup-{stamp}.zip"'
        },
    )


def _read_payload(raw: bytes) -> tuple[dict, zipfile.ZipFile]:
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "that file isn't a Your Loot backup (not a zip)")
    try:
        payload = json.loads(z.read("database.json"))
    except KeyError:
        raise HTTPException(400, "no database.json inside — is this a Your Loot backup?")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "the database.json inside is corrupt")

    if payload.get("format") != FORMAT:
        raise HTTPException(400, "that zip isn't a Your Loot backup")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(
            400,
            f"backup format v{payload.get('schema_version')} can't be read by this "
            f"version (expects v{SCHEMA_VERSION})",
        )
    if not isinstance(payload.get("tables"), dict):
        raise HTTPException(400, "the backup has no tables in it")
    return payload, z


def _validate_against_schema(tables: dict) -> dict[str, list[dict]]:
    """A backup from a NEWER app can carry tables or columns this build has
    never heard of. Restoring it would drop them silently, so refuse instead —
    the opposite direction (an older backup) is fine, since anything missing
    just takes its default."""
    known = {t.name: t for t in Base.metadata.sorted_tables}

    unknown = sorted(set(tables) - set(known))
    if unknown:
        raise HTTPException(
            400,
            "this backup is from a newer version of Your Loot — it has "
            f"collections this build doesn't know about ({', '.join(unknown)}). "
            "Update first, then restore.",
        )

    normalised: dict[str, list[dict]] = {}
    for name, rows in tables.items():
        if not isinstance(rows, list) or not rows:
            continue
        columns = set(known[name].columns.keys())
        present = set().union(*(set(r) for r in rows))
        extra = sorted(present - columns)
        if extra:
            raise HTTPException(
                400,
                f"this backup is from a newer version of Your Loot — '{name}' has "
                f"fields this build doesn't know about ({', '.join(extra)}). "
                "Update first, then restore.",
            )
        decoders = {
            c: _decoder(known[name].columns[c]) for c in present
        }
        # every row gets identical keys so the bulk insert stays a single
        # statement; a key absent from the whole table is left out entirely so
        # its column default still applies
        normalised[name] = [
            {c: (decoders[c](r.get(c)) if decoders[c] else r.get(c)) for c in present}
            for r in rows
        ]
    return normalised


def _restore_images(z: zipfile.ZipFile) -> int:
    """Additive: images already on disk are left alone, so restoring an old
    backup never deletes a photo added since."""
    image_dir = Path(cfg.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for info in z.infolist():
        if info.is_dir() or not info.filename.startswith("images/"):
            continue
        # basename only — a crafted archive can't write outside the image dir
        name = Path(info.filename).name
        if not name or name.startswith("."):
            continue
        (image_dir / name).write_bytes(z.read(info))
        written += 1
    return written


def _reset_sequences(db: Session):
    """Rows go back in with their original ids, so every id sequence has to be
    moved past them or the next insert collides."""
    for table in Base.metadata.sorted_tables:
        for col in table.primary_key.columns:
            seq = db.execute(
                text("SELECT pg_get_serial_sequence(:t, :c)"),
                {"t": table.name, "c": col.name},
            ).scalar()
            if not seq:
                continue
            db.execute(
                text(
                    f'SELECT setval(:seq, COALESCE(MAX("{col.name}"), 1), '
                    f'MAX("{col.name}") IS NOT NULL) FROM "{table.name}"'
                ),
                {"seq": seq},
            )


@router.post("/restore")
async def restore_backup(
    file: UploadFile, db: Session = Depends(get_db), _=Depends(require_admin)
):
    """Replaces the entire collection with the contents of a backup. Everything
    is validated before a single row is touched, and the wipe-and-reload runs in
    one transaction, so a bad file leaves the database exactly as it was."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(400, "that backup is too large to upload")
    if not raw:
        raise HTTPException(400, "that file is empty")

    payload, z = _read_payload(raw)
    rows_by_table = _validate_against_schema(payload["tables"])

    # images first: orphaned files are invisible, whereas rows pointing at
    # images that failed to write would show up as broken covers
    images = _restore_images(z)

    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            rows = rows_by_table.get(table.name)
            if rows:
                db.execute(table.insert(), rows)
        _reset_sequences(db)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"restore failed and nothing was changed: {e}")

    return {
        "restored": {name: len(rows) for name, rows in rows_by_table.items()},
        "images": images,
        "from_version": payload.get("app_version"),
        "created_at": payload.get("created_at"),
    }
