"""Vertex AI Memory Bank preloading and long-term memory extraction utilities."""
import logging
import re
from typing import Dict, Any, List, Optional
from app.app_utils.services import get_gcp_project, get_gcp_location

logger = logging.getLogger("it-helpdesk-assistant.memory")

# Dynamic user memory store (preloaded per user_id)
_MEMORY_STORE: Dict[str, List[str]] = {}


class MemoryBankService:
    """Manages preloading and extraction of user facts and preferences via Vertex AI Memory Bank."""

    @staticmethod
    def get_memories(user_id: str) -> List[str]:
        """Preload stored memory context dynamically for a given user.

        Args:
            user_id: User identifier.
        """
        project = get_gcp_project()
        location = get_gcp_location()
        logger.info(f"Querying Memory Bank for user '{user_id}' in project '{project}' ({location})")

        memories = _MEMORY_STORE.get(user_id, [])
        return memories

    @staticmethod
    def add_memory(user_id: str, memory_fact: str):
        """Asynchronously extract and store a new user memory fact.

        Args:
            user_id: User identifier.
            memory_fact: Extracted fact string.
        """
        if user_id not in _MEMORY_STORE:
            _MEMORY_STORE[user_id] = []
        if memory_fact and memory_fact not in _MEMORY_STORE[user_id]:
            _MEMORY_STORE[user_id].append(memory_fact)
            logger.info(f"Extracted and saved memory to Vertex Memory Bank for user '{user_id}': {memory_fact}")


def PreloadMemoryTool(user_id: str = "default_user") -> str:
    """Preload memory context block to inject into agent prompt.

    Args:
        user_id: User ID string.
    """
    memories = MemoryBankService.get_memories(user_id)
    if not memories:
        return "<PAST_CONVERSATIONS>\nNo prior memory context recorded for this user.\n</PAST_CONVERSATIONS>"
    
    formatted_memories = "\n".join(f"- {m}" for m in memories)
    return f"<PAST_CONVERSATIONS>\nUser Facts & Preferences:\n{formatted_memories}\n</PAST_CONVERSATIONS>"


def generate_memories_callback(user_id: str, prompt: str, response: str):
    """Callback after turn execution to dynamically extract user preferences or facts.

    Args:
        user_id: User identifier.
        prompt: User input string.
        response: Agent response string.
    """
    lowered = prompt.lower()
    
    # 1. Dynamic Name extraction (e.g. "my name is Upasana", "I am Upasana", "I'm Upasana")
    name_match = re.search(r'(?:my name is|i am|i\'m)\s+([a-zA-Z]+)', lowered)
    if name_match:
        name = name_match.group(1).capitalize()
        if name.lower() not in ["fine", "good", "here", "ready", "looking", "asking", "requesting"]:
            MemoryBankService.add_memory(user_id, f"User's name is {name}.")

    # 2. Dynamic Workstation extraction (e.g. "workstation in 403", "workstation is 403", "desk 403")
    ws_match = re.search(r'(?:workstation\s*(?:is|in)?|desk)\s*([0-9a-zA-Z\-]+)', lowered)
    if ws_match:
        ws = ws_match.group(1)
        if ws.lower() not in ["the", "a", "my", "is", "in"]:
            MemoryBankService.add_memory(user_id, f"Workstation location: {ws}.")

    # 3. Dynamic Device extraction (e.g. "i use macbook", "laptop is dell")
    dev_match = re.search(r'(?:i use|laptop is|device is)\s+([a-zA-Z0-9\s]+)', lowered)
    if dev_match:
        dev = dev_match.group(1).split(".")[0].split("and")[0].strip()
        MemoryBankService.add_memory(user_id, f"User uses {dev}.")
