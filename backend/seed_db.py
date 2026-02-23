"""One-time DB setup: create tables and seed essential records."""
from app.db.session import Base, get_engine, get_session_factory
from app.db.models import (
    Document,
    EducationLevelEnum,
    IngestionStatusEnum,
    RoleEnum,
    User,
)
from app.core.security import hash_password

# 1. Create all tables
engine = get_engine()
Base.metadata.create_all(bind=engine)
print("✅ All tables created in PostgreSQL")

session_factory = get_session_factory()
with session_factory() as db:
    # 2. System user (owner for auto-generated documents)
    sys_user = db.query(User).filter(User.email == "system@local").first()
    if not sys_user:
        sys_user = User(
            email="system@local",
            hashed_password="x",
            full_name="System",
            role=RoleEnum.ADMIN,
        )
        db.add(sys_user)
        db.commit()
        db.refresh(sys_user)
        print("✅ Created system user")
    else:
        print("  System user already exists")

    # 3. Test admin user
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
            full_name="Admin User",
            role=RoleEnum.ADMIN,
        )
        db.add(admin)
        db.commit()
        print("✅ Created admin: admin@example.com / admin123")
    else:
        print("  Admin user already exists")

    # 4. Test student user
    student = db.query(User).filter(User.email == "student@example.com").first()
    if not student:
        student = User(
            email="student@example.com",
            hashed_password=hash_password("student123"),
            full_name="Student User",
            role=RoleEnum.STUDENT,
        )
        db.add(student)
        db.commit()
        print("✅ Created student: student@example.com / student123")
    else:
        print("  Student user already exists")

    # 5. Placeholder document for RAG-generated questions
    doc = db.query(Document).filter(Document.filename == "RAG_GENERATED.pdf").first()
    if not doc:
        doc = Document(
            filename="RAG_GENERATED.pdf",
            subject="General",
            level=EducationLevelEnum.S3,
            year="2024",
            file_path="placeholder",
            uploaded_by=sys_user.id,
            ingestion_status=IngestionStatusEnum.COMPLETED,
        )
        db.add(doc)
        db.commit()
        print(f"✅ Created RAG placeholder document (id={doc.id})")
    else:
        print("  RAG placeholder document already exists")

print("\n🎉 Database is ready to use!")
print("   Admin:   admin@example.com   / admin123")
print("   Student: student@example.com / student123")
