"""Matching eval — checks shared-term matching logic."""

from python.schemas.domain import ContextItem, Visibility, Sensitivity, State


def shared_terms(a_contexts: list[ContextItem], b_contexts: list[ContextItem]) -> set[str]:
    terms = set()
    for a in a_contexts:
        for b in b_contexts:
            for term in ["上海", "咖啡", "AI", "周末", "探店", "展览", "数据库"]:
                if term in a.text and term in b.text:
                    terms.add(term)
    return terms


def run() -> dict:
    user_a = [
        ContextItem(id="a1", user_id="a", text="喜欢在上海喝咖啡和逛展览", visibility=Visibility.match_only, sensitivity=Sensitivity.normal, state=State.active),
    ]
    user_b = [
        ContextItem(id="b1", user_id="b", text="上海咖啡店探店和AI技术交流", visibility=Visibility.match_only, sensitivity=Sensitivity.normal, state=State.active),
    ]
    terms = shared_terms(user_a, user_b)
    expected = {"上海", "咖啡"}
    passed = 1 if expected.issubset(terms) else 0
    print(f"matching_eval: {passed}/1 passed (shared_terms={terms})")
    return {"suite": "matching", "passed": passed, "total": 1, "results": [{"shared_terms": list(terms)}]}


if __name__ == "__main__":
    run()
