"""
test_auth.py — tests for register, login, logout, and /me endpoints.
"""

import pytest
from tests.conftest import make_user


class TestRegister:
    def test_register_success(self, client, db):
        resp = client.post("/api/auth/register", json={
            "email": "new@store.com",
            "password": "pass123",
            "store_name": "New Store",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user_id" in data
        assert data["store_name"] == "New Store"

    def test_register_duplicate_email(self, app, client, db):
        with app.app_context():
            make_user(db, email="taken@store.com")
            db.session.commit()

        resp = client.post("/api/auth/register", json={
            "email": "taken@store.com",
            "password": "pass123",
            "store_name": "Store",
        })
        assert resp.status_code == 409

    def test_register_missing_fields(self, client, db):
        resp = client.post("/api/auth/register", json={"email": "x@x.com"})
        assert resp.status_code == 400

    def test_register_sets_session(self, client, db):
        resp = client.post("/api/auth/register", json={
            "email": "sess@store.com",
            "password": "pass123",
            "store_name": "Sess Store",
        })
        assert resp.status_code == 201
        # Session cookie set — /me should return the user
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.get_json()["email"] == "sess@store.com"


class TestLogin:
    def _register(self, client, email="login@store.com", password="pass123"):
        client.post("/api/auth/register", json={
            "email": email, "password": password, "store_name": "Store"
        })

    def test_login_success(self, client, db):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@store.com", "password": "pass123"
        })
        assert resp.status_code == 200
        assert resp.get_json()["store_name"] == "Store"

    def test_login_wrong_password(self, client, db):
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@store.com", "password": "wrongpass"
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client, db):
        resp = client.post("/api/auth/login", json={
            "email": "ghost@store.com", "password": "pass123"
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client, db):
        resp = client.post("/api/auth/login", json={"email": "x@x.com"})
        assert resp.status_code == 400

    def test_login_email_case_insensitive(self, client, db):
        self._register(client, email="Case@Store.com")
        resp = client.post("/api/auth/login", json={
            "email": "case@store.com", "password": "pass123"
        })
        assert resp.status_code == 200


class TestLogout:
    def test_logout_clears_session(self, client, db):
        client.post("/api/auth/register", json={
            "email": "out@store.com", "password": "pass", "store_name": "S"
        })
        assert client.get("/api/auth/me").status_code == 200
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401

    def test_logout_unauthenticated_ok(self, client, db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200


class TestMe:
    def test_me_authenticated(self, client, db):
        client.post("/api/auth/register", json={
            "email": "me@store.com", "password": "pass", "store_name": "Me Store"
        })
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["email"] == "me@store.com"
        assert data["store_name"] == "Me Store"
        assert "created_at" in data

    def test_me_unauthenticated(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
