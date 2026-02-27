import sys
import os
import uuid

# Add the app directory to sys.path so we can import from app
# Assumes we are running from the /backend directory
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.db.session import get_session_factory
from app.db.models import (
    Subject, Document, PracticeSession, ChatSession,
    EducationLevelEnum, StudentSubject, Topic
)

def unify_driving_data():
    factory = get_session_factory()
    engine = factory.kw['bind']
    print(f"🔗 Connecting to database: {engine.url}")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    print(f"📋 Tables visible to script: {inspector.get_table_names()}")

    db = factory()
    try:
        print("🔍 Searching for DRIVING level subjects...")
        driving_subjects = db.query(Subject).filter(
            Subject.level == EducationLevelEnum.DRIVING
        ).all()

        if not driving_subjects:
            print("❌ No DRIVING subjects found in database. Checking for legacy documents/sessions anyway...")
        
        legacy_names = [s.name for s in driving_subjects]
        # Add common legacy names just in case they aren't in the Subject table but are in Documents
        standard_legacy = ["Traffic Rules and Regulations", "Highway Code", "Provisional License Test Prep"]
        for name in standard_legacy:
            if name not in legacy_names:
                legacy_names.append(name)

        print(f"📊 Identified legacy subject names: {legacy_names}")

        # 1. Identify or create the main "Driving Prep" subject
        main_subject = db.query(Subject).filter(
            Subject.name == "Driving Prep",
            Subject.level == EducationLevelEnum.DRIVING
        ).first()

        if not main_subject:
            print("✨ Creating main 'Driving Prep' subject...")
            main_subject = Subject(
                name="Driving Prep",
                level=EducationLevelEnum.DRIVING,
                icon="🚗"
            )
            db.add(main_subject)
            db.flush()
        else:
            print(f"✅ Main subject identified: {main_subject.name} (ID: {main_subject.id})")

        # 2. Update Documents
        print("📄 Updating Documents...")
        docs = db.query(Document).filter(
            Document.level == EducationLevelEnum.DRIVING
        ).all()
        doc_count = 0
        for doc in docs:
            doc.subject = "Driving Prep"
            doc.subject_id = main_subject.id
            doc.collection_name = "DRIVING"
            doc_count += 1
        print(f"  - Updated {doc_count} documents.")

        # 3. Update Topics
        print("📂 Updating Topics...")
        topics = db.query(Topic).filter(
            Topic.subject.in_(legacy_names)
        ).all()
        topic_count = 0
        for topic in topics:
            topic.subject = "Driving Prep"
            topic_count += 1
        print(f"  - Updated {topic_count} topics.")

        # 4. Update Practice Sessions
        print("📝 Updating Practice Sessions...")
        # Update by subject_id
        sessions_by_id = db.query(PracticeSession).filter(
            PracticeSession.subject_id.in_([s.id for s in driving_subjects])
        ).all()
        # Update sessions that might have old collection names but missing subject_id
        sessions_by_coll = db.query(PracticeSession).filter(
            PracticeSession.collection_name.like("DRIVING_%")
        ).all()
        
        all_sessions = set(sessions_by_id) | set(sessions_by_coll)
        session_count = 0
        for sess in all_sessions:
            sess.subject_id = main_subject.id
            sess.collection_name = "DRIVING"
            session_count += 1
        print(f"  - Updated {session_count} practice sessions.")

        # 5. Update Chat Sessions
        print("💬 Updating Chat Sessions...")
        chat_sessions = db.query(ChatSession).filter(
            ChatSession.collection.like("DRIVING_%")
        ).all()
        chat_count = 0
        for sess in chat_sessions:
            sess.collection = "DRIVING"
            chat_count += 1
        print(f"  - Updated {chat_count} chat sessions.")

        # 6. Handle Student Enrollments
        print("🎓 Updating Student Enrollments...")
        other_subject_ids = [s.id for s in driving_subjects if s.id != main_subject.id]
        enroll_count = 0
        if other_subject_ids:
            enrollments = db.query(StudentSubject).filter(
                StudentSubject.subject_id.in_(other_subject_ids)
            ).all()
            for enroll in enrollments:
                # Check if already enrolled in main subject
                existing = db.query(StudentSubject).filter(
                    StudentSubject.student_id == enroll.student_id,
                    StudentSubject.subject_id == main_subject.id
                ).first()
                if not existing:
                    enroll.subject_id = main_subject.id
                    enroll_count += 1
                else:
                    db.delete(enroll)
                    enroll_count += 1
        print(f"  - Migrated/cleaned {enroll_count} enrollments.")

        # 7. Delete old subjects
        print("🗑️ Deleting legacy driving subjects...")
        del_count = 0
        for s in driving_subjects:
            if s.id != main_subject.id:
                db.delete(s)
                del_count += 1
        print(f"  - Deleted {del_count} legacy subjects.")

        db.commit()
        print("🎉 Successfully unified all driving data!")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    unify_driving_data()
