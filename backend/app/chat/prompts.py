"""Prompt building for the chat feature.

``build_prompt`` assembles the final message list for the generation call.
The stable prefix (system.md) always comes first so Gemini's implicit context
caching can kick in (spec 07). Dynamic content (context, history, query)
follows.

Prompt structure (ordered for caching):
  1. SystemMessage — system.md contents (stable; changes rarely)
  2. HumanMessage  — context chunks + history + current query (dynamic)

The history is embedded in the human turn to keep the structure simple and
avoid alternating HumanMessage/AIMessage pairs that would push the stable
system prefix further from the caching window boundary. This is a deliberate
trade-off: caching efficiency > conversational structure in the message list.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.chat.models import Citation
from app.retrieval.models import Candidate, Turn

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system.md"

_system_prompt_cache: str | None = None


def _load_system_prompt() -> str:
    """Load system.md, stripping the YAML front-matter block."""
    global _system_prompt_cache
    if _system_prompt_cache is not None:
        return _system_prompt_cache

    raw = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    # Strip YAML front-matter delimited by --- lines.
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            raw = parts[2].strip()

    _system_prompt_cache = raw
    logger.debug(
        "Loaded system prompt (%d chars, sha=%s)",
        len(raw),
        hashlib.sha256(raw.encode()).hexdigest()[:8],
    )
    return raw


def system_prompt_hash() -> str:
    """Return a short SHA-256 of the current system prompt (for tracing)."""
    text = _load_system_prompt()
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def build_context_block(candidates: list[Candidate]) -> str:
    """Format retrieved chunks into the context block injected into the prompt."""
    if not candidates:
        return "*(No relevant documentation found for this query.)*"

    parts: list[str] = []
    for i, c in enumerate(candidates, start=1):
        parts.append(
            f"[{i}] **{c.section}** ({c.source})\n{c.content.strip()}"
        )
    return "\n\n---\n\n".join(parts)


def build_history_block(history: list[Turn]) -> str:
    """Format conversation history as a readable block."""
    if not history:
        return ""
    lines: list[str] = ["## Previous conversation"]
    for turn in history:
        lines.append(f"**User:** {turn.question}")
        lines.append(f"**Assistant:** {turn.answer}")
    return "\n".join(lines)


def build_prompt(
    query: str,
    history: list[Turn],
    candidates: list[Candidate],
) -> list[SystemMessage | HumanMessage]:
    """Build the message list for the Gemini generation call.

    Returns a two-element list: [SystemMessage(stable prefix), HumanMessage(dynamic)].

    The stable prefix is identical across every call (spec 07). Only the
    HumanMessage changes, so Gemini can cache the system token prefix.
    """
    system = _load_system_prompt()
    context_block = build_context_block(candidates)
    history_block = build_history_block(history)

    human_parts: list[str] = [
        "## Retrieved documentation context",
        context_block,
    ]
    if history_block:
        human_parts.append(history_block)
    human_parts.append(f"## Current question\n{query}")

    human_content = "\n\n".join(human_parts)

    return [
        SystemMessage(content=system),
        HumanMessage(content=human_content),
    ]


def citations_from_candidates(candidates: list[Candidate]) -> list[Citation]:
    """Convert retrieval candidates to Citation objects for the SSE payload."""
    return [
        Citation(
            source=c.source,
            section=c.section,
            chunk_hash=c.chunk_hash,
        )
        for c in candidates
    ]
