"""Small transparent smoke set, not a benchmark or a correctness proof."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from strata_review import ReviewError, Source, StrataClient

# Labels are used only for scoring; they are never sent to the model.
CASES = [
    ("01", "bounds", """#include <vector>
int total(const std::vector<int>& values) {
    int result = 0;
    for (std::size_t i = 0; i <= values.size(); ++i) {
        result += values[i];
    }
    return result;
}
"""),
    ("02", "lifetime", """int* value() {
    int local = 42;
    return &local;
}
"""),
    ("03", "lifetime", """int value() {
    int* p = new int(42);
    delete p;
    return *p;
}
"""),
    ("04", "race", """#include <thread>
int counter = 0;
void worker() { for (int i = 0; i < 1000; ++i) { ++counter; } }
int main() {
    std::thread first(worker), second(worker);
    first.join(); second.join();
    return 0;
}
"""),
    ("05", "deadlock", """#include <mutex>
std::mutex mutex;
void inner() { std::lock_guard<std::mutex> lock(mutex); }
void outer() {
    std::lock_guard<std::mutex> lock(mutex);
    inner();
}
int main() { outer(); }
"""),
    ("06", "logic", """bool is_even(int number) {
    return number % 2 != 0;
}
"""),
    ("07", None, """#include <algorithm>
#include <vector>
#include <cstdint>
// Return the sum of at most the first 1000 elements.
std::int64_t total_first_1000(const std::vector<int>& values) {
    std::int64_t result = 0;
    const auto count = std::min(values.size(), std::size_t{1000});
    for (std::size_t i = 0; i < count; ++i) { result += values[i]; }
    return result;
}
"""),
    ("08", None, """#include <memory>
std::unique_ptr<int> make_value() {
    return std::make_unique<int>(42);
}
"""),
    ("09", None, """#include <atomic>
#include <thread>
std::atomic<int> counter{0};
void worker() { for (int i = 0; i < 1000; ++i) { counter.fetch_add(1); } }
int main() {
    std::thread first(worker), second(worker);
    first.join(); second.join();
    return counter.load() == 2000 ? 0 : 1;
}
"""),
    ("10", None, """#include <mutex>
#include <thread>
std::mutex mutex;
int counter = 0;
void worker() {
    for (int i = 0; i < 1000; ++i) {
        std::lock_guard<std::mutex> lock(mutex);
        ++counter;
    }
}
int main() {
    std::thread first(worker), second(worker);
    first.join(); second.join();
    return counter == 2000 ? 0 : 1;
}
"""),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case", action="append", help="Case ID; repeat to select a subset")
    parser.add_argument("--effort", choices=["none", "low", "medium", "high"], default="none")
    args = parser.parse_args()
    selected = [case for case in CASES if not args.case or case[0] in args.case]
    if not selected or (args.case and set(args.case) - {case[0] for case in CASES}):
        parser.error("Unknown case ID")
    output = args.output_dir or Path("results") / datetime.now().strftime("live-%Y%m%d-%H%M%S")
    output.mkdir(parents=True, exist_ok=False)
    client = StrataClient()
    rows = []
    for case_id, expected, code in selected:
        source = Source(f"case_{case_id}.cpp", code)
        source_path = output / source.name
        source_path.write_text(code, encoding="utf-8")
        compile_result = subprocess.run(
            ["clang++", "-std=c++20", "-pthread", "-fsyntax-only", str(source_path)],
            capture_output=True, text=True, timeout=30,
        )
        if compile_result.returncode:
            raise RuntimeError(compile_result.stderr)
        print(f"CASE {case_id}: requesting review", flush=True)
        row = {"case": case_id, "expected_category": expected, "syntax_check": "passed"}
        try:
            result = client.review([source], effort=args.effort, max_tokens=2048)
            findings = result["review"]["findings"]
            row.update({
                "valid_response": True, "result": result,
                "category_match": any(f["category"] == expected for f in findings) if expected else None,
                "clean_no_findings": not findings if expected is None else None,
            })
        except ReviewError as exc:
            row.update({"valid_response": False, "error": str(exc)})
        rows.append(row)
        (output / f"case_{case_id}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in row.items() if k != "result"}, ensure_ascii=False), flush=True)
    buggy = [row for row in rows if row["expected_category"] is not None]
    clean = [row for row in rows if row["expected_category"] is None]
    summary = {
        "model": client.model, "effort": args.effort, "cases": len(rows),
        "valid_responses": sum(row["valid_response"] for row in rows),
        "bug_cases": len(buggy), "expected_category_hits": sum(bool(row.get("category_match")) for row in buggy),
        "clean_cases": len(clean), "clean_no_findings": sum(bool(row.get("clean_no_findings")) for row in clean),
        "rows": rows,
        "limitations": "Tiny authored smoke set. Category matching is not proof of reasoning correctness. "
        "Anchors are validated, not claims or generated repros. Inspect full reports. No model-generated code executed.",
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {output / 'summary.json'}", flush=True)
    return 0 if summary["valid_responses"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
