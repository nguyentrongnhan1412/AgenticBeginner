#!/usr/bin/env python3
"""Main Entrypoint for the LangGraph + deepagents Agentic App."""

import json
import logging
import os
import sys
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.types import Command

# Ensure the App directory is in our path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_agent.agent import app as deep_agent_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("agent_app")

INTERRUPT_KEY = "__interrupt__"


def _prompt_hitl_decisions(interrupts: tuple[Any, ...]) -> dict[str, Any]:
    """Build resume payload for HumanInTheLoopMiddleware (one decision per action_request)."""
    decisions: list[dict[str, Any]] = []
    for intr in interrupts:
        hitl = intr.value
        for ar in hitl.get("action_requests", []):
            name = ar.get("name", "?")
            args = ar.get("args", {})
            desc = ar.get("description", "")
            print("\n--- Tool pending approval ---")
            print(f"Tool: {name}")
            if desc:
                print(desc)
            print("Arguments:")
            print(json.dumps(args, indent=2))
            choice = input("[a]pprove / [r]eject / [e]dit: ").strip().lower()
            if choice == "e":
                raw = input("New arguments JSON object (e.g. {\"command\": \"echo ok\"}): ").strip()
                try:
                    new_args = json.loads(raw)
                except json.JSONDecodeError:
                    print("Invalid JSON; treating as reject.")
                    decisions.append({"type": "reject", "message": "Invalid JSON for edit."})
                    continue
                decisions.append(
                    {
                        "type": "edit",
                        "edited_action": {"name": name, "args": new_args},
                    }
                )
            elif choice == "r":
                msg = input("Reject reason (optional): ").strip()
                d: dict[str, Any] = {"type": "reject"}
                if msg:
                    d["message"] = msg
                decisions.append(d)
            else:
                decisions.append({"type": "approve"})
    return {"decisions": decisions}


def _stream_turn(
    app,
    state_input: dict[str, Any] | Command,
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[Any, ...] | None, bool]:
    """Stream messages and values; surface interrupts from updates."""
    latest: dict[str, Any] | None = None
    interrupts: tuple[Any, ...] | None = None
    header_printed = False
    streamed_text = False

    for chunk in app.stream(
        state_input,
        config,
        stream_mode=["updates", "messages", "values"],
    ):
        if isinstance(chunk, tuple) and len(chunk) == 3:
            _, mode, payload = chunk
        elif isinstance(chunk, tuple) and len(chunk) == 2:
            mode, payload = chunk
        else:
            continue

        if mode == "messages" and isinstance(payload, tuple) and len(payload) == 2:
            msg, _meta = payload
            if isinstance(msg, AIMessageChunk) and msg.content:
                streamed_text = True
                if not header_printed:
                    print("\nAssistant> ", end="", flush=True)
                    header_printed = True
                print(msg.content, end="", flush=True)
        elif mode == "updates" and isinstance(payload, dict):
            if INTERRUPT_KEY in payload:
                ints = payload[INTERRUPT_KEY]
                interrupts = ints if isinstance(ints, tuple) else tuple(ints)
        elif mode == "values" and isinstance(payload, dict):
            latest = payload

    if header_printed:
        print()
    return latest, interrupts, streamed_text


def _final_ai_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return ""


def main():
    print("==================================================")
    print("Welcome to the LangGraph + deepagents Agentic App!")
    print("==================================================")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or api_key == "your_google_api_key_here":
        print("\nERROR: Please set GOOGLE_API_KEY in your .env file.")
        sys.exit(1)

    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes"):
        logger.info("LANGCHAIN_TRACING_V2 is on (LangSmith tracing).")

    print("\n[System] PDFs are not loaded at startup — no embedding cost until you ask.")
    print("         Use the agent: load_pdf_resource_tool / load_pdf_tool, then query_pdf_tool.")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    logger.info("Session thread_id=%s", thread_id)

    print("\nThe agent is ready! Shell commands require approval when using execute_command_tool.")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            query = input("\nUser> ")
            if query.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            if not query.strip():
                continue

            print("\nWorking...")
            inp: dict[str, Any] | Command = {"messages": [HumanMessage(content=query)]}

            streamed_any = False
            while True:
                result, interrupts, did_stream = _stream_turn(deep_agent_app, inp, config)
                streamed_any = streamed_any or did_stream
                if interrupts:
                    resume = _prompt_hitl_decisions(interrupts)
                    inp = Command(resume=resume)
                    continue
                break

            if not streamed_any and result and "messages" in result:
                final_message = _final_ai_text(result["messages"])
                if final_message.strip():
                    print("\n==================== Agent ====================")
                    print(final_message)
                    print("===============================================")

        except KeyboardInterrupt:
            print("\nInterrupted by user. Goodbye!")
            break
        except Exception as e:
            logger.exception("Graph execution failed")
            print(f"\n[Error] Graph execution failed: {e}")


if __name__ == "__main__":
    main()
