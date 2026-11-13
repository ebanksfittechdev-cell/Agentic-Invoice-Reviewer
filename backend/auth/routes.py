import bcrypt
from flask import Blueprint, request, session, jsonify

from db import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    store_name = (data.get("store_name") or "").strip()

    if not email or not password or not store_name:
        return jsonify({"error": "email, password, and store_name are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password_hash=pw_hash, store_name=store_name)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    return jsonify({"user_id": user.id, "store_name": user.store_name}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user.id
    return jsonify({"user_id": user.id, "store_name": user.store_name}), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 401

    return jsonify({
        "user_id": user.id,
        "email": user.email,
        "store_name": user.store_name,
        "created_at": user.created_at.isoformat(),
    }), 200
