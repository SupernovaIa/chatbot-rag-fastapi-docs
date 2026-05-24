#!/usr/bin/env python3
"""Measure the impact of Gemini implicit caching on the RAG pipeline.

Sends N consecutive turns to the chat endpoint (same session, varying queries)
and records the cached_content_token_count reported by the API for each turn.
Computes the cache hit rate, token savings and estimated USD savings.

Usage
-----
    # With the stack running (docker compose up -d):
    python scripts/measure_caching_impact.py

    # Custom parameters:
    python scripts/measure_caching_impact.py \\
        --turns 10 \\
        --base-url http://localhost:8000 \\
        --email user@example.com \\
        --password secret \\
        --output docs/caching-impact.md

    # Dry-run: just print the queries that would be sent
    python scripts/measure_caching_impact.py --dry-run

Requirements
------------
    pip install httpx  (or: uv run python scripts/measure_caching_impact.py)

Note on free tier
-----------------
The Gemini free tier does not expose cached_content_token_count in all
situations (Issue #12 — LangChain streaming limitation).  When the field is
absent or 0, this script marks the turn as 'caching_unavailable' and computes
a hypothetical saving based on the system prompt token count.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Gemini pricing — imported from the canonical source in the backend.
# Falls back to hardcoded values only when the backend package is not on the
# path (e.g. running the script outside the project virtualenv).
# ---------------------------------------------------------------------------

def _load_flash_rates() -> dict[str, float]:
    """Return the Flash pricing dict from cost.py, or fall back to defaults."""
    _repo_backend = os.path.join(os.path.dirname(__file__), "..", "backend")
    sys.path.insert(0, _repo_backend)
    try:
        from app.observability.cost import pricing_for_model  # type: ignore[import]
        return pricing_for_model("gemini-3.5-flash")
    except ImportError:
        # Running outside the project venv — use embedded copy.
        # Keep in sync with backend/app/observability/cost.py _PRICING.
        return {"input": 0.30, "cached_input": 0.075, "output": 1.25}
    finally:
        sys.path.pop(0)


_FLASH_RATES = _load_flash_rates()

# Approximate system prompt token count (measured with SDK, block CH)
_SYSTEM_PROMPT_TOKENS = 1_200

# Default test queries (varied to exercise different parts of the corpus)
_DEFAULT_QUERIES = [
    "¿Cómo se define un endpoint básico en FastAPI?",
    "¿Para qué sirven los Path Parameters?",
    "¿Qué diferencia hay entre parámetros de query y de ruta?",
    "¿Cómo se validan los datos de entrada con Pydantic?",
    "¿Cómo se documenta automáticamente una API con FastAPI?",
    "¿Qué es el modo async en FastAPI y cuándo usarlo?",
    "¿Cómo se añade autenticación con OAuth2 en FastAPI?",
    "¿Cómo se manejan los errores HTTP en FastAPI?",
    "¿Para qué sirve el sistema de dependencias de FastAPI?",
    "¿Cómo se hacen tests de una aplicación FastAPI?",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    turn_idx: int
    query: str
    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: float = 0.0
    duration_ms: float = 0.0
    error: Optional[str] = None
    caching_available: bool = False


@dataclass
class CachingReport:
    turns: list[TurnResult] = field(default_factory=list)
    model: str = "gemini-3.5-flash"
    base_url: str = "http://localhost:8000"
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def successful_turns(self) -> list[TurnResult]:
        return [t for t in self.turns if t.error is None]

    @property
    def caching_turns(self) -> list[TurnResult]:
        return [t for t in self.successful_turns if t.caching_available]

    @property
    def cache_hit_rate(self) -> float:
        s = self.successful_turns
        return len(self.caching_turns) / len(s) if s else 0.0

    @property
    def mean_cached_tokens(self) -> float:
        ct = self.caching_turns
        return sum(t.cached_tokens for t in ct) / len(ct) if ct else 0.0

    @property
    def mean_prompt_tokens(self) -> float:
        s = self.successful_turns
        return sum(t.prompt_tokens for t in s) / len(s) if s else 0.0

    @property
    def mean_output_tokens(self) -> float:
        s = self.successful_turns
        return sum(t.output_tokens for t in s) / len(s) if s else 0.0

    def _token_cost(self, non_cached: int, cached: int, output: int) -> float:
        M = 1_000_000.0
        return (
            non_cached / M * _FLASH_RATES["input"]
            + cached / M * _FLASH_RATES["cached_input"]
            + output / M * _FLASH_RATES["output"]
        )

    @property
    def actual_cost_usd(self) -> float:
        total = 0.0
        for t in self.successful_turns:
            nc = max(0, t.prompt_tokens - t.cached_tokens)
            total += self._token_cost(nc, t.cached_tokens, t.output_tokens)
        return total

    @property
    def hypothetical_cost_no_cache_usd(self) -> float:
        """Cost if all prompt tokens were billed at full input rate."""
        total = 0.0
        for t in self.successful_turns:
            total += self._token_cost(t.prompt_tokens, 0, t.output_tokens)
        return total

    @property
    def savings_usd(self) -> float:
        return max(0.0, self.hypothetical_cost_no_cache_usd - self.actual_cost_usd)

    @property
    def savings_pct(self) -> float:
        base = self.hypothetical_cost_no_cache_usd
        return self.savings_usd / base * 100 if base > 0 else 0.0

    @property
    def mean_ttft_ms(self) -> float:
        s = self.successful_turns
        return sum(t.ttft_ms for t in s) / len(s) if s else 0.0

    @property
    def mean_duration_ms(self) -> float:
        s = self.successful_turns
        return sum(t.duration_ms for t in s) / len(s) if s else 0.0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _login(session: "httpx.Client", base_url: str, email: str, password: str) -> None:  # type: ignore[name-defined]
    """Authenticate and store the cookie in *session*."""
    resp = session.post(
        f"{base_url}/auth/login",
        data={"username": email, "password": password},
    )
    if resp.status_code not in (200, 204):
        print(f"[ERROR] Login failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Logged in as {email}")


def _send_turn(
    session: "httpx.Client",  # type: ignore[name-defined]
    base_url: str,
    query: str,
    session_id: Optional[str],
) -> tuple[dict, float, float]:
    """Send a chat turn and return (usage_dict, ttft_ms, duration_ms)."""
    payload: dict = {"query": query}
    if session_id:
        payload["session_id"] = session_id

    start = time.perf_counter()
    first_token_time: Optional[float] = None
    usage: dict = {}
    session_id_out: Optional[str] = None

    with session.stream(
        "POST",
        f"{base_url}/chat/",
        json=payload,
        timeout=120.0,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        for line in resp.iter_lines():
            now = time.perf_counter()
            if not line.startswith("data:"):
                continue
            raw = line[len("data:"):].strip()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")
            if etype == "token" and first_token_time is None:
                first_token_time = now
            elif etype == "citations":
                # The usage metadata is not in the SSE stream; it's on the span.
                # We parse session_id from items if available.
                pass
            elif etype == "usage":
                # In case we add a usage event later
                usage = event.get("usage", {})

    duration_ms = (time.perf_counter() - start) * 1000.0
    ttft_ms = ((first_token_time or start) - start) * 1000.0
    return usage, ttft_ms, duration_ms


def _fetch_span_usage(
    base_url: str,
    session: "httpx.Client",  # type: ignore[name-defined]
    session_id: str,
    turn_idx: int,
    *,
    project: str = "chatbot-rag-fastapi-docs",
) -> Optional[dict]:
    """Query Phoenix spans API for the generate span of this turn.

    The ``generate`` span includes a ``session_id`` attribute (set in
    chat/router.py block F) so we can filter client-side after fetching recent
    spans.

    Phoenix REST endpoint: GET /v1/projects/{project}/spans  (NOT /v1/spans).
    """
    phoenix_base = base_url.replace(":8000", ":6006")
    endpoint = f"{phoenix_base}/v1/projects/{project}/spans"
    try:
        resp = session.get(
            endpoint,
            params={"limit": 100},  # enough for one measurement run
            timeout=10.0,
        )
        if resp.status_code != 200:
            print(
                f"[WARN] Phoenix returned {resp.status_code} from {endpoint}",
                file=sys.stderr,
            )
            return None

        data = resp.json()
        spans = data.get("data", [])

        # Keep only "generate" spans that belong to this session.
        # The generate span records session_id as an attribute (block F).
        matches = [
            s for s in spans
            if s.get("name") == "generate"
            and str(s.get("attributes", {}).get("session_id", "")) == str(session_id)
        ]

        if not matches:
            return None

        # Phoenix typically returns spans newest-first; use the most recent match.
        attrs = matches[0].get("attributes", {})
        return {
            "prompt_tokens": int(attrs.get("prompt_tokens", 0)),
            "cached_tokens": int(attrs.get("cached_tokens", 0)),
            "output_tokens": int(attrs.get("output_tokens", 0)),
            "ttft_ms": float(attrs.get("ttft_ms", 0.0)),
            "caching_available": bool(attrs.get("caching_available", False)),
        }
    except Exception as exc:
        print(f"[WARN] Could not fetch span from Phoenix: {exc}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------


def render_report(report: CachingReport) -> str:
    lines = [
        "# Informe de impacto del caching implícito — Gemini",
        "",
        f"> Generado: {report.timestamp}",
        f"> Modelo: `{report.model}`",
        f"> Endpoint: `{report.base_url}`",
        f"> Session ID: `{report.session_id}`",
        "",
        "## Resumen ejecutivo",
        "",
    ]

    s = report.successful_turns
    if not s:
        lines += ["No hay turnos completados sin error.", ""]
        return "\n".join(lines)

    lines += [
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Turnos enviados | {len(report.turns)} |",
        f"| Turnos completados | {len(s)} |",
        f"| Turnos con caching activo | {len(report.caching_turns)} |",
        f"| Cache hit rate | {report.cache_hit_rate * 100:.1f} % |",
        f"| Tokens prompt (media) | {report.mean_prompt_tokens:.0f} |",
        f"| Tokens cacheados (media, cuando aplica) | {report.mean_cached_tokens:.0f} |",
        f"| Tokens output (media) | {report.mean_output_tokens:.0f} |",
        f"| TTFT p50 (media) | {report.mean_ttft_ms:.0f} ms |",
        f"| Duración total (media) | {report.mean_duration_ms:.0f} ms |",
        f"| Coste real estimado | ${report.actual_cost_usd:.6f} |",
        f"| Coste hipotético (sin caché) | ${report.hypothetical_cost_no_cache_usd:.6f} |",
        f"| Ahorro estimado | ${report.savings_usd:.6f} ({report.savings_pct:.1f} %) |",
        "",
        "## Detalle por turno",
        "",
        "| Turno | Prompt tokens | Cached tokens | Output tokens | TTFT (ms) | Coste USD | Caché |",
        "|-------|--------------|---------------|---------------|-----------|-----------|-------|",
    ]

    for t in report.turns:
        if t.error:
            lines.append(
                f"| {t.turn_idx} | — | — | — | — | — | ❌ ERROR: {t.error[:40]} |"
            )
        else:
            nc = max(0, t.prompt_tokens - t.cached_tokens)
            M = 1_000_000.0
            cost = (
                nc / M * _FLASH_RATES["input"]
                + t.cached_tokens / M * _FLASH_RATES["cached_input"]
                + t.output_tokens / M * _FLASH_RATES["output"]
            )
            cache_icon = "✅" if t.caching_available else "⬜"
            lines.append(
                f"| {t.turn_idx} | {t.prompt_tokens} | {t.cached_tokens} "
                f"| {t.output_tokens} | {t.ttft_ms:.0f} | ${cost:.6f} | {cache_icon} |"
            )

    lines += [
        "",
        "## Interpretación",
        "",
        "### Tokens y coste",
        "",
        "Los conteos de tokens se leen de `chunk.usage_metadata` (campo directo del",
        "`AIMessageChunk`). LangChain-Google-GenAI usa nombres distintos a los del",
        "proto de Gemini:",
        "",
        "| LangChain | Gemini proto | Campo en UsageMeta |",
        "|---|---|---|",
        "| `input_tokens` | `prompt_token_count` | `prompt_token_count` |",
        "| `output_tokens` | `candidates_token_count + thoughts_token_count` | `candidates_token_count` |",
        "| `input_token_details[\"cache_read\"]` | `cached_content_token_count` | `cached_content_token_count` |",
        "",
        "Nota: `output_tokens` incluye reasoning tokens internos de modelos con thinking",
        "(p. ej. Gemini Flash). Ambos se facturan al precio de output.",
        "",
        "### Caching implícito de Gemini",
        "",
        "El caching implícito aplica cuando el prefijo del prompt supera",
        f"los **1 024 tokens**. El system prompt de este proyecto mide ~{_SYSTEM_PROMPT_TOKENS} tokens,",
        "por lo que el prefijo es elegible en tamaño.",
        "",
        "Si `cached_tokens = 0` en todos los turnos, las causas probables son:",
        "",
        "1. **Prefijo inestable**: cada turno incluye chunks de retrieval distintos,",
        "   lo que cambia el prefijo y hace que Gemini no encuentre una entrada cacheada.",
        "2. **Tier gratuito**: el caching implícito puede no estar disponible o garantizado",
        "   en el free tier de Google AI Studio.",
        "3. **TTL no alcanzado**: el caching requiere que el mismo prefijo se repita",
        "   varias veces en una ventana de tiempo.",
        "",
        "### Separación de fases",
        "",
        "- **Rewriter y reranker**: el prefijo varía por turno (incluye candidatos/historial).",
        "  El caching implícito no aplica aquí.",
        "- **Generador**: el system prompt es el prefijo estable, pero los chunks de",
        "  retrieval varían. El caching aplica solo si el sistema prompt ocupa la mayor",
        "  parte del prefijo y los chunks son secundarios.",
        "",
        "### Precios usados",
        "",
        f"- Input: ${_FLASH_RATES['input']}/M tokens",
        f"- Input cacheado: ${_FLASH_RATES['cached_input']}/M tokens",
        f"- Output: ${_FLASH_RATES['output']}/M tokens",
        "",
        "Ver `docs/cost-model.md` para el modelo completo.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure Gemini implicit caching impact on the RAG pipeline."
    )
    p.add_argument(
        "--turns", type=int, default=5,
        help="Number of turns to send (default: 5).",
    )
    p.add_argument(
        "--base-url", default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000).",
    )
    p.add_argument("--email", default="test@example.com", help="Login email.")
    p.add_argument("--password", default="testpassword123", help="Login password.")
    p.add_argument(
        "--output",
        default="docs/caching-impact.md",
        help="Output markdown file (default: docs/caching-impact.md).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print the queries that would be sent without making requests.",
    )
    p.add_argument(
        "--no-write", action="store_true",
        help="Print the report to stdout instead of writing to --output.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    queries = _DEFAULT_QUERIES[: args.turns]
    if len(queries) < args.turns:
        # Cycle through queries if more turns than default questions
        queries = (queries * (args.turns // len(queries) + 1))[: args.turns]

    if args.dry_run:
        print(f"Would send {len(queries)} turns to {args.base_url}:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")
        return

    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx is required. Install with: pip install httpx", file=sys.stderr)
        sys.exit(1)

    report = CachingReport(base_url=args.base_url)
    import uuid
    session_id = str(uuid.uuid4())
    report.session_id = session_id

    with httpx.Client(base_url=args.base_url, follow_redirects=True) as client:
        _login(client, args.base_url, args.email, args.password)

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Sending: {query[:60]}...")
            result = TurnResult(turn_idx=i, query=query)

            try:
                usage, ttft_ms, duration_ms = _send_turn(
                    client, args.base_url, query, session_id
                )
                result.ttft_ms = ttft_ms
                result.duration_ms = duration_ms

                # Try to get token counts from Phoenix spans.
                # BatchSpanProcessor flushes on a schedule; 3 s is enough for
                # local Phoenix but may still be too short for the very first turn.
                time.sleep(3.0)
                span_data = _fetch_span_usage(
                    args.base_url, client, session_id, i
                )
                if span_data:
                    result.prompt_tokens = span_data.get("prompt_tokens", 0)
                    result.cached_tokens = span_data.get("cached_tokens", 0)
                    result.output_tokens = span_data.get("output_tokens", 0)
                    result.ttft_ms = span_data.get("ttft_ms", ttft_ms)
                    result.caching_available = span_data.get("caching_available", False)
                else:
                    # Fallback: usage from SSE stream (may not include tokens)
                    result.prompt_tokens = usage.get("prompt_token_count", 0)
                    result.cached_tokens = usage.get("cached_content_token_count", 0)
                    result.output_tokens = usage.get("candidates_token_count", 0)
                    result.caching_available = result.cached_tokens > 0

                cache_status = "✅" if result.caching_available else "⬜"
                print(
                    f"  → prompt={result.prompt_tokens} cached={result.cached_tokens} "
                    f"output={result.output_tokens} ttft={result.ttft_ms:.0f}ms "
                    f"duration={result.duration_ms:.0f}ms caching={cache_status}"
                )

            except Exception as exc:
                result.error = str(exc)
                print(f"  → ERROR: {exc}", file=sys.stderr)

            report.turns.append(result)

    md = render_report(report)

    if args.no_write:
        print(md)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"\n[INFO] Report written to {out}")

    # Summary to stdout
    print("\n=== Summary ===")
    print(f"Turns: {len(report.turns)} sent, {len(report.successful_turns)} OK")
    print(f"Cache hit rate: {report.cache_hit_rate * 100:.1f}%")
    print(f"Mean TTFT: {report.mean_ttft_ms:.0f} ms")
    print(f"Estimated savings: ${report.savings_usd:.6f} ({report.savings_pct:.1f}%)")


if __name__ == "__main__":
    main()
