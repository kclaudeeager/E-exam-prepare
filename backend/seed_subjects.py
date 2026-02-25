#!/usr/bin/env python3
"""Seed default subjects into the database."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import uuid
from app.config import settings
from app.db.models import Subject

# Create engine and session
engine = create_engine(settings.database_url)

# Insert default subjects
DEFAULT_SUBJECTS = [
    # P6 (Primary 6)
    {"name": "Mathematics", "level": "P6", "description": "Primary 6 Mathematics", "icon": "🔢"},
    {"name": "English", "level": "P6", "description": "Primary 6 English Language", "icon": "📚"},
    {"name": "Science and Elementary Technology", "level": "P6", "description": "Primary 6 Science", "icon": "🔬"},
    {"name": "Social Studies", "level": "P6", "description": "Primary 6 Social Studies", "icon": "🌍"},
    
    # S3 (Ordinary Level)
    {"name": "Mathematics", "level": "S3", "description": "Ordinary Level Mathematics", "icon": "🔢"},
    {"name": "English", "level": "S3", "description": "Ordinary Level English", "icon": "📚"},
    {"name": "Biology", "level": "S3", "description": "Ordinary Level Biology", "icon": "🧬"},
    {"name": "Chemistry", "level": "S3", "description": "Ordinary Level Chemistry", "icon": "⚗️"},
    {"name": "Physics", "level": "S3", "description": "Ordinary Level Physics", "icon": "⚡"},
    
    # S6 (Advanced Level)
    {"name": "Mathematics", "level": "S6", "description": "Advanced Level Mathematics", "icon": "🔢"},
    {"name": "Physics", "level": "S6", "description": "Advanced Level Physics", "icon": "⚡"},
    {"name": "Chemistry", "level": "S6", "description": "Advanced Level Chemistry", "icon": "⚗️"},
    {"name": "Biology", "level": "S6", "description": "Advanced Level Biology", "icon": "🧬"},
]

def seed_subjects():
    """Insert default subjects if they don't exist."""
    with Session(engine) as session:
        for subject_data in DEFAULT_SUBJECTS:
            # Check if subject already exists
            existing = session.query(Subject).filter(
                Subject.name == subject_data["name"],
                Subject.level == subject_data["level"]
            ).first()
            
            if not existing:
                subject = Subject(
                    id=uuid.uuid4(),
                    name=subject_data["name"],
                    level=subject_data["level"],
                    description=subject_data["description"],
                    icon=subject_data["icon"],
                )
                session.add(subject)
                print(f"✅ Created subject: {subject_data['level']} {subject_data['name']}")
            else:
                print(f"⏭️  Subject already exists: {subject_data['level']} {subject_data['name']}")
        
        session.commit()
        print("\n✅ Seeding complete!")

if __name__ == "__main__":
    seed_subjects()
