"""Loading and rendering of versioned prompt templates from ``prompts/``.

Prompts live as Markdown files at the repo root ``prompts/`` directory. Each
file starts with an HTML-comment metadata block (version, model_tier, …) which
is stripped before rendering. Placeholders use ``{{name}}`` syntax.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# repo_root/prompts ; this file is backend/app/retrieval/prompts.py
_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"

_FRONTMATTER_RE = re.compile(r"^\s*<!--.*?-->\s*", re.DOTALL)


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the body of ``prompts/<name>.md`` with metadata stripped."""
    path = _PROMPTS_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    return _FRONTMATTER_RE.sub("", raw, count=1).strip()


def render(template: str, **values: str) -> str:
    """Substitute ``{{key}}`` placeholders with *values* (literal, no eval)."""
    out = template
    for key, value in values.items():
        out = out.replace(f"{{{{{key}}}}}", value)
    return out
