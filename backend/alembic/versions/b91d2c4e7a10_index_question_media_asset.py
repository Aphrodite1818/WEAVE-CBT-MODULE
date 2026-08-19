"""index question media asset references

Revision ID: b91d2c4e7a10
Revises: 5edfc6f73032
Create Date: 2026-08-19

"""

from typing import Sequence, Union

from alembic import op


revision: str = "b91d2c4e7a10"
down_revision: Union[str, Sequence[str], None] = "5edfc6f73032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_questions_image_asset_id",
        "questions",
        ["image_asset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_questions_image_asset_id",
        table_name="questions",
    )
