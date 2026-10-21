# Help assistant: retrieval quality

This is a retrieval system, not a trained model: there is no training data, no weights and no model file. It is documented here because it answers questions and its quality must be reported honestly. Design: `docs/decisions/ADR-0003-retrieval-help-assistant.md`.

## Method
PostgreSQL full-text search (English configuration, stemming, stop words) over the weighted title (A), body (B) and curated keywords (C, added in migration 0015) of published articles, plus the sorting-guide entries. For a question: stem its meaningful words; candidates are ranked by matched words, a title bonus and `ts_rank_cd` as tie-break; an answer is given only if a matched word is in the article's title or keywords (**anchor rule**) and at least 60% of the question's words occur in the article (`MIN_QUERY_COVERAGE`). Between 25% and 60% coverage an article is only suggested as "possibly related".

## Evaluation data
`backend/tests/data/assistant_eval.json`, checked by `backend/tests/api/test_support_assistant_quality.py` on every CI run against the 31 starter articles.

| Set | In-scope questions | Out-of-scope questions | Role |
|---|---|---|---|
| `in_scope` / `out_of_scope` (development) | 64 | 20 | used while building and tuning |
| `held_out` | 40 | 16 | written after the keywords were added |

**Limits you must keep in mind:** all questions were written by the same author who wrote the articles and the retrieval code, not by users, and nobody outside the project labelled them. The held-out set was run once before the anchor rule and once after it, so it is **no longer a clean holdout** and its numbers are optimistic. There is no evidence from real users yet.

## Results (final run on this branch)
| Set | top-1 correct | wrong article | no direct answer | false answers to out-of-scope |
|---|---|---|---|---|
| Development | 0.953 | 0.031 | 0.016 | 0.050 (1 of 20: "how do I get a refund" matched the cancel-redemption article) |
| Held-out (contaminated) | 0.550 | 0.000 | 0.450 | 0.000 (0 of 16) |

For 13 of the 18 held-out questions with no direct answer, the right article was among the three suggested ones. Before the anchor rule the first held-out run gave top-1 0.525, wrong 0.025 and 2 of 16 false answers.

Interpretation: when it answers it is usually right (wrong rate low in both sets), but about half of the questions worded differently from the articles get a "no answer" plus suggestions. That is the intended failure mode. The development top-1 is tuned and should not be quoted as expected real-world accuracy.

## Gates in CI
Development top-1 >= 0.90, held-out top-1 >= 0.50, wrong-article rate <= 0.05 in each set, false answers to out-of-scope questions <= 0.10 in each set. A change to the articles, keywords or thresholds that breaks a gate fails the build; the thresholds were not loosened to pass.

## How to improve it honestly
1. Staff add keywords and articles for questions the usage tab shows as unanswered (`GET /support/assistant/stats` counts them).
2. Collect real, consented questions and re-measure with labels from someone who did not write the articles; keep that set out of tuning.
3. Only then consider embeddings or a generative layer (ADR-0003, "Extension point").
