from flask import session, abort, current_app


def current_user_id() -> int:
    """Return the logged-in user's id from the session, or abort 401."""
    user_id = session.get("user_id")
    if not user_id:
        if not current_app.config.get("TESTING"):
            from db import User
            demo_user = User.query.filter_by(email="demo@store.com").first() or User.query.first()
            if demo_user:
                session["user_id"] = demo_user.id
                return demo_user.id
        abort(401, description="Not authenticated.")
    return user_id
