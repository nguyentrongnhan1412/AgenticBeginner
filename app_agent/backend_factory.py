"""Composite backend: ephemeral agent files + on-disk project skills for SkillsMiddleware."""

from pathlib import Path

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.filesystem import FilesystemBackend
from deepagents.backends.state import StateBackend
from langgraph.prebuilt import ToolRuntime

_APP_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_PROJECT_ROOT = _APP_ROOT / "skills" / "project"


def agent_backend_factory(rt: ToolRuntime) -> CompositeBackend:
    skills_fs = FilesystemBackend(
        root_dir=str(_SKILLS_PROJECT_ROOT),
        virtual_mode=True,
    )
    return CompositeBackend(
        default=StateBackend(rt),
        routes={"/skills/project/": skills_fs},
    )
