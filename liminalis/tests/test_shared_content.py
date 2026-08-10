from backend._shared.content import classify_content, keyword_snippets, relevance_confidence


def test_shared_content_classifier_and_confidence() -> None:
    assert classify_content("DuckDB v1.0 released", "new optimizer features") == "release"
    assert classify_content("Query optimizer internals", "join ordering") == "engine"
    assert relevance_confidence("DuckDB release", "database query engine") > 0.5


def test_keyword_snippets_extracts_limited_relevant_sentences() -> None:
    snippets = keyword_snippets(
        "Short. This release improves storage engine performance for analytical queries."
        " Another unrelated sentence.",
    )

    assert snippets == ["This release improves storage engine performance for analytical queries"]
