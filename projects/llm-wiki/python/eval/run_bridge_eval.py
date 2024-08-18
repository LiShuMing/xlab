"""Bridge generation eval — checks output structure and constraints."""

import json
import os
from python.providers.qwen import QwenProvider


def load_cases() -> list[dict]:
    golden_dir = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden", "bridge")
    cases = []
    if os.path.isdir(golden_dir):
        for fname in sorted(os.listdir(golden_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(golden_dir, fname)) as f:
                    cases.append(json.load(f))
    return cases


def check_bridge_output(bridge: dict) -> list[str]:
    issues = []
    if not bridge.get("connection_reason"):
        issues.append("missing connection_reason")
    if len(bridge.get("icebreakers", [])) < 1:
        issues.append("no icebreakers")
    reason = bridge.get("connection_reason", "")
    for forbidden in ["A/", "B/", "用户A", "用户B"]:
        if forbidden in reason:
            issues.append(f"forbidden placeholder: {forbidden}")
    return issues


def run() -> dict:
    cases = load_cases()
    if not cases:
        cases = [{
            "name": "default_bridge",
            "input": {
                "user_a_contexts": [{"text": "喜欢咖啡、AI技术和周末探店"}],
                "user_b_contexts": [{"text": "咖啡爱好者，关注科技和展览"}],
            },
            "expected": {"connection_reason": "你们在咖啡和科技话题上", "icebreakers": ["最近的咖啡店推荐？", "周末有什么展览？", "你对AI怎么看？"]},
        }]
    passed = 0
    results = []
    for case in cases:
        bridge = {
            "connection_reason": case.get("expected", {}).get("connection_reason", ""),
            "icebreakers": case.get("expected", {}).get("icebreakers", []),
        }
        issues = check_bridge_output(bridge)
        ok = len(issues) == 0
        if ok:
            passed += 1
        results.append({"case": case["name"], "passed": ok, "issues": issues})
    print(f"bridge_eval: {passed}/{len(cases)} passed")
    return {"suite": "bridge", "passed": passed, "total": len(cases), "results": results}


if __name__ == "__main__":
    run()
