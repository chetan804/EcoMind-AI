"""How well the help assistant's retrieval answers, and when it stays silent.

Runs the real retrieval over the shipped platform help (PostgreSQL full-text search) with a
labelled question set (``tests/data/assistant_eval.json``). The set is small, written by the
maintainers and not independent of the article wording, so these numbers are *regression
guards*, not a claim about real users. Each run prints the measured rates (``pytest -s``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.modules.support import knowledge, retrieval

_DATA = json.loads((Path(__file__).parent.parent / "data" / "assistant_eval.json").read_text())
SETS = {"development": _DATA, "held_out": _DATA["held_out"]}

# Measured on the shipped articles when this file was written (see docs/ml/support-assistant.md);
# the thresholds sit a little below so a real regression fails and rounding noise does not.
MIN_TOP1_RATE = {"development": 0.90, "held_out": 0.50}
MAX_WRONG_RATE = 0.05
MAX_FALSE_ANSWER_RATE = 0.10


@pytest.fixture
def seeded(db_engine: Engine) -> sessionmaker:  # type: ignore[type-arg]
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    with factory() as db:
        knowledge.seed_platform_help(db)
    return factory


def _ask(factory: sessionmaker, question: str) -> tuple[str | None, bool]:  # type: ignore[type-arg]
    with factory() as db:
        hits, answer = retrieval.find_answers(db, question)
        if not hits:
            return None, False
        slug = db.execute(
            text("SELECT slug FROM knowledge_articles WHERE id = :id"), {"id": hits[0].id}
        ).scalar_one_or_none()
        return slug, answer is not None


def _related_slugs(factory: sessionmaker, question: str) -> list[str]:  # type: ignore[type-arg]
    with factory() as db:
        ids = [h.id for h in retrieval.find_related(db, question)]
        rows = db.execute(
            text("SELECT slug FROM knowledge_articles WHERE id = ANY(:ids)"), {"ids": ids}
        ).scalars()
        return list(rows)


@pytest.mark.parametrize("name", SETS)
def test_in_scope_questions_are_answered_from_the_right_article(
    name: str,
    seeded: sessionmaker,  # type: ignore[type-arg]
    capsys: pytest.CaptureFixture[str],
) -> None:
    eval_set = SETS[name]
    top1 = wrong = silent = suggested = 0
    misses = []
    for case in eval_set["in_scope"]:
        slug, _ = _ask(seeded, case["question"])
        if slug == case["expected_slug"]:
            top1 += 1
        elif slug is None:
            silent += 1
            if case["expected_slug"] in _related_slugs(seeded, case["question"]):
                suggested += 1
            misses.append(("silent", case["question"], case["expected_slug"]))
        else:
            wrong += 1
            misses.append(("wrong:" + slug, case["question"], case["expected_slug"]))
    total = len(eval_set["in_scope"])
    with capsys.disabled():
        print(
            f"\nassistant {name} in-scope: n={total} top1={top1 / total:.3f} "
            f"wrong={wrong / total:.3f} silent={silent / total:.3f} "
            f"(of the silent ones the right article was suggested for {suggested} of {silent})"
        )
        for miss in misses:
            print("   ", miss)
    assert top1 / total >= MIN_TOP1_RATE[name]
    assert wrong / total <= MAX_WRONG_RATE


@pytest.mark.parametrize("name", SETS)
def test_questions_the_help_does_not_cover_get_no_answer(
    name: str,
    seeded: sessionmaker,  # type: ignore[type-arg]
    capsys: pytest.CaptureFixture[str],
) -> None:
    out_of_scope = SETS[name]["out_of_scope"]
    answered = [q for q in out_of_scope if _ask(seeded, q)[0] is not None]
    total = len(out_of_scope)
    with capsys.disabled():
        print(
            f"\nassistant {name} out-of-scope: n={total} false_answers={len(answered) / total:.3f}"
        )
        for question in answered:
            print("    answered:", question)
    assert len(answered) / total <= MAX_FALSE_ANSWER_RATE
