"""Shared utilities for the LangGraph Agentic App.

Inspired by the deep_research example pattern of centralising shared
infrastructure (model factory, reflection tools) to keep agent files thin.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

load_dotenv()


# ---------------------------------------------------------------------------
# Shared model factory
# ---------------------------------------------------------------------------

def get_model(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Return a configured ChatGoogleGenerativeAI instance.

    Reads GOOGLE_API_KEY and GEMINI_MODEL from the environment.
    All agents should call this instead of constructing the model themselves.

    Args:
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        A ready-to-use ChatGoogleGenerativeAI model.
    """
    return ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# think_tool — adapted from deep_research example
# ---------------------------------------------------------------------------

@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection before and after key decisions.

    Inspired by the deep_research example. Use this to pause and assess:
    - After retrieving PDF chunks: do I have enough to answer?
    - Before running a sandbox command: is the extracted command correct?
    - When uncertain: what is the best next step?

    Reflection should cover:
    1. What information do I have so far?
    2. What is still missing or unclear?
    3. What should I do next?

    Args:
        reflection: Detailed reflection on current state and next steps.

    Returns:
        Confirmation that the reflection was recorded.
    """
    return f"[think] {reflection}"
