"""long term memory

Revision ID: 014484b643d3
Revises: 28de2d593529
Create Date: 2026-07-28 13:08:54.612519

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014484b643d3"
down_revision: str | Sequence[str] | None = "28de2d593529"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Autogenerate also proposed dropping `checkpoints`/`checkpoint_writes`/
    `checkpoint_blobs`/`checkpoint_migrations` — those are the LangGraph Postgres
    checkpointer's own tables (Phase 10), created by its own `.setup()` call rather than
    Alembic, so they are absent from `Base.metadata` and autogenerate reads that absence
    as "should be dropped". Left out here entirely: see
    `orchestration/checkpointer.py`'s docstring for why that table set is deliberately
    outside Alembic's ownership.
    """
    op.create_table(
        "long_term_memory",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("preference", "goal", "recurring_finding", name="memory_kind"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_thread_id", sa.UUID(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name=op.f("fk_long_term_memory_profile_id_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_long_term_memory_source_thread_id_chat_threads"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_long_term_memory")),
    )
    op.create_index(
        op.f("ix_long_term_memory_profile_id"), "long_term_memory", ["profile_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_long_term_memory_profile_id"), table_name="long_term_memory")
    op.drop_table("long_term_memory")
    op.execute("DROP TYPE IF EXISTS memory_kind")
