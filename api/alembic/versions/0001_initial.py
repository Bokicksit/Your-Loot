"""initial schema: collection_item + per-module attrs + owned/wanted + platforms

Revision ID: 0001
Revises:
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("image_url", sa.String(500)),
        sa.Column("source", sa.String(20)),
        sa.Column("external_id", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_item_module", "collection_item", ["module"])
    # NULLs are distinct in PG unique indexes, so manual items (no external id) coexist
    op.create_index(
        "uq_item_source_external", "collection_item", ["source", "external_id"], unique=True
    )

    op.create_table(
        "card_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("set_code", sa.String(30)),
        sa.Column("set_name", sa.String(100)),
        sa.Column("card_number", sa.String(20)),
        sa.Column("rarity", sa.String(50)),
        sa.Column("national_dex_no", sa.Integer()),
        sa.Column("variant", sa.String(20)),
    )
    op.create_index("ix_card_attrs_set_code", "card_attrs", ["set_code"])
    op.create_index("ix_card_attrs_national_dex_no", "card_attrs", ["national_dex_no"])

    op.create_table(
        "platforms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("abbreviation", sa.String(20)),
    )

    op.create_table(
        "game_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("platform_id", sa.Integer(), sa.ForeignKey("platforms.id")),
        sa.Column("region", sa.String(20)),
        sa.Column("is_hardware", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "movie_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("format", sa.String(30)),
        sa.Column("edition", sa.String(100)),
        sa.Column("region_code", sa.String(10)),
    )

    op.create_table(
        "owned",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition", sa.String(20)),
        sa.Column("completeness", sa.String(20)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_owned_item_id", "owned", ["item_id"])

    op.create_table(
        "wanted",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("priority", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # reference data, seeded here so the games module has platforms on day one
    platforms = sa.table(
        "platforms", sa.column("name", sa.String), sa.column("abbreviation", sa.String)
    )
    op.bulk_insert(platforms, [
        {"name": "Nintendo Entertainment System", "abbreviation": "NES"},
        {"name": "Super Nintendo", "abbreviation": "SNES"},
        {"name": "Nintendo 64", "abbreviation": "N64"},
        {"name": "Nintendo GameCube", "abbreviation": "GCN"},
        {"name": "Nintendo Wii", "abbreviation": "Wii"},
        {"name": "Nintendo Wii U", "abbreviation": "WiiU"},
        {"name": "Nintendo Switch", "abbreviation": "NSW"},
        {"name": "Game Boy", "abbreviation": "GB"},
        {"name": "Game Boy Color", "abbreviation": "GBC"},
        {"name": "Game Boy Advance", "abbreviation": "GBA"},
        {"name": "Nintendo DS", "abbreviation": "NDS"},
        {"name": "Nintendo 3DS", "abbreviation": "3DS"},
        {"name": "PlayStation", "abbreviation": "PS1"},
        {"name": "PlayStation 2", "abbreviation": "PS2"},
        {"name": "PlayStation 3", "abbreviation": "PS3"},
        {"name": "PlayStation 4", "abbreviation": "PS4"},
        {"name": "PlayStation 5", "abbreviation": "PS5"},
        {"name": "PlayStation Portable", "abbreviation": "PSP"},
        {"name": "PlayStation Vita", "abbreviation": "Vita"},
        {"name": "Xbox", "abbreviation": "XBOX"},
        {"name": "Xbox 360", "abbreviation": "X360"},
        {"name": "Xbox One", "abbreviation": "XONE"},
        {"name": "Xbox Series X|S", "abbreviation": "XSX"},
        {"name": "Sega Genesis", "abbreviation": "GEN"},
        {"name": "Sega Dreamcast", "abbreviation": "DC"},
        {"name": "PC", "abbreviation": "PC"},
    ])


def downgrade() -> None:
    op.drop_table("wanted")
    op.drop_table("owned")
    op.drop_table("movie_attrs")
    op.drop_table("game_attrs")
    op.drop_table("platforms")
    op.drop_table("card_attrs")
    op.drop_table("collection_item")
