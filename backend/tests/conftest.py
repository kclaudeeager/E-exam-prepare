"""Shared pytest fixtures for backend tests."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app


# Use an in-memory SQLite database for testing with static pool
SQLALCHEMY_TEST_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Use StaticPool to keep connection alive
    echo=False,
)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Create all tables once at startup
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def mock_celery_tasks():
    """Mock Celery tasks for all tests to prevent Redis connection."""
    mock_task = MagicMock(return_value=MagicMock(id="fake-task-id"))
    mock_task.delay = MagicMock(return_value=MagicMock(id="fake-task-id"))
    
    # Patch at the import point in the documents module
    with patch("app.api.documents.ingest_document", mock_task):
        yield


@pytest.fixture(scope="function")
def db():
    """Get a fresh DB session for each test."""
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()  # Rollback changes after each test
        session.close()


@pytest.fixture(scope="function")
def client(db: Session):
    """FastAPI test client with overridden DB dependency."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    # Remove TrustedHostMiddleware for tests to allow 'testserver' host
    app.user_middleware = [m for m in app.user_middleware if "TrustedHost" not in str(m)]
    
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
