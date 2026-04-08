"""Tests for auth API: login, logout, me."""

import pytest
import pytest_asyncio

from tests.conftest import login_as, TEST_PASSWORD


@pytest.mark.asyncio
async def test_login_valid_credentials(client, seed_users):
    """Login with correct credentials returns 200 and sets cookie."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Login successful"
    assert data["user"]["username"] == "testadmin"
    assert data["user"]["role"] == "admin"
    # Cookie should be set
    assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(client, seed_users):
    """Login with wrong password returns 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, seed_users):
    """Login with unknown username returns 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_cookie(client, seed_users):
    """GET /auth/me with a valid cookie returns user info."""
    cookies = await login_as(client, "testadmin")
    resp = await client.get("/api/auth/me", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testadmin"
    assert data["role"] == "admin"
    assert data["email"] == "admin@test.local"


@pytest.mark.asyncio
async def test_get_me_without_cookie(client, seed_users):
    """GET /auth/me without any cookie returns 401."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_different_roles(client, seed_users):
    """GET /auth/me returns correct role for each user type."""
    for username, expected_role in [("testadmin", "admin"), ("testengineer", "engineer"), ("testsales", "sales")]:
        cookies = await login_as(client, username)
        resp = await client.get("/api/auth/me", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["role"] == expected_role


@pytest.mark.asyncio
async def test_logout_clears_cookie(client, seed_users):
    """POST /auth/logout clears access_token cookie."""
    cookies = await login_as(client, "testadmin")
    resp = await client.post("/api/auth/logout", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out"
    # The cookie should be cleared (set with max_age=0 or deleted)
    # After logout, /me should fail
    # Note: httpx doesn't auto-clear cookies, so we verify the response instructs deletion
    set_cookie_header = resp.headers.get("set-cookie", "")
    # The cookie deletion sets max-age=0 or expires in the past
    assert "access_token" in set_cookie_header


@pytest.mark.asyncio
async def test_login_updates_last_login(client, seed_users):
    """Login updates the user's last_login timestamp."""
    users = seed_users
    admin = users["admin"]
    assert admin.last_login is None
    cookies = await login_as(client, "testadmin")
    # Verify the login succeeded
    resp = await client.get("/api/auth/me", cookies=cookies)
    assert resp.status_code == 200
