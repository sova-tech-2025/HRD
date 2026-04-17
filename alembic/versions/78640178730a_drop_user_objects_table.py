"""drop_user_objects_table

Revision ID: 78640178730a
Revises: 71cd763f56f9
Create Date: 2026-04-16 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "78640178730a"
down_revision: Union[str, None] = "71cd763f56f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("user_objects")


def downgrade() -> None:
    op.create_table(
        "user_objects",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("object_id", sa.Integer(), sa.ForeignKey("objects.id"), primary_key=True),
    )
