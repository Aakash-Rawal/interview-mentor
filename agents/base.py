"""Shared agent helpers: Anthropic client, skill loading, Claude calls.

Keeps every agent thin. In Phase 3 get_client() will be swapped to decrypt a
per-user Fernet key; for now it uses the single key from config.
"""
from functools import lru_cache

import anthropic

import config


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


@lru_cache(maxsize=32)
def load_skill(topic: str) -> str:
    """Load and cache the markdown skill file for a topic. '' if none/missing."""
    rel = config.SKILL_FILES.get(topic)
    if not rel:
        return ""
    path = config.SKILLS_DIR / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def call_claude(system: str, messages: list[dict],
                max_tokens: int = config.MAX_TOKENS) -> str:
    """One text-in/text-out call to Claude. messages = [{role, content}, ...].

    The system prompt (which carries the large, static skill-file content) is
    sent as a cache-controlled block. Repeated calls within the cache window
    re-bill that prefix at ~10% — meaningful since every turn in a topic
    prepends the same skill markdown.
    """
    resp = get_client().messages.create(
        model=config.MODEL_NAME,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=messages,
    )
    return "".join(block.text for block in resp.content if block.type == "text")
