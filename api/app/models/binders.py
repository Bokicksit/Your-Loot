"""Binders: a shelf arranged the way you would arrange the physical thing.

There are three kinds and they differ only in where their slots come from.

A **dex** binder has one slot per national dex number, and any card of that
species fills it. A **set** binder has one slot per card in a set, and only
that exact card fills it. A **custom** binder holds whatever you put in it, in
the order you put it — a binder of nothing but Charizards.

The first two have a *universe* the app already knows: 1,025 dex numbers, or
the catalogue rows for one set. Those slots are not stored. Writing 1,025 rows
per binder to record that they are still empty would mean a binder that goes
stale the moment the catalogue gains a card, and a reseed that has to
reconcile against every binder anybody ever made. So a row here exists only
where there is something to remember — a copy filed in the slot, or the flag
saying you are happy with what is in it. The rest is computed from the
universe at read time. That is how the Pokédex has always worked; this only
gives it a name.

A custom binder has no universe, so its rows *are* the binder, and `position`
is what its order means.

One card, many binders. Your best Charizard belongs in the Pokédex, in the
Celebrations set binder and in the Charizard binder, all at once — which is
why filing a card is a row here rather than the single `owned.in_binder` flag
this replaces. That flag could answer "in a binder" but never "in which one",
and on this install 881 of 943 copies were already claimed by the Pokédex, so
anything exclusive would have emptied it.
"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Binder(TimestampMixin, Base):
    __tablename__ = "binder"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # dex|set|custom
    # set binders only: which set, and whether every printing gets its own slot
    set_code: Mapped[str | None] = mapped_column(String(30))
    master: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # the cover: a photo of the real binder, or the art of whatever it is
    # about. A shelf of names and nothing else is hard to read at a glance.
    image_url: Mapped[str | None] = mapped_column(String(500))
    # A flat colour instead of a picture — most binders on a shelf are one,
    # and photographing a plain black folder to tell it from the other plain
    # black folder is work for nothing. Null keeps the colour the shelf makes
    # up from the kind and the name.
    color: Mapped[str | None] = mapped_column(String(7))

    # The shape of the physical thing: pockets across, pockets down, and
    # whether it is read as a spread of two facing pages. These decide where
    # the page breaks fall and nothing else — no slot moves because you
    # changed them, which is what makes them safe to change.
    rows: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    cols: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    double_page: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Whether Japanese cards belong in this binder — eligibility, not a view
    # filter. Off, one is never offered for it and never takes a slot in it.
    allow_ja: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # where it sits on the shelf; null means never placed, and those sort
    # after the ones that have been
    position: Mapped[int | None] = mapped_column(Integer)

    slots = relationship(
        "BinderSlot", back_populates="binder", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # One Pokédex each. It is the only kind whose universe is fixed and
        # universal, so a second one would be the same binder twice.
        Index(
            "uq_binder_one_dex", "user_id",
            unique=True, postgresql_where=text("kind = 'dex'"),
        ),
        # One binder per set per mode. A second Celebrations binder in the same
        # mode is a mistake every time; master and regular are different
        # binders and both are allowed.
        Index(
            "uq_binder_one_set", "user_id", "set_code", "master",
            unique=True, postgresql_where=text("kind = 'set'"),
        ),
    )


class BinderSlot(Base):
    """One remembered slot.

    On dex and set binders this row annotates a slot that exists whether or
    not the row does, and `slot_key` says which — the dex number, or the card
    number. On custom binders the row is the slot.
    """

    __tablename__ = "binder_slot"

    id: Mapped[int] = mapped_column(primary_key=True)
    binder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("binder.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Dex number or card number, as text because card numbers are text:
    # "TG12", "101a", and in one set a card numbered "!". Null on custom
    # binders, where position is the only ordering that means anything.
    slot_key: Mapped[str | None] = mapped_column(String(20))
    # Master-set binders split a card into its printings, so a slot has to say
    # which one it is: normal / reverse / holo. Empty rather than null on the
    # binders that do not split — Postgres counts nulls as distinct, so a
    # nullable column here would let the unique index below wave through two
    # rows for the same slot, which is exactly what it did once.
    variant: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=""
    )
    position: Mapped[int | None] = mapped_column(Integer)  # custom binders only

    # The catalogue card this slot is for. Set and custom binders both know it;
    # a dex slot does not, because any Charizard fills the Charizard slot and
    # choosing which one is the whole point of the binder.
    item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("collection_item.id", ondelete="CASCADE")
    )
    # The copy filed here. Null means empty — which on a set binder is the
    # interesting state, the gaps being what you open it to see.
    # SET NULL, not CASCADE: selling the card empties the slot, it does not
    # remove the slot. "I was happy with what was here" is worth keeping when
    # the card leaves, which is the same reason `unfile` keeps the row.
    owned_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("owned.id", ondelete="SET NULL")
    )
    # "I am happy with this one": it stays even though something better
    # exists. Carried over from the Pokédex, where it is the difference
    # between a placeholder and the card you actually wanted.
    happy: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # joined, not lazy: `Owned.in_binder` asks every slot what kind of
    # binder it belongs to, and one query per slot would undo the batching
    # the selectin on the other side just bought.
    binder = relationship("Binder", back_populates="slots", lazy="joined")
    owned = relationship("Owned", back_populates="binder_slots")
    item = relationship("CollectionItem")

    __table_args__ = (
        # One row per slot on the kinds that have a universe. slot_key is the
        # null one, and only on custom binders, which is what leaves them free
        # to hold as many rows as they like — variant is never null, so it
        # cannot smuggle a duplicate past this.
        Index("uq_binder_slot_key", "binder_id", "slot_key", "variant", unique=True),
        # "which binders is this copy in?", for the card list's hide filter
        Index("ix_binder_slot_owned", "owned_id"),
    )
