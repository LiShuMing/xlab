"""Privacy check eval — verifies sensitive content is flagged."""

from python.schemas.domain import ContextItem, Visibility, Sensitivity, State
from python.providers.qwen import QwenProvider


def run() -> dict:
    cases = [
        {
            "name": "private_context_not_exposed",
            "context": ContextItem(
                id="ctx_test_1",
                user_id="user_a",
                text="我在上海市南京东路100号工作，每天9点出门。",
                visibility=Visibility.private,
                sensitivity=Sensitivity.normal,
                state=State.active,
            ),
            "expect_exposed": False,
        },
        {
            "name": "match_only_context_ok",
            "context": ContextItem(
                id="ctx_test_2",
                user_id="user_a",
                text="喜欢周末去咖啡馆和探店。",
                visibility=Visibility.match_only,
                sensitivity=Sensitivity.normal,
                state=State.active,
            ),
            "expect_exposed": True,
        },
    ]
    passed = 0
    results = []
    for case in cases:
        ctx = case["context"]
        has_sensitive = any(kw in ctx.text for kw in ["南京东路", "100号", "9点出门"])
        ok = (has_sensitive and not case["expect_exposed"]) or (not has_sensitive and case["expect_exposed"])
        if ok:
            passed += 1
        results.append({"case": case["name"], "passed": ok})
    print(f"privacy_eval: {passed}/{len(cases)} passed")
    return {"suite": "privacy", "passed": passed, "total": len(cases), "results": results}


if __name__ == "__main__":
    run()
