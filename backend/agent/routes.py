"""
agent/routes.py — POST /api/agent/chat endpoint for interactive Q&A in ChatPage.

Every reply is produced by the read-only chat agent (agent.runner.run_chat),
which looks answers up with tools. There are no canned answers: if the model
is unavailable the endpoint returns an error explaining why.
"""

from flask import Blueprint, request, jsonify

from auth.utils import current_user_id

agent_bp = Blueprint("agent", __name__)

MAX_MESSAGE_CHARS = 4000


@agent_bp.post("/chat")
def chat():
    user_id = current_user_id()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": f"message is longer than {MAX_MESSAGE_CHARS} characters"}), 400

    history = data.get("history")
    if not isinstance(history, list):
        history = []
    history = [
        {"role": t.get("role"), "text": str(t.get("text", ""))[:MAX_MESSAGE_CHARS]}
        for t in history
        if isinstance(t, dict) and t.get("role") in ("user", "assistant")
    ]

    from agent.runner import run_chat, AgentUnavailable
    try:
        result = run_chat(user_id, message, history)
    except AgentUnavailable as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(result), 200
