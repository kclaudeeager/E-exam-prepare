"""Add DRIVING education level and driving_manual document category.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-26

"""

from alembic import op

# revision identifiers
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enums need explicit ALTER TYPE to add new values.
    # Using raw SQL because Alembic's op.execute works with enums.

    # Add DRIVING to education_level_enum
    op.execute("ALTER TYPE education_level_enum ADD VALUE IF NOT EXISTS 'DRIVING'")

    # Add driving_manual to document_category_enum
    op.execute("ALTER TYPE document_category_enum ADD VALUE IF NOT EXISTS 'driving_manual'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # Downgrade would require recreating the enum, which is complex.
    # For safety, we leave the enum values in place on downgrade.
    pass
