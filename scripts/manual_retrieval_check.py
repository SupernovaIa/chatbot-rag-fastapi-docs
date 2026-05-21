#!/usr/bin/env python3
"""Compute recall@5 and MRR for the retrieval pipeline over the gold dataset.

Runs the full pipeline (rewrite → hybrid → rerank) against the 35 single-turn
gold examples and reports retrieval quality. The 5 ``no_se`` examples have no
``gold_chunks`` (they are un-answerable by design), so recall@5 / MRR are
computed over the 30 answerable single-turn examples; the ``no_se`` set is
reported separately for context.

A retrieved candidate matches a gold chunk when (source, section) are equal —
the same keys the gold dataset was validated against (spec 08).

Usage (from repo root, stack up, .env loaded):
    python scripts/manual_retrieval_check.py [--top-k 5] [--no-rerank]

Environment: GOOGLE_API_KEY, DATABASE_URL, CORPUS_SHA (optional).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Tracing is best-effort; from the host the 'phoenix' service name does not
# resolve, so disable export to avoid noisy retries during the offline check.
os.environ.setdefault("DISABLE_TRACING", "1")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("manual_retrieval_check")

_GOLD_PATH = _REPO_ROOT / "corpus" / "sample" / "fastapi-docs" / "evals" / "gold.jsonl"
_DATABASE_URL_DEFAULT = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbot_rag"


def _load_gold() -> list[dict]:
    return [json.loads(line) for line in _GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _gold_keys(example: dict) -> set[tuple[str, str]]:
    return {(gc["source"], gc["section"]) for gc in example["gold_chunks"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip the LLM reranker; measure hybrid search alone.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        logger.error("GOOGLE_API_KEY is not set.")
        return 1
    database_url = os.environ.get("DATABASE_URL", _DATABASE_URL_DEFAULT)
    corpus_sha = os.environ.get(
        "CORPUS_SHA", "40e33e492dbf4af6172997f4e3238a32e56cbe26"
    )

    from sqlalchemy import create_engine

    from app.retrieval.hybrid import PgVectorHybridSearcher
    from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
    from app.retrieval.orchestrator import retrieve

    engine = create_engine(database_url, pool_pre_ping=True)
    searcher = PgVectorHybridSearcher(engine=engine, corpus_sha=corpus_sha, rrf_k=60)
    embeddings = QueryEmbeddingsAdapter(api_key=api_key)
    rewrite_llm = GeminiChatAdapter(api_key=api_key, model="gemini-3.5-flash", timeout=1.5)
    rerank_llm = GeminiChatAdapter(api_key=api_key, model="gemini-3.5-flash", timeout=5.0)

    gold = _load_gold()
    single_turn = [g for g in gold if g["type"] != "multi_turn"]
    answerable = [g for g in single_turn if g["gold_chunks"]]
    no_se = [g for g in single_turn if not g["gold_chunks"]]

    print(
        f"Gold: {len(gold)} total · {len(single_turn)} single-turn · "
        f"{len(answerable)} answerable · {len(no_se)} no_se (excluded from recall)"
    )
    print(f"Pipeline: rewrite (no-op, single-turn) → hybrid → "
          f"{'rerank' if not args.no_rerank else 'NO rerank'} · top_k={args.top_k}\n")

    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    hits = 0

    for ex in answerable:
        query = ex["question_es"]
        if args.no_rerank:
            qvec = embeddings.embed_query(query)
            cands = searcher.search(qvec, query, candidates=20, top_k=args.top_k)
        else:
            result = retrieve(
                query=query,
                embeddings=embeddings,
                searcher=searcher,
                rewrite_llm=rewrite_llm,
                rerank_llm=rerank_llm,
                history=[],
                candidates=20,
                top_k=args.top_k,
            )
            cands = result.candidates

        retrieved = [(c.source, c.section) for c in cands]
        gold_set = _gold_keys(ex)
        found = [r for r in retrieved if r in gold_set]

        recall = len(set(found)) / len(gold_set)
        recalls.append(recall)

        rank = next((i + 1 for i, r in enumerate(retrieved) if r in gold_set), 0)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        if rank:
            hits += 1

        mark = "✓" if found else "✗"
        print(f"  {mark} {ex['id']} ({ex['type']:11s}) recall={recall:.2f} "
              f"rr={1.0/rank if rank else 0.0:.2f}  {query[:60]}")

    n = len(answerable)
    print("\n=== Baseline ===")
    print(f"  recall@{args.top_k}: {sum(recalls)/n:.3f}  (avg over {n} answerable)")
    print(f"  hit-rate@{args.top_k}: {hits/n:.3f}  ({hits}/{n} with ≥1 gold chunk)")
    print(f"  MRR@{args.top_k}: {sum(reciprocal_ranks)/n:.3f}")
    print(f"  no_se excluded: {[g['id'] for g in no_se]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
