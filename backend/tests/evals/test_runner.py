"""Tests for the eval runner with fully faked retrieval / generation / judge."""

from __future__ import annotations

from app.evals.loader import GoldChunk, GoldExample
from app.evals.runner import run_evals
from app.retrieval.models import Turn
from tests.evals.conftest import (
    FakeGenerator,
    FakeJudge,
    FakeRetriever,
    make_candidate,
)


def _answerable(qid: str, source: str, section: str) -> GoldExample:
    return GoldExample(
        id=qid,
        type="factual",
        question=f"q-{qid}",
        expected_answer="expected",
        gold_chunks=[GoldChunk(source=source, section=section)],
    )


def _no_se(qid: str) -> GoldExample:
    return GoldExample(id=qid, type="no_se", question=f"q-{qid}", expected_answer="No tengo esa información")


def test_runner_computes_deterministic_and_judge_metrics() -> None:
    ex = _answerable("g-1", "a.md", "Sec A")
    retriever = FakeRetriever(
        by_question={"q-g-1": [make_candidate("a.md", "Sec A"), make_candidate("x.md", "X")]}
    )
    report = run_evals(
        [ex],
        retriever_fn=retriever,
        generator=FakeGenerator(answer="grounded answer"),
        judge=FakeJudge(),
    )
    assert report.metrics.recall_at_5 == 1.0
    assert report.metrics.mrr == 1.0
    assert report.metrics.faithfulness == 0.9
    assert report.metrics.context_recall == 0.9
    assert report.n_total == 1
    assert report.n_answerable == 1


def test_runner_excludes_no_se_from_recall_and_feeds_abstention() -> None:
    answerable = _answerable("g-1", "a.md", "Sec A")
    refusal = _no_se("g-2")
    retriever = FakeRetriever(
        by_question={
            "q-g-1": [make_candidate("a.md", "Sec A")],
            "q-g-2": [make_candidate("z.md", "Z")],
        }
    )

    def gen_answer(query, history, candidates):
        return "No tengo esa información" if query == "q-g-2" else "real answer"

    gen = FakeGenerator()
    gen.generate = gen_answer  # type: ignore[assignment]

    judge = FakeJudge()
    report = run_evals([answerable, refusal], retriever_fn=retriever, generator=gen, judge=judge)

    # recall/MRR computed over the 1 answerable example only.
    assert report.metrics.recall_at_5 == 1.0
    # abstention computed over the 1 no_se example, correctly refused.
    assert report.metrics.abstention_rate == 1.0
    # judge only saw the answerable example.
    assert judge.n_samples == 1


def test_runner_captures_per_example_error_without_aborting() -> None:
    ok = _answerable("g-1", "a.md", "Sec A")
    bad = _answerable("g-2", "b.md", "Sec B")
    retriever = FakeRetriever(
        by_question={"q-g-1": [make_candidate("a.md", "Sec A")]},
        default=[],
    )

    def gen(query, history, candidates):
        if query == "q-g-2":
            raise RuntimeError("boom")
        return "ok"

    g = FakeGenerator()
    g.generate = gen  # type: ignore[assignment]

    report = run_evals([ok, bad], retriever_fn=retriever, generator=g, judge=FakeJudge())
    assert len(report.errors) == 1
    assert report.errors[0].id == "g-2"
    # The healthy example still scored.
    assert report.metrics.recall_at_5 == 1.0


def test_runner_no_judge_skips_ragas() -> None:
    ex = _answerable("g-1", "a.md", "Sec A")
    retriever = FakeRetriever(by_question={"q-g-1": [make_candidate("a.md", "Sec A")]})
    judge = FakeJudge()
    report = run_evals(
        [ex], retriever_fn=retriever, generator=FakeGenerator(), judge=judge, use_judge=False
    )
    assert report.metrics.faithfulness is None
    assert judge.n_samples is None  # judge never called
    assert report.metrics.recall_at_5 == 1.0


def test_runner_excludes_multi_source_from_recall() -> None:
    # A multi_source example whose gold chunks are NOT retrieved must not drag
    # down recall@5 (it is excluded from the deterministic metric).
    factual = _answerable("g-1", "a.md", "Sec A")
    multi = GoldExample(
        id="g-2", type="multi_source", question="q-g-2", expected_answer="x",
        gold_chunks=[GoldChunk("gold.md", "Gold")],
    )
    retriever = FakeRetriever(by_question={
        "q-g-1": [make_candidate("a.md", "Sec A")],
        "q-g-2": [make_candidate("other.md", "Other")],  # gold NOT retrieved
    })
    report = run_evals([factual, multi], retriever_fn=retriever,
                       generator=FakeGenerator(), judge=FakeJudge())
    # recall computed over the factual only (multi_source excluded) -> 1.0
    assert report.metrics.recall_at_5 == 1.0


def test_runner_retrieval_only_skips_generation_and_judge() -> None:
    ex = _answerable("g-1", "a.md", "Sec A")
    retriever = FakeRetriever(by_question={"q-g-1": [make_candidate("a.md", "Sec A")]})
    gen = FakeGenerator()
    judge = FakeJudge()
    report = run_evals([ex], retriever_fn=retriever, generator=gen, judge=judge,
                       use_generator=False)
    assert gen.calls == []          # generator never invoked
    assert judge.n_samples is None  # judge never invoked
    assert report.runs[0].response == ""
    assert report.metrics.recall_at_5 == 1.0  # retrieval metric still computed
    assert report.metrics.faithfulness is None


def test_runner_accepts_none_generator_and_judge() -> None:
    ex = _answerable("g-1", "a.md", "Sec A")
    retriever = FakeRetriever(by_question={"q-g-1": [make_candidate("a.md", "Sec A")]})
    report = run_evals([ex], retriever_fn=retriever, generator=None, judge=None,
                       use_generator=False)
    assert report.metrics.recall_at_5 == 1.0


def test_runner_passes_history_to_retriever() -> None:
    ex = GoldExample(
        id="g-36",
        type="multi_turn",
        question="¿y eso?",
        expected_answer="...",
        gold_chunks=[GoldChunk("a.md", "Sec A")],
        history=[Turn(question="prev", answer="prev-a")],
    )
    retriever = FakeRetriever(by_question={"¿y eso?": [make_candidate("a.md", "Sec A")]})
    run_evals([ex], retriever_fn=retriever, generator=FakeGenerator(), judge=FakeJudge())
    assert retriever.calls[0][1] == ex.history
