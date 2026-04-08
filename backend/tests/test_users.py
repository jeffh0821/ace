"""Tests for user management API."""

import pytest
import pytest_asyncio

from tests.conftest import login_as, TEST_PASSWORD


@pytest.mark.asyncio
async def test_admin_can_create_user(client, seed_users):
    """Admin can create a new user."""
    cookies = await login_as(client, "testadmin")
    resp = await client.post(
        "/api/users/",
        json={
            "username": "newuser",
            "email": "newuser@test.local",
            "display_name": "New User",
            "password": "newpass123",
            "role": "sales",
        },
        cookies=cookies,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@test.local"
    assert data["role"] == "sales"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_admin_can_list_users(client, seed_users):
    """Admin can list all users."""
    cookies = await login_as(client, "testadmin")
    resp = await client.get("/api/users/", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3  # admin, engineer, sales
    usernames = [u["username"] for u in data]
    assert "testadmin" in usernames
    assert "testengineer" in usernames
    assert "testsales" in usernames


@pytest.mark.asyncio
async def test_admin_can_deactivate_user(client, seed_users):
    """Admin can deactivate a user."""
    users = seed_users
    sales_id = users["sales"].id
    cookies = await login_as(client, "testadmin")
    resp = await client.patch(f"/api/users/{sales_id}/deactivate", cookies=cookies)
    assert resp.status_code == 200
    assert "deactivated" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_sales_cannot_create_user(client, seed_users):
    """Sales user cannot create users (403)."""
    cookies = await login_as(client, "testsales")
    resp = await client.post(
        "/api/users/",
        json={
            "username": "hackuser",
            "email": "hack@test.local",
            "display_name": "Hacker",
            "password": "hackpass",
            "role": "sales",
        },
        cookies=cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_engineer_cannot_create_user(client, seed_users):
    """Engineer user cannot create users (403)."""
    cookies = await login_as(client, "testengineer")
    resp = await client.post(
        "/api/users/",
        json={
            "username": "hackuser",
            "email": "hack@test.local",
            "display_name": "Hacker",
            "password": "hackpass",
            "role": "engineer",
        },
        cookies=cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_username_returns_400(client, seed_users):
    """Creating a user with an existing username returns 400."""
    cookies = await login_as(client, "testadmin")
    resp = await client.post(
        "/api/users/",
        json={
            "username": "testadmin",  # already exists
            "email": "unique@test.local",
            "display_name": "Duplicate",
            "password": "pass123",
            "role": "sales",
        },
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_email_returns_400(client, seed_users):
    """Creating a user with an existing email returns 400."""
    cookies = await login_as(client, "testadmin")
    resp = await client.post(
        "/api/users/",
        json={
            "username": "uniqueuser",
            "email": "admin@test.local",  # already exists
            "display_name": "Duplicate Email",
            "password": "pass123",
            "role": "sales",
        },
        cookies=cookies,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unauthenticated_cannot_list_users(client, seed_users):
    """Unauthenticated request to list users returns 401."""
    resp = await client.get("/api/users/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_cannot_login(client, seed_users):
    """After deactivation, user cannot login."""
    users = seed_users
    sales_id = users["sales"].id
    # Deactivate the sales user
    admin_cookies = await login_as(client, "testadmin")
    resp = await client.patch(f"/api/users/{sales_id}/deactivate", cookies=admin_cookies)
    assert resp.status_code == 200

    # Now try to login as the deactivated user
    resp = await client.post(
        "/api/auth/login",
        json={"username": "testsales", "password": TEST_PASSWORD},
    )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()
