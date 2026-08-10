"""Photo context extraction eval — mock, no real vision API."""

import json
import os
import sys
from python.providers.qwen import QwenProvider
from python.schemas.domain import PhotoExtraction


def load_cases() -> list[dict]:
    golden_dir = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden", "photo_extract")
    cases = []
    if os.path.isdir(golden_dir):
        for fname in sorted(os.listdir(golden_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(golden_dir, fname)) as f:
                    cases.append(json.load(f))
    if not cases:
        cases.append({
            "name": "default_photo_extract",
            "input": {"filename": "test.jpg", "metadata": {}},
            "expected": {"topics": ["城市漫步"]},
        })
    return cases


def run() -> dict:
    provider = QwenProvider()
    cases = load_cases()
    passed = 0
    results = []
    for case in cases:
        extraction = provider.extract_photo_context(case["input"]["filename"], case["input"].get("metadata", {}))
        expected_topics = case.get("expected", {}).get("topics", [])
        ok = any(t in extraction.topics for t in expected_topics) if expected_topics else len(extraction.topics) > 0
        if ok:
            passed += 1
        results.append({
            "case": case["name"],
            "passed": ok,
            "topics": extraction.topics,
            "confidence": extraction.confidence,
        })
    print(f"extraction_eval: {passed}/{len(cases)} passed")
    return {"suite": "extraction", "passed": passed, "total": len(cases), "results": results}


if __name__ == "__main__":
    run()
