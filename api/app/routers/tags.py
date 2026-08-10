from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_db
from app.models import CollectionItem, ItemTag, Tag, User, tag_key
from app.routers.settings import MODULES
from app.tagging import MAX_NAME, facet, set_item_tags
from app.tenancy import on_my_shelf

router = APIRouter(prefix="/api/tags", tags=["tags"])


def _scope(scope: str) -> str:
    """Collections are a closed set. Accepting anything here would quietly
    strand tags under a name no page ever asks for."""
    if scope not in MODULES:
        raise HTTPException(422, f"unknown collection {scope!r}")
    return scope


class ItemTagsIn(BaseModel):
    scope: str
    names: list[str] = Field(default_factory=list)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME)


@router.get("")
def list_tags(
    scope: str = Query(...),
    include_wanted: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """This person's vocabulary for one collection, with usage counts.

    Feeds both the autocomplete on the form and the filter control, which
    want the same list and disagree only about whether to show the zeroes.

    Counted against the same shelf the page shows, so the number on a chip
    matches what clicking it returns. `include_wanted` is the Wanted tab
    asking for the half it cares about — a tag can sit on something you are
    still hunting.

    Every collection asks here rather than through its own /facets, so there
    is one place these numbers are computed and only one to be wrong.
    """
    return {
        "tags": facet(
            db,
            user.id,
            _scope(scope),
            on_my_shelf(user.id, ItemTag.item_id, include_wanted),
        )
    }


@router.put("/item/{item_id}")
def set_tags(
    item_id: int,
    body: ItemTagsIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Replace an item's tags with exactly these. Names that don't exist yet
    are created; the client never has to make a tag before using it, which is
    the whole point of typing one into the form."""
    if not db.get(CollectionItem, item_id):
        raise HTTPException(404, "item not found")
    names = set_item_tags(db, user.id, _scope(body.scope), item_id, body.names)
    db.commit()
    return {"tags": names}


@router.patch("/{tag_id}")
def rename_tag(
    tag_id: int,
    body: RenameIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Rename everywhere at once — the point of a tag being a row rather than
    a string repeated on every item."""
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != user.id:
        raise HTTPException(404, "tag not found")

    name = " ".join(body.name.split())[:MAX_NAME]
    key = tag_key(name)
    if not key:
        raise HTTPException(422, "a tag needs a name")

    clash = db.scalar(
        select(Tag).where(
            Tag.user_id == user.id,
            Tag.scope == tag.scope,
            Tag.key == key,
            Tag.id != tag.id,
        )
    )
    if clash:
        raise HTTPException(409, f"{clash.name!r} already exists in this collection")

    tag.name, tag.key = name, key
    db.commit()
    return {"id": tag.id, "name": tag.name}


@router.delete("/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Removes the word, not the items. The rows in item_tag go with it by
    cascade; nothing that was tagged is touched."""
    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != user.id:
        raise HTTPException(404, "tag not found")
    db.delete(tag)
    db.commit()
