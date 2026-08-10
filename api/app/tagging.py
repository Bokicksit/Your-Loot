"""Words a person filed their own things under.

Same reasoning as tenancy: every module needs the identical four answers, and
writing them out once means there is one place to be right. A tag row already
carries who owns it, so the rules here start from `user_id` and a query that
forgets it returns nothing rather than everybody's labels.

`scope` is the collection as the app shows it — 'records', 'hardware' — not
the module as the database stores it. Hardware shares a table with games and
should not share its vocabulary.
"""

from sqlalchemy import and_, delete, func, select

from app.models import ItemTag, Tag, tag_key

MAX_NAME = 40


def clean_names(names) -> dict[str, str]:
    """Submitted names, folded to {key: display}, first spelling winning.

    Typing "Hip Hop" onto a record already tagged "hip-hop" should not make a
    second tag, and should not silently rename the first.
    """
    out: dict[str, str] = {}
    for raw in names or []:
        if not isinstance(raw, str):
            continue
        name = " ".join(raw.split())[:MAX_NAME]
        key = tag_key(name)
        if key and key not in out:
            out[key] = name
    return out


def tags_for(db, user_id: int, item_ids) -> dict[int, list[str]]:
    """{item_id: [names]} for a page of items, in one query.

    The list endpoints serialise a hundred items at a time; asking per item
    would be a hundred round trips to render one screen.
    """
    ids = list(item_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(ItemTag.item_id, Tag.name)
        .join(Tag, Tag.id == ItemTag.tag_id)
        .where(ItemTag.item_id.in_(ids), Tag.user_id == user_id)
        .order_by(Tag.name)
    )
    out: dict[int, list[str]] = {}
    for item_id, name in rows:
        out.setdefault(item_id, []).append(name)
    return out


def tags_of(db, user_id: int, item_id: int) -> list[str]:
    """One item's tags — for the create and update replies, which return a
    single row and have no page to batch with."""
    return tags_for(db, user_id, [item_id]).get(item_id, [])


def tagged(user_id: int, scope: str, name: str, item_col):
    """EXISTS: this person tagged that item with this word, in this
    collection. For putting a tag filter on a list query."""
    return (
        select(ItemTag.item_id)
        .join(Tag, Tag.id == ItemTag.tag_id)
        .where(
            ItemTag.item_id == item_col,
            Tag.user_id == user_id,
            Tag.scope == scope,
            Tag.key == tag_key(name),
        )
        .exists()
    )


def facet(db, user_id: int, scope: str, shelf=None) -> list[dict]:
    """Every tag in this collection with how many items carry it.

    `shelf` is the same predicate the page itself filters by. Without it the
    count includes things you tagged and no longer have a copy of, so the bar
    offers "hip-hop (3)" and clicking it returns nothing — worse than a zero,
    because a zero at least looks like a zero. It goes in the join rather than
    the WHERE so that emptied tags still come back: an unused word is still
    part of your vocabulary and the autocomplete should keep offering it. It
    is the filter bar's job to leave the zeroes out.
    """
    on = ItemTag.tag_id == Tag.id
    rows = db.execute(
        select(Tag.id, Tag.name, func.count(ItemTag.item_id))
        .outerjoin(ItemTag, on if shelf is None else and_(on, shelf))
        .where(Tag.user_id == user_id, Tag.scope == scope)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name)
    )
    # `value`/`count` to match the shape the other facets already use, plus
    # the id, without which the filter bar could show a tag but never offer
    # to rename or delete it
    return [{"id": tid, "value": name, "count": count} for tid, name, count in rows]


def set_item_tags(db, user_id: int, scope: str, item_id: int, names) -> list[str]:
    """Make this item's tags exactly `names`, creating any that are new.

    Only touches tags in this person's copy of this collection: the delete
    goes through a subquery of their own tag ids, so re-tagging a record can
    never strip a label off somebody else's shelf or off the same item in a
    different tab.
    """
    wanted = clean_names(names)

    existing = {
        t.key: t
        for t in db.scalars(
            select(Tag).where(Tag.user_id == user_id, Tag.scope == scope)
        )
    }
    keep = []
    for key, display in wanted.items():
        tag = existing.get(key)
        if tag is None:
            tag = Tag(user_id=user_id, scope=scope, name=display, key=key)
            db.add(tag)
            db.flush()
            existing[key] = tag
        keep.append(tag)

    mine = select(Tag.id).where(Tag.user_id == user_id, Tag.scope == scope)
    db.execute(delete(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id.in_(mine)))
    for tag in keep:
        db.add(ItemTag(tag_id=tag.id, item_id=item_id))

    return [t.name for t in sorted(keep, key=lambda t: t.name)]
