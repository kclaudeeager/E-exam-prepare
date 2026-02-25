"""Add subjects, student_subjects, practice_sessions, practice_answers + document enhancements

Revision ID: a1b2c3d4e5f6
Revises: 3295efca321d
Create Date: 2025-01-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3295efca321d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New Enums (already created in initial migration, but ensure they exist) ─────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE document_category_enum AS ENUM ('exam_paper', 'marking_scheme', 'syllabus', 'textbook', 'notes', 'other');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # NOTE: subjects, student_subjects, practice_sessions, practice_answers tables
    # are now created in the initial migration (0_initial). This migration is now a no-op
    # except for adding the document_category enum and columns.

    # ── Add columns to documents table ────────────────────────────────
    op.add_column('documents', sa.Column(
        'document_category',
        postgresql.ENUM('exam_paper', 'marking_scheme', 'syllabus', 'textbook', 'notes', 'other', name='document_category_enum', create_type=False),
        nullable=True,
        server_default='exam_paper',
    ))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('subject_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_documents_subject_id', 'documents', 'subjects', ['subject_id'], ['id'])


def downgrade() -> None:
    # ── Drop foreign keys + columns from documents ────────────────────
    op.drop_constraint('fk_documents_subject_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'subject_id')
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'document_category')

    # ── Drop tables (reverse order of creation) ───────────────────────
    op.drop_table('practice_answers')
    op.drop_table('practice_sessions')
    op.drop_table('student_subjects')
    op.drop_table('subjects')

    # ── Drop enums ────────────────────────────────────────────────────
    sa.Enum(name='practice_status_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='document_category_enum').drop(op.get_bind(), checkfirst=True)
