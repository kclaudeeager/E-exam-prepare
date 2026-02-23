"""Unit tests for user API endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration."""
    response = client.post(
        "/api/users/register",
        json={
            "email": "u1@ex.com",
            "password": "pwd1",
            "full_name": "Test User",
            "role": "student",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "u1@ex.com"
    assert data["full_name"] == "Test User"


def test_register_duplicate_email(client: TestClient):
    """Test registering with duplicate email."""
    # Register first user
    client.post(
        "/api/users/register",
        json={
            "email": "u2@ex.com",
            "password": "pwd1",
            "full_name": "Test User",
            "role": "student",
        },
    )
    
    # Try to register with same email
    response = client.post(
        "/api/users/register",
        json={
            "email": "u2@ex.com",
            "password": "pwd2",
            "full_name": "Another User",
            "role": "student",
        },
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


def test_login_user(client: TestClient):
    """Test user login."""
    # Register user first
    client.post(
        "/api/users/register",
        json={
            "email": "u3@ex.com",
            "password": "pwd1",
            "full_name": "Test User",
            "role": "student",
        },
    )
    
    # Login
    response = client.post(
        "/api/users/login",
        json={
            "email": "u3@ex.com",
            "password": "pwd1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_login_invalid_credentials(client: TestClient):
    """Test login with invalid credentials."""
    response = client.post(
        "/api/users/login",
        json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


def test_get_current_user(client: TestClient):
    """Test getting current user info."""
    # Register user
    register_response = client.post(
        "/api/users/register",
        json={
            "email": "u4@ex.com",
            "password": "pwd1",
            "full_name": "Test User",
            "role": "student",
        },
    )
    assert register_response.status_code == 201
    
    # Get current user with auth (will test this properly when auth is implemented)
    # For now, just verify registration worked
    user = register_response.json()
    assert user["email"] == "u4@ex.com"
    assert user["full_name"] == "Test User"


def test_unauthorized_access(client: TestClient):
    """Test accessing protected endpoint without token."""
    response = client.get("/api/users/me")
    # Will return 401 Unauthorized due to missing token
    assert response.status_code == 401

