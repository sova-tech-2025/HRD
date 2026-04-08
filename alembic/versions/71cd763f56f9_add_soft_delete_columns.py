"""add_soft_delete_columns

Revision ID: 71cd763f56f9
Revises: 79b0c7d86372
Create Date: 2026-04-07 16:26:19.204032

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "71cd763f56f9"
down_revision: Union[str, None] = "79b0c7d86372"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # deleted_at для моделей, у которых уже есть is_active
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("groups", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("objects", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("tests", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("learning_paths", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("learning_stages", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("learning_sessions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("attestations", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # is_active + deleted_at для TestQuestion
    op.add_column("test_questions", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("test_questions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE test_questions SET is_active = true WHERE is_active IS NULL")
    op.alter_column("test_questions", "is_active", nullable=False, server_default=sa.text("true"))
    op.create_index("idx_test_question_is_active", "test_questions", ["is_active"], unique=False)

    # is_active + deleted_at для AttestationQuestion
    op.add_column("attestation_questions", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("attestation_questions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE attestation_questions SET is_active = true WHERE is_active IS NULL")
    op.alter_column("attestation_questions", "is_active", nullable=False, server_default=sa.text("true"))
    op.create_index("idx_attestation_question_is_active", "attestation_questions", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_attestation_question_is_active", table_name="attestation_questions")
    op.drop_column("attestation_questions", "deleted_at")
    op.drop_column("attestation_questions", "is_active")

    op.drop_index("idx_test_question_is_active", table_name="test_questions")
    op.drop_column("test_questions", "deleted_at")
    op.drop_column("test_questions", "is_active")

    op.drop_column("attestations", "deleted_at")
    op.drop_column("learning_sessions", "deleted_at")
    op.drop_column("learning_stages", "deleted_at")
    op.drop_column("learning_paths", "deleted_at")
    op.drop_column("tests", "deleted_at")
    op.drop_column("objects", "deleted_at")
    op.drop_column("groups", "deleted_at")
    op.drop_column("users", "deleted_at")
