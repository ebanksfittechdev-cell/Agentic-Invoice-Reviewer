"""
agent/runner.py — run the ADK agents.

run_agent(): reviews one invoice's discrepancies and proposes actions.
run_chat():  answers an owner's question with read-only tools.

Injects user_id into ADK session state before the agent starts.
The model never sees or chooses the user_id.

Call limit: an after_model_callback stops the agent after MAX_MODEL_CALLS
model calls to prevent runaway inference costs.

Neither function invents text: if the model produces no answer, or can't be
reached, AgentUnavailable is raised and the caller reports the real error.
"""

import asyncio
import inspect
import json
import logging
import os

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent.agent import build_agent, build_chat_agent
from db import Discrepancy, PendingAction

_log = logging.getLogger(__name__)

MAX_MODEL_CALLS = 8
APP_NAME = "invoice_reviewer"
_PLACEHOLDER_KEYS = {"", "your-gemini-api-key-here"}


class AgentUnavailable(RuntimeError):
    """The model could not produce an answer (missing key, API error, empty reply)."""


def run_agent(invoice_id: int, user_id: int, discrepancies: list[Discrepancy]) -> dict:
    """
    Run the reviewer agent for one invoice and return:
    {
        "summary": str,
        "steps": [str, ...],
        "pending_action_ids": [int, ...]
    }
    """
    existing_action_ids = {
        a.id for a in PendingAction.query.filter_by(
            user_id=user_id, invoice_id=invoice_id
        ).all()
    }

    disc_lines = "\n".join(
        f"- [{d.type}] item_code={d.item_code or 'N/A'} amount=${d.amount or 0:.2f}"
        for d in discrepancies
    )
    message = (
        f"Invoice ID: {invoice_id}\n"
        f"The following discrepancies were found:\n{disc_lines}\n\n"
        "Please investigate each one using the available tools and propose appropriate actions."
    )

    summary, steps = _run(build_agent(), user_id, message, label=f"invoice {invoice_id}")

    new_actions = PendingAction.query.filter(
        PendingAction.user_id == user_id,
        PendingAction.invoice_id == invoice_id,
        ~PendingAction.id.in_(existing_action_ids),
    ).all()

    return {
        "summary": summary,
        "steps": steps,
        "pending_action_ids": [a.id for a in new_actions],
    }


def run_chat(user_id: int, message: str, history: list[dict] | None = None) -> dict:
    """
    Answer an owner's chat message with the read-only chat agent.
    history: prior turns as [{"role": "user"|"assistant", "text": str}, ...]
    Returns {"reply": str, "steps": [str, ...]}.
    """
    transcript = "\n".join(
        f"{'Owner' if t.get('role') == 'user' else 'Assistant'}: {t.get('text', '').strip()}"
        for t in (history or [])[-10:]
        if t.get("text")
    )
    prompt = (
        f"Conversation so far:\n{transcript}\n\nOwner's new message: {message}"
        if transcript else message
    )
    reply, steps = _run(build_chat_agent(), user_id, prompt, label="chat")
    return {"reply": reply, "steps": steps}


# ---------------------------------------------------------------------------
# Shared execution
# ---------------------------------------------------------------------------

def _run(agent, user_id: int, message: str, label: str) -> tuple[str, list[str]]:
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key in _PLACEHOLDER_KEYS:
        raise AgentUnavailable("GEMINI_API_KEY is not set in backend/.env")
    # ADK's Gemini client reads GOOGLE_API_KEY.
    os.environ.setdefault("GOOGLE_API_KEY", api_key)

    try:
        text, steps = asyncio.run(_run_async(agent, user_id, message, label))
    except AgentUnavailable:
        raise
    except Exception as exc:  # network / auth / model-not-found errors from the SDK
        _log.exception("Agent run failed (%s)", label)
        raise AgentUnavailable(f"The model call failed: {exc}") from exc

    if not text.strip():
        raise AgentUnavailable("The model returned no answer.")
    return text.strip(), steps


async def _run_async(agent, user_id: int, message: str, label: str) -> tuple[str, list[str]]:
    call_counter = {"count": 0}

    def after_model_callback(callback_context, llm_response):
        call_counter["count"] += 1
        if call_counter["count"] >= MAX_MODEL_CALLS:
            _log.warning("Agent hit %d-call limit (%s) — stopping.", MAX_MODEL_CALLS, label)
            llm_response.turn_complete = True
        return llm_response

    agent.after_model_callback = after_model_callback

    session_service = InMemorySessionService()
    # user_id lives only in session state — the model never sees it.
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=str(user_id),
        state={"user_id": user_id},
    )
    # google-adk 0.x returns the Session directly; 1.x returns a coroutine.
    if inspect.isawaitable(session):
        session = await session
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)

    final_text = ""
    steps: list[str] = []
    async for event in runner.run_async(
        user_id=str(user_id),
        session_id=session.id,
        new_message=genai_types.Content(role="user", parts=[genai_types.Part(text=message)]),
    ):
        for call in event.get_function_calls() or []:
            steps.append(_format_call(call.name, call.args))
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text for p in event.content.parts if getattr(p, "text", None))

    return final_text, steps


def _format_call(name: str, args) -> str:
    args = dict(args or {})
    shown = ", ".join(
        f"{k}={json.dumps(v)[:60]}" for k, v in args.items() if k != "tool_context"
    )
    return f"{name}({shown})"
