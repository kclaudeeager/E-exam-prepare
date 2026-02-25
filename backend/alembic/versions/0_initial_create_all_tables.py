"""Initial migration - create all base tables

Revision ID: 0_initial
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create enums ──────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE role_enum AS ENUM ('student', 'admin');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE education_level_enum AS ENUM ('P6', 'S3', 'S6', 'TTC');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ingestion_status_enum AS ENUM ('pending', 'ingesting', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── users table ───────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', postgresql.ENUM('student', 'admin', name='role_enum', create_type=False), nullable=False, server_default='student'),
        sa.Column('education_level', postgresql.ENUM('P6', 'S3', 'S6', 'TTC', name='education_level_enum', create_type=False), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_user_email'),
    )

    # ── documents table ───────────────────────────────────────────────
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('subject', sa.String(100), nullable=False),
        sa.Column('level', postgresql.ENUM('P6', 'S3', 'S6', 'TTC', name='education_level_enum', create_type=False), nullable=False),
        sa.Column('year', sa.String(10), nullable=False),
        sa.Column('official_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('marking_scheme', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ingestion_status', postgresql.ENUM('pending', 'ingesting', 'completed', 'failed', name='ingestion_status_enum', create_type=False), nullable=False, server_default='pending'),
        sa.Column('collection_name', sa.String(200), nullable=True),
        sa.Column('is_personal', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_documents_subject', 'subject'),
        sa.Index('ix_documents_is_archived', 'is_archived'),
        sa.Index('ix_documents_is_personal', 'is_personal'),
        sa.Index('ix_documents_is_shared', 'is_shared'),
    )

    # ── subjects table ────────────────────────────────────────────────
    op.create_table(
        'subjects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('level', postgresql.ENUM('P6', 'S3', 'S6', 'TTC', name='education_level_enum', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'level', name='uq_subject_name_level'),
    )

    # ── topics table ──────────────────────────────────────────────────
    op.create_table(
        'topics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('subject_id', sa.UUID(), nullable=True),
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['topics.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── questions table ───────────────────────────────────────────────
    op.create_table(
        'questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(20), nullable=False),
        sa.Column('options', sa.Text(), nullable=True),
        sa.Column('correct_answer', sa.Text(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── solutions table ───────────────────────────────────────────────
    op.create_table(
        'solutions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=True),
        sa.Column('solution_text', sa.Text(), nullable=False),
        sa.Column('step_by_step', sa.Text(), nullable=True),
        sa.Column('related_topics', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── student_subjects enrollment ───────────────────────────────────
    op.create_table(
        'student_subjects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'subject_id', name='uq_student_subject'),
    )

    # ── subscriptions table ───────────────────────────────────────────
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('topic_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'topic_id', name='uq_student_topic'),
    )

    # ── quizzes table ─────────────────────────────────────────────────
    op.create_table(
        'quizzes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('mode', sa.String(50), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── quiz_questions M2M ────────────────────────────────────────────
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('quiz_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quiz_id', 'question_id', name='uq_quiz_question'),
    )

    # ── attempts table ────────────────────────────────────────────────
    op.create_table(
        'attempts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('quiz_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── attempt_answers table ─────────────────────────────────────────
    op.create_table(
        'attempt_answers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('attempt_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('student_answer', sa.Text(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['attempt_id'], ['attempts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── progress table ────────────────────────────────────────────────
    op.create_table(
        'progress',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('topic_id', sa.UUID(), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'topic_id', name='uq_student_topic_progress'),
    )

    # ── practice_sessions table ───────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE practice_status_enum AS ENUM ('in_progress', 'completed', 'abandoned');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.create_table(
        'practice_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=True),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('collection_name', sa.String(200), nullable=True),
        sa.Column('status', postgresql.ENUM('in_progress', 'completed', 'abandoned', name='practice_status_enum', create_type=False), nullable=False, server_default='in_progress'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('answered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── practice_answers table ────────────────────────────────────────
    op.create_table(
        'practice_answers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(20), nullable=False, server_default='short-answer'),
        sa.Column('student_answer', sa.Text(), nullable=False),
        sa.Column('is_handwritten', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('correct_answer', sa.Text(), nullable=True),
        sa.Column('source_references', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['practice_sessions.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── chat_sessions table ───────────────────────────────────────────
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('collection_name', sa.String(200), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── chat_messages table ───────────────────────────────────────────
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── document_shares table (moved here) ─────────────────────────────
    op.create_table(
        'document_shares',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('shared_with_user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['shared_with_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'shared_with_user_id', name='uq_document_share')
    )


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('document_shares')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('practice_answers')
    op.drop_table('practice_sessions')
    op.drop_table('progress')
    op.drop_table('attempt_answers')
    op.drop_table('attempts')
    op.drop_table('quiz_questions')
    op.drop_table('quizzes')
    op.drop_table('subscriptions')
    op.drop_table('student_subjects')
    op.drop_table('solutions')
    op.drop_table('questions')
    op.drop_table('topics')
    op.drop_table('subjects')
    op.drop_table('documents')
    op.drop_table('users')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS practice_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS ingestion_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS education_level_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS role_enum CASCADE")
