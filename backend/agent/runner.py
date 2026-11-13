"""
agent/runner.py — run the invoice reviewer agent for one invoice.

Injects user_id into ADK session state before the agent starts.
The model never sees or chooses the user_id.

Call limit: an after_model_callback stops the agent after 8 model calls
to prevent runaway inference costs.
"""

import asyncio
import logging
import os

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent.agent import build_agent
from db import Discrepancy, PendingAction

_log = logging.getLogger(__name__)

MAX_MODEL_CALLS = 8
APP_NAME = "invoice_reviewer"


def run_agent(invoice_id: int, user_id: int, discrepancies: list[Discrepancy]) -> dict:
    """
    Run the agent for one invoice and return a summary dict:
    {
        "summary": str,
        "pending_action_ids": [int, ...]
    }
    """
    # Count actions before the run so we can find new ones after
    existing_action_ids = {
        a.id for a in PendingAction.query.filter_by(
            user_id=user_id, invoice_id=invoice_id
        ).all()
    }

    summary = asyncio.run(_run_async(invoice_id, user_id, discrepancies))

    new_actions = PendingAction.query.filter(
        PendingAction.user_id == user_id,
        PendingAction.invoice_id == invoice_id,
        ~PendingAction.id.in_(existing_action_ids),
    ).all()

    return {
        "summary": summary,
        "pending_action_ids": [a.id for a in new_actions],
    }


async def _run_async(invoice_id: int, user_id: int, discrepancies: list[Discrepancy]) -> str:
    """Async core: build session, inject state, run agent, return summary text."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    agent = build_agent()

    # Attach the call-limit callback
    call_counter = {"count": 0}

    def after_model_callback(callback_context, llm_response):
        call_counter["count"] += 1
        if call_counter["count"] >= MAX_MODEL_CALLS:
            _log.warning(
                "Agent hit %d-call limit for invoice %s — stopping.",
                MAX_MODEL_CALLS, invoice_id,
            )
            # Signal the agent to stop by marking the response as turn_complete
            llm_response.turn_complete = True
        return llm_response

    agent.after_model_callback = after_model_callback

    session_service = InMemorySessionService()

    # Build the initial message: a plain-text list of discrepancies
    disc_lines = "\n".join(
        f"- [{d.type}] item_code={d.item_code or 'N/A'} amount=${d.amount or 0:.2f}"
        for d in discrepancies
    )
    initial_message = (
        f"Invoice ID: {invoice_id}\n"
        f"The following discrepancies were found:\n{disc_lines}\n\n"
        "Please investigate each one using the available tools and propose appropriate actions."
    )

    # Create session with user_id in state — the model never sees this directly
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=str(user_id),
        state={"user_id": user_id},
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=str(user_id),
        session_id=session.id,
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=initial_message)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text") and p.text
            )

    return final_text or "Agent completed with no summary."
