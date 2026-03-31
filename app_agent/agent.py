"""Main Agent Definition using deepagents.create_deep_agent."""

import logging
from pathlib import Path

from langchain_core.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from utils import get_model, think_tool
from tools.pdf_qa import (
    load_pdf,
    load_pdf_from_resource,
    list_pdf_resources,
    query_pdf,
)
from tools.sandbox_modal import sandbox_exec
from skills.excel_to_csv import excel_to_csv
from skills.registry import list_skill_names, load_skill

from app_agent.backend_factory import agent_backend_factory
from app_agent.prompts import MAIN_AGENT_INSTRUCTIONS, EXCEL_SPECIALIST_INSTRUCTIONS

logger = logging.getLogger(__name__)

# ============================================================================
# Core Tools Wrapped for the Agent
# ============================================================================


@tool
def load_pdf_tool(path: str) -> str:
    """Load or replace the PDF used for document Q&A (host filesystem path).

    Call only when the user needs PDF-based answers — this runs chunking + embeddings.
    After success, use query_pdf_tool for questions.

    Args:
        path: Absolute or relative path to a .pdf file on the host machine.

    Returns:
        Status message; on failure, explains what went wrong.
    """
    logger.info("load_pdf_tool path=%s", path)
    p = Path(path)
    if not p.suffix.lower() == ".pdf":
        return "Error: path must be a .pdf file."
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        load_pdf(str(p.resolve()))
        return f"PDF loaded and indexed: {p.resolve()}"
    except Exception as e:
        logger.exception("load_pdf_tool failed")
        return f"Error loading PDF: {e}"


@tool
def list_pdf_resources_tool() -> str:
    """List PDF files in the resource folder (default ./resource under the app).

    Optional env: PDF_RESOURCE_DIR — absolute path or path relative to app root.
    Use this before load_pdf_resource_tool when the user does not give a full path.
    """
    logger.info("list_pdf_resources_tool")
    return list_pdf_resources()


@tool
def load_pdf_resource_tool(filename: str) -> str:
    """Load a PDF from the resource folder by file name only (replaces the active index).

    Use only when document Q&A is needed — triggers chunking + embeddings for that file.

    Args:
        filename: Base name, e.g. Security.pdf or Security ( .pdf is added if omitted).

    Returns:
        Status message; on failure, suggests listing available PDFs.
    """
    logger.info("load_pdf_resource_tool filename=%s", filename)
    return load_pdf_from_resource(filename)


@tool
def query_pdf_tool(question: str) -> str:
    """Ask a question about the loaded PDF document.

    Args:
        question: The user's question about the text.

    Returns:
        Relevant excerpts from the PDF, with page numbers.
    """
    logger.info("query_pdf_tool question_chars=%s", len(question))
    return query_pdf(question, k=4)


@tool
def list_registered_skills_tool() -> str:
    """List skill names registered in the Python skills registry (invoke via invoke_registered_skill_tool)."""
    names = list_skill_names()
    return "Registered skills: " + (", ".join(names) if names else "(none)")


@tool
def invoke_registered_skill_tool(skill_name: str, input_text: str) -> str:
    """Run a registered skill by name with natural-language input (often includes a file path).

    Args:
        skill_name: Registry key, e.g. excel_to_csv.
        input_text: Instruction string; skills that need paths parse them from this text.

    Returns:
        Skill output message.
    """
    logger.info("invoke_registered_skill_tool name=%s", skill_name)
    try:
        fn = load_skill(skill_name)
        return fn(input_text)
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.exception("invoke_registered_skill_tool failed")
        return f"Error running skill: {e}"


@tool
def execute_command_tool(command: str) -> str:
    """Execute a shell command in a secure Modal Sandbox.

    Use this for terminal tasks that do not require host files. The sandbox does
    not share the host filesystem with Excel/PDF tools unless files are copied in.

    Args:
        command: The shell command to run.

    Returns:
        The combined stdout/stderr output from the sandbox.
    """
    logger.info("execute_command_tool command_preview=%s", command[:200])
    try:
        return sandbox_exec(command)
    except Exception as e:
        logger.exception("execute_command_tool failed")
        return f"Error executing command: {e}"


@tool
def convert_excel_tool(filename: str) -> str:
    """Convert an Excel (.xlsx) file to CSV on the host filesystem.

    Args:
        filename: Path to the Excel file on the host.

    Returns:
        Success or error message.
    """
    logger.info("convert_excel_tool filename=%s", filename)
    return excel_to_csv(filename)


# ============================================================================
# Sub-Agents
# ============================================================================

excel_specialist = {
    "name": "excel-specialist",
    "description": "Delegate tasks involving Excel (.xlsx) file conversions or transformations here.",
    "system_prompt": EXCEL_SPECIALIST_INSTRUCTIONS,
    "tools": [convert_excel_tool, invoke_registered_skill_tool, list_registered_skills_tool],
}

# ============================================================================
# Main Orchestrator
# ============================================================================

model = get_model()

checkpointer = InMemorySaver()

app = create_deep_agent(
    name="main-orchestrator",
    model=model,
    tools=[
        load_pdf_tool,
        list_pdf_resources_tool,
        load_pdf_resource_tool,
        query_pdf_tool,
        list_registered_skills_tool,
        invoke_registered_skill_tool,
        execute_command_tool,
        think_tool,
    ],
    system_prompt=MAIN_AGENT_INSTRUCTIONS,
    subagents=[excel_specialist],
    backend=agent_backend_factory,
    skills=["/skills/project/"],
    checkpointer=checkpointer,
    interrupt_on={
        "execute_command_tool": {
            "allowed_decisions": ["approve", "reject", "edit"],
            "description": (
                "Modal sandbox shell command — confirm before execution. "
                "Args JSON follows."
            ),
        }
    },
)
