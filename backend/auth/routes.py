import bcrypt
from flask import Blueprint, request, session, jsonify

from db import get_db, put_db

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    store_name = (data.get("store_name") or "").strip()

    if not email or not password or not store_name:
        return jsonify({"error": "email, password, and store_name are required"}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({"error": "Email already registered"}), 409
            cur.execute(
                "INSERT INTO users (email, password_hash, store_name) VALUES (%s, %s, %s) RETURNING id",
                (email, pw_hash, store_name),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    finally:
        put_db(conn)

    session["user_id"] = user_id
    return jsonify({"user_id": user_id, "store_name": store_name}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, store_name FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
    finally:
        put_db(conn)

    if not row or not bcrypt.checkpw(password.encode(), row[1].encode()):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = row[0]
    return jsonify({"user_id": row[0], "store_name": row[2]}), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, store_name, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        put_db(conn)

    if not row:
        session.clear()
        return jsonify({"error": "User not found"}), 401

    return jsonify({
        "user_id": row[0],
        "email": row[1],
        "store_name": row[2],
        "created_at": row[3].isoformat(),
    }), 200
