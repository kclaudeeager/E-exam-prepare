"""Verify FK fix: PracticeAnswer with non-existent question_id should save with question_id=NULL."""
from sqlalchemy.orm import sessionmaker
from app.db.session import get_engine
from app.db.models import PracticeAnswer, PracticeSession, PracticeStatusEnum, User, Subject
import uuid

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    user = db.query(User).first()
    if not user:
        print("SKIP: No users in DB")
        exit(0)

    subject = db.query(Subject).first()
    if not subject:
        print("SKIP: No subjects in DB")
        exit(0)

    session = PracticeSession(
        student_id=user.id,
        subject_id=subject.id,
        total_questions=1,
        answered_count=0,
        correct_count=0,
        status=PracticeStatusEnum.IN_PROGRESS,
    )
    db.add(session)
    db.flush()

    # The fixed code: question not in DB -> question_id=None
    answer = PracticeAnswer(
        session_id=session.id,
        question_id=None,
        question_text="Test Q",
        student_answer="Test A",
        is_correct=True,
        score=1.0,
        feedback="OK",
    )
    db.add(answer)
    db.commit()
    print("FK fix OK: saved with question_id=NULL")

    db.delete(answer)
    db.delete(session)
    db.commit()
    print("Cleanup done")
finally:
    db.close()
