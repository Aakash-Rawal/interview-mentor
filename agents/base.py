"""Shared agent helpers: Anthropic client, skill loading, Claude calls.

Every call sends the large, static system prompt (skill markdown + persona) as
a cache-controlled block so repeated turns on the same topic re-bill the prefix
at the cached rate. Adaptive thinking is on for every call; `effort` trades
depth for latency per call site.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

import config


class ClaudeError(RuntimeError):
    """A user-presentable failure talking to Claude."""


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    if not config.ANTHROPIC_API_KEY:
        raise ClaudeError("ANTHROPIC_API_KEY is not set. Add it to .env and restart the app.")
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


@lru_cache(maxsize=32)
def load_skill(topic: str) -> str:
    """Load and cache the markdown skill file for a topic. '' if none/missing."""
    rel = config.SKILL_FILES.get(topic)
    if not rel:
        return ""
    path = config.SKILLS_DIR / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _request(system: str, messages: list[dict], max_tokens: int, effort: str,
             model: str | None) -> dict:
    return dict(
        model=model or config.DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
    )


def _friendly(exc: Exception) -> ClaudeError:
    if isinstance(exc, anthropic.AuthenticationError):
        return ClaudeError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY in .env.")
    if isinstance(exc, anthropic.NotFoundError):
        return ClaudeError("The selected model was not found. Pick another model in Settings.")
    if isinstance(exc, anthropic.RateLimitError):
        return ClaudeError("Rate limited by Anthropic. Wait a moment and try again.")
    if isinstance(exc, anthropic.APIStatusError):
        return ClaudeError(f"Anthropic API error {exc.status_code}: {exc.message}")
    if isinstance(exc, anthropic.APIConnectionError):
        return ClaudeError("Could not reach the Anthropic API. Check your network.")
    return ClaudeError(str(exc))


def call_claude(system: str, messages: list[dict], max_tokens: int = config.MAX_TOKENS_LONG,
                effort: str = config.EFFORT_SCORE, model: str | None = None) -> str:
    """One text-in/text-out call. Raises ClaudeError on failure, refusal, or truncation.

    Uses the streaming transport under the hood so large max_tokens (scoring,
    generation, enrichment) never trip HTTP timeouts; callers still get a string.
    """
    try:
        with get_client().messages.stream(
                **_request(system, messages, max_tokens, effort, model)) as stream:
            resp = stream.get_final_message()
    except anthropic.APIError as exc:
        raise _friendly(exc) from exc
    if resp.stop_reason == "refusal":
        raise ClaudeError("Claude declined to answer this request.")
    if resp.stop_reason == "max_tokens":
        raise ClaudeError(f"Response was cut off at {max_tokens} tokens; ask for a smaller batch.")
    return "".join(block.text for block in resp.content if block.type == "text")


def stream_claude(system: str, messages: list[dict], max_tokens: int = config.MAX_TOKENS_CHAT,
                  effort: str = config.EFFORT_CHAT, model: str | None = None):
    """Yield text deltas as they arrive. Callers accumulate for the full reply."""
    try:
        with get_client().messages.stream(
                **_request(system, messages, max_tokens, effort, model)) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
            if final.stop_reason == "refusal":
                raise ClaudeError("Claude declined to continue this conversation.")
    except anthropic.APIError as exc:
        raise _friendly(exc) from exc


def check_model(model: str) -> tuple[bool, str]:
    """Metadata-only check that the key works and the model exists. No token cost."""
    try:
        m = get_client().models.retrieve(model)
        return True, f"API key valid; model '{m.id}' reachable."
    except ClaudeError as exc:
        return False, str(exc)
    except anthropic.APIError as exc:
        return False, str(_friendly(exc))
