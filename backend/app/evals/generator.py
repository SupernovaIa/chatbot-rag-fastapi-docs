"""Non-streaming answer generator for evals (Gemini Flash).

The chat feature streams tokens over SSE (spec 05); evals need the whole answer
as a string to feed the judge. This adapter reuses the same prompt builder
(``build_prompt``) and the same model (Gemini Flash) so the answer scored by
the judge matches what production would generate — only the transport differs
(``invoke`` instead of ``astream``).
"""

from __future__ import annotations

import logging

from app.chat.prompts import build_prompt
from app.evals.ports import AnswerGeneratorPort
from app.retrieval.llm import _extract_text
from app.retrieval.models import Candidate, Turn

logger = logging.getLogger(__name__)


class GeminiAnswerGenerator:
    """Generates a complete answer with Gemini Flash via LangChain ``invoke``."""

    def __init__(self, api_key: str, model: str, timeout: float = 60.0) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.0,
            timeout=timeout,
        )

    def generate(
        self, query: str, history: list[Turn], candidates: list[Candidate]
    ) -> str:
        messages = build_prompt(query=query, history=history, candidates=candidates)
        response = self._llm.invoke(messages)
        return _extract_text(response.content)


# Satisfy the Protocol at type-check time.
_g: AnswerGeneratorPort = GeminiAnswerGenerator.__new__(GeminiAnswerGenerator)  # type: ignore[assignment]
