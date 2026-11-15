"""initial schema: papers, analyses, http_cache, paper_chunks (pgvector)

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "papers",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("doi", sa.String(255), index=True),
        sa.Column("pmid", sa.String(32)),
        sa.Column("title", sa.Text),
        sa.Column(
            "metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "paper_sha256",
            sa.String(64),
            sa.ForeignKey("papers.sha256", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False, index=True),
        sa.Column(
            "progress", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("report", postgresql.JSONB),
        sa.Column("report_version", sa.String(16)),
        sa.Column("input_text", sa.Text),
        sa.Column("attempts", sa.Integer, server_default="0", nullable=False),
        sa.Column("models_used", postgresql.JSONB),
        sa.Column("cost_usd", sa.Numeric(10, 5)),
        sa.Column("error", sa.Text),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.func.now(), nullable=False, index=True
        ),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "http_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("response", postgresql.JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False, index=True),
    )

    op.create_table(
        "paper_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "paper_sha256",
            sa.String(64),
            sa.ForeignKey("papers.sha256", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024)),
    )
    op.execute(
        "CREATE INDEX ix_paper_chunks_embedding ON paper_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("paper_chunks")
    op.drop_table("http_cache")
    op.drop_table("analyses")
    op.drop_table("papers")
