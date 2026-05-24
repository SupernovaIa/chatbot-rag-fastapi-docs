"""CLI entrypoint for the eval runner (spec 10).

Wires the real adapters (pgvector hybrid search, Gemini embeddings/Flash/Pro)
into ``run_evals``, applies the gate, prints the Markdown report and writes the
machine-readable artifacts CI consumes.

Two modes:

- ``--retrieval-only`` — the **PR gate**: deterministic recall@5 / MRR over the
  label-matchable answerable examples. No generation, no judge → runs in seconds.
- default — the **nightly monitor**: full pipeline + RAGAS judge (Gemini Pro),
  floors + regression vs the baseline; refreshes the judge baseline.

Usage (stack up, env loaded), from ``backend/``:

    # PR gate (deterministic, blocking, seconds):
    python -m app.evals.cli --subset ci_gate --retrieval-only --markdown eval_report.md
    # Nightly judge monitor (full suite) + baseline refresh:
    python -m app.evals.cli --subset full --baseline baseline_metrics.json \\
        --update-baseline baseline_metrics.json --markdown eval_report.md

Exit code is ``0`` when the check passes, ``1`` when it fails (PR gate blocks the
merge; nightly turns red as a trend alert), ``2`` on a wiring/setup error.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("app.evals.cli")


def _build_retriever(settings, *, top_k: int):
    from sqlalchemy import create_engine

    from app.retrieval.hybrid import PgVectorHybridSearcher
    from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
    from app.retrieval.models import RetrievalResult, Turn
    from app.retrieval.orchestrator import retrieve

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    searcher = PgVectorHybridSearcher(
        engine=engine, corpus_sha=settings.corpus_sha, rrf_k=settings.rrf_k
    )
    embeddings = QueryEmbeddingsAdapter(api_key=settings.google_api_key)
    rewrite_llm = GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.rewrite_timeout_s,
        max_retries=settings.rerank_max_retries,
    )
    rerank_llm = GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.rerank_timeout_s,
        max_retries=settings.rerank_max_retries,
    )

    def retriever_fn(query: str, history: list[Turn]) -> RetrievalResult:
        return retrieve(
            query=query,
            embeddings=embeddings,
            searcher=searcher,
            rewrite_llm=rewrite_llm,
            rerank_llm=rerank_llm,
            history=history,
            candidates=settings.retrieval_candidates,
            top_k=top_k,
        )

    return retriever_fn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--subset", choices=["ci_gate", "ci_subset", "full"], default="ci_gate",
        help="ci_gate (6 ej., PR gate), ci_subset (14 ej.), or full (40, nightly).",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--retrieval-only", action="store_true",
        help="Deterministic PR gate: retrieval metrics only (no generation, no judge).",
    )
    parser.add_argument("--baseline", type=Path, help="baseline_metrics.json to compare against.")
    parser.add_argument("--update-baseline", type=Path, help="Write this run as the new baseline JSON.")
    parser.add_argument("--markdown", type=Path, help="Write the PR-comment Markdown here.")
    parser.add_argument("--json", type=Path, dest="json_out", help="Write the run metrics JSON here.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from app.config import get_settings
    from app.evals.generator import GeminiAnswerGenerator
    from app.evals.judge import RagasGeminiJudge
    from app.evals.loader import CI_GATE_IDS, CI_SUBSET_IDS, load_gold, select_subset
    from app.evals.report import (
        evaluate_gate,
        evaluate_judge,
        load_baseline,
        render_markdown,
        report_to_baseline,
    )
    from app.evals.runner import run_evals
    from app.evals.telemetry import record_eval_run

    settings = get_settings()
    if not settings.google_api_key:
        logger.error("GOOGLE_API_KEY is not set.")
        return 2

    examples = load_gold()
    if args.subset == "ci_gate":
        examples = select_subset(examples, ids=CI_GATE_IDS)
    elif args.subset == "ci_subset":
        examples = select_subset(examples, ids=CI_SUBSET_IDS)

    try:
        retriever_fn = _build_retriever(settings, top_k=args.top_k)
        generator = None if args.retrieval_only else GeminiAnswerGenerator(
            api_key=settings.google_api_key,
            model=settings.gemini_flash_model,
            timeout=settings.evals_gen_timeout_s,
        )
        judge = None if args.retrieval_only else RagasGeminiJudge(
            api_key=settings.google_api_key,
            judge_model=settings.gemini_pro_model,
            max_workers=settings.evals_judge_max_workers,
            timeout=settings.evals_judge_timeout_s,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to wire eval adapters: %s", exc)
        return 2

    report = run_evals(
        examples,
        retriever_fn=retriever_fn,
        generator=generator,
        judge=judge,
        top_k=args.top_k,
        commit_sha=os.environ.get("GITHUB_SHA", ""),
        corpus_sha=settings.corpus_sha,
        subset=args.subset,
        use_generator=not args.retrieval_only,
        use_judge=not args.retrieval_only,
    )

    record_eval_run(report)

    if args.retrieval_only:
        # PR gate: deterministic floors (recall@5, MRR). Blocking.
        verdict = evaluate_gate(report)
        markdown = render_markdown(report, verdict)
    else:
        # Nightly monitor: judge floors + regression vs baseline. Alerting.
        baseline = load_baseline(args.baseline)
        verdict = evaluate_judge(report, baseline=baseline)
        markdown = render_markdown(
            report, verdict,
            title="Juez LLM (monitor de tendencia · nocturna)",
            advisory=("recall_at_5", "mrr", "abstention_rate"),
            show_baseline=True,
        )
    print(markdown)

    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    if args.json_out:
        args.json_out.write_text(
            json.dumps(report_to_baseline(report), indent=2), encoding="utf-8"
        )
    if args.update_baseline:
        args.update_baseline.write_text(
            json.dumps(report_to_baseline(report), indent=2), encoding="utf-8"
        )

    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
