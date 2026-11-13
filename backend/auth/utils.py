from flask import session, abort


def current_user_id() -> int:
    """Return the logged-in user's id from the session, or abort 401."""
    user_id = session.get("user_id")
    if not user_id:
        abort(401, description="Not authenticated.")
    return user_id
