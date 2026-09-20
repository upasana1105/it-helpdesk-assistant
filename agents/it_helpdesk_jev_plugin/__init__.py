"""Single-Agent (`1-Box`) Jev Integration via ADK `BasePlugin` (`it_helpdesk_jev_plugin`)."""
from pathlib import Path
import sys

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from .agent import app, root_agent

__all__ = ["app", "root_agent"]
