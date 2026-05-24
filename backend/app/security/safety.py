"""Layer 1 · Gemini safety filters (spec 09).

Configures ``ChatGoogleGenerativeAI`` with ``BLOCK_MEDIUM_AND_ABOVE`` on the
four content-harm categories. When Gemini blocks a generation, the streamed
response carries a ``finish_reason`` of ``SAFETY`` (or the prompt feedback flags
a block); the generator detects this and the router returns a safe message
instead of leaking the partial / blocked content.

The thresholds are deliberately *not* applied to civic-integrity or image
categories: this is a text-only docs chatbot and those add false positives on
legitimate FastAPI security questions (e.g. asking about auth, CORS, CSRF).
"""

from __future__ import annotations

from langchain_google_genai import HarmBlockThreshold, HarmCategory

# Finish reasons (and prompt-feedback block reasons) that indicate the model
# refused to answer for safety/policy reasons rather than finishing normally.
SAFETY_FINISH_REASONS: frozenset[str] = frozenset(
    {
        "SAFETY",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "BLOCKED_REASON_UNSPECIFIED",
    }
)


def default_safety_settings() -> dict[HarmCategory, HarmBlockThreshold]:
    """Return the layer-1 safety configuration for the generation call.

    ``BLOCK_MEDIUM_AND_ABOVE`` per spec: blocks content rated medium or high
    probability of harm, while letting low-probability technical content
    through (avoids over-blocking legitimate security questions).
    """
    threshold = HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    return {
        HarmCategory.HARM_CATEGORY_HARASSMENT: threshold,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: threshold,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: threshold,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: threshold,
    }


def is_safety_block(finish_reason: str | None) -> bool:
    """True if *finish_reason* indicates a layer-1 safety block."""
    if not finish_reason:
        return False
    return finish_reason.upper() in SAFETY_FINISH_REASONS
