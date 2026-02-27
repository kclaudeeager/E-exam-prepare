"""Add account_type column to users table.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-26

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the account_type_enum type
    account_type_enum = sa.Enum("academic", "practice", name="account_type_enum")
    account_type_enum.create(op.get_bind(), checkfirst=True)

    # Add account_type column with default 'academic' for existing users
    op.add_column(
        "users",
        sa.Column(
            "account_type",
            account_type_enum,
            server_default="academic",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "account_type")
    sa.Enum(name="account_type_enum").drop(op.get_bind(), checkfirst=True)
