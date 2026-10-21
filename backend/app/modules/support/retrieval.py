"""Find the help content that answers a question. No model, no network, nothing generated.

How it works (and why it can be trusted to stay inside its sources):

1. The question is reduced to its *meaningful lexemes* by PostgreSQL's English text-search
   configuration (stemming and stop-word removal), minus a short list of words that carry no
   topic ("want", "need", "please" ...).
2. Candidates are the published knowledge articles and the active sorting-guide entries whose
   text-search vector shares at least one lexeme (GIN-indexed for articles).
3. Each candidate is scored by *coverage*: the share of the question's lexemes that it contains
   (title matches count extra). Below ``MIN_QUERY_COVERAGE`` the assistant says it does not know.
4. The reply is quoted from the winning source (best paragraph(s)); nothing is paraphrased or added.

``tests/api/test_support_assistant_quality.py`` measures the answer and abstention rates on a
labelled question set; change the threshold only together with that evidence.
"""

from __future__ import annotations

import dataclasses
import re
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.support.constants import (
    MAX_ANSWER_CHARS,
    MAX_RELATED,
    MAX_SOURCES,
    MIN_QUERY_COVERAGE,
    MIN_RELATED_COVERAGE,
    SourceKind,
)

# Stems (as produced by the English configuration) of words that say nothing about the topic.
_FILLER = frozenset(
    {
        "want",
        "need",
        "pleas",
        "tell",
        "show",
        "know",
        "help",
        "like",
        "get",
        "got",
        "thank",
        "hi",
        "hello",
        "hey",
        "ok",
        "okay",
        "could",
        "would",
        "should",
        "someth",
        "thing",
        "possibl",
        "work",
        "wrong",
        "anyth",
        # Question words that say nothing about the topic.
        "mani",
        "much",
        "put",
        "make",
        "made",
        "still",
        "say",
        "long",
        "take",
        "give",
        "exist",
    }
)
_TITLE_BONUS = 0.25
# ts_rank_cd (frequency, proximity; squashed to 0..1) mostly breaks ties between equal coverages.
_RANK_WEIGHT = 0.05


@dataclasses.dataclass(frozen=True)
class Hit:
    kind: SourceKind
    id: uuid.UUID
    title: str
    text: str  # what is quoted to the person
    score: float
    coverage: float
    anchored: bool  # a matched word is in the title or the keywords, not only in the body


def question_lexemes(db: Session, question: str) -> list[str]:
    row = db.execute(
        text("SELECT tsvector_to_array(to_tsvector('english', :q))"), {"q": question}
    ).scalar_one()
    return sorted(lex for lex in (row or []) if lex not in _FILLER)


def _or_query(lexemes: list[str]) -> str:
    """A ``to_tsquery('simple', ...)`` string matching any of the (already stemmed) lexemes."""
    quoted = ("'" + lex.replace("\\", "\\\\").replace("'", "''") + "'" for lex in lexemes)
    return " | ".join(quoted)


def _coverage(question: set[str], document: set[str]) -> float:
    return len(question & document) / len(question) if question else 0.0


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def _quote(db: Session, body: str, question: set[str]) -> str:
    """The whole body when it is short, otherwise the paragraphs that match the question best."""
    body = body.strip()
    if len(body) <= MAX_ANSWER_CHARS:
        return body
    paragraphs = _paragraphs(body)
    rows = db.execute(
        text(
            "SELECT tsvector_to_array(to_tsvector('english', p)) "
            "FROM unnest(CAST(:paragraphs AS text[])) WITH ORDINALITY AS t(p, n) ORDER BY n"
        ),
        {"paragraphs": paragraphs},
    ).scalars()
    overlaps = [len(question & set(lexemes or [])) for lexemes in rows]
    order = sorted(range(len(paragraphs)), key=lambda i: (-overlaps[i], i))
    chosen: list[int] = []
    used = 0
    for index in order:
        if chosen and used + len(paragraphs[index]) > MAX_ANSWER_CHARS:
            continue
        chosen.append(index)
        used += len(paragraphs[index])
    quoted = "\n\n".join(paragraphs[i] for i in sorted(chosen))
    return quoted[:MAX_ANSWER_CHARS].rstrip()


def _article_hits(db: Session, lexemes: list[str], query: set[str]) -> list[Hit]:
    rows = db.execute(
        text(
            "SELECT id, title, body, tsvector_to_array(search_vector) AS lexemes, "
            "tsvector_to_array(to_tsvector('english', title)) AS title_lexemes, "
            "tsvector_to_array(to_tsvector('english', title || ' ' || keywords)) AS anchors, "
            "ts_rank_cd(search_vector, to_tsquery('simple', :q), 32) AS rank "
            "FROM knowledge_articles "
            "WHERE published AND search_vector @@ to_tsquery('simple', :q) "
            "ORDER BY id"
        ),
        {"q": _or_query(lexemes)},
    ).all()
    hits = []
    for row in rows:
        coverage = _coverage(query, set(row.lexemes))
        title_coverage = _coverage(query, set(row.title_lexemes))
        hits.append(
            Hit(
                kind=SourceKind.ARTICLE,
                id=row.id,
                title=row.title,
                text=row.body,
                score=coverage + _TITLE_BONUS * title_coverage + _RANK_WEIGHT * float(row.rank),
                coverage=coverage,
                anchored=bool(query & set(row.anchors)),
            )
        )
    return hits


def _guidance_hits(db: Session, lexemes: list[str], query: set[str]) -> list[Hit]:
    # A fixed statement (no interpolation): the search document is built once in a subquery.
    rows = db.execute(
        text(
            "SELECT id, title, instructions, preparation_notes, disposal_method, "
            "source_reference, material, "
            "tsvector_to_array(document) AS lexemes, "
            "tsvector_to_array(to_tsvector('english', material || ' ' || title)) AS title_lexemes, "
            "tsvector_to_array(to_tsvector('english', material || ' ' || title)) AS anchors "
            "FROM ("
            "SELECT g.id, g.title, g.instructions, g.preparation_notes, g.disposal_method, "
            "g.source_reference, coalesce(c.name, '') AS material, "
            "to_tsvector('english', coalesce(c.name, '') || ' ' || coalesce(g.title, '') || ' ' "
            "|| coalesce(g.instructions, '') || ' ' || coalesce(g.preparation_notes, '')) "
            "AS document "
            "FROM sorting_guidance g JOIN material_categories c ON c.id = g.material_category_id "
            "WHERE g.is_active AND c.is_active"
            ") AS guidance "
            "WHERE document @@ to_tsquery('simple', :q) "
            "ORDER BY id"
        ),
        {"q": _or_query(lexemes)},
    ).all()
    hits = []
    for row in rows:
        coverage = _coverage(query, set(row.lexemes))
        title_coverage = _coverage(query, set(row.title_lexemes))
        parts = [f"{row.material}: {row.title}.", row.instructions.strip()]
        if row.preparation_notes:
            parts.append(f"Preparation: {row.preparation_notes.strip()}")
        parts.append(
            f"Source: {row.source_reference}"
            if row.source_reference
            else "No source is cited for this guidance."
        )
        hits.append(
            Hit(
                kind=SourceKind.SORTING_GUIDANCE,
                id=row.id,
                title=f"{row.material}: {row.title}",
                text="\n\n".join(parts),
                score=coverage + _TITLE_BONUS * title_coverage,
                coverage=coverage,
                anchored=bool(query & set(row.anchors)),
            )
        )
    return hits


def _ranked(db: Session, question: str) -> tuple[list[Hit], set[str]]:
    lexemes = question_lexemes(db, question)
    if not lexemes:
        return [], set()
    query = set(lexemes)
    hits = _article_hits(db, lexemes, query) + _guidance_hits(db, lexemes, query)
    # Articles first on equal scores (they are written for questions); then a stable tie-break.
    hits.sort(key=lambda h: (-h.score, h.kind != SourceKind.ARTICLE, h.title, str(h.id)))
    return hits, query


def find_answers(db: Session, question: str) -> tuple[list[Hit], str | None]:
    """Trustworthy hits (best first) and the quoted answer, or ``([], None)`` when unsure."""
    ranked, query = _ranked(db, question)
    hits = [h for h in ranked if h.coverage >= MIN_QUERY_COVERAGE and h.anchored]
    if not hits:
        return [], None
    best = hits[0]
    chosen = [best]
    for other in hits[1:]:
        if len(chosen) >= MAX_SOURCES:
            break
        if other.score >= 0.85 * best.score:
            chosen.append(other)
    if len(chosen) == 1:
        return chosen, _quote(db, best.text, query)
    # More than one comparable source: quote each in full (they are short) and name them.
    quoted = [f"{h.title}\n{_quote(db, h.text, query)}" for h in chosen]
    return chosen, "\n\n".join(quoted)


def find_related(db: Session, question: str) -> list[Hit]:
    """Near misses to *suggest* (never to answer with): some overlap, below the answer threshold."""
    ranked, _ = _ranked(db, question)
    return [h for h in ranked if h.coverage >= MIN_RELATED_COVERAGE][:MAX_RELATED]
