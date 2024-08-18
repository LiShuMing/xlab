"""Aggregate eval results and produce a markdown report."""

import json
import os
from datetime import date


def main():
    suites = []
    # Import and run each eval
    try:
        from python.eval.run_extraction_eval import run as run_extraction
        suites.append(run_extraction())
    except Exception as e:
        suites.append({"suite": "extraction", "error": str(e)})
    try:
        from python.eval.run_privacy_eval import run as run_privacy
        suites.append(run_privacy())
    except Exception as e:
        suites.append({"suite": "privacy", "error": str(e)})
    try:
        from python.eval.run_matching_eval import run as run_matching
        suites.append(run_matching())
    except Exception as e:
        suites.append({"suite": "matching", "error": str(e)})
    try:
        from python.eval.run_bridge_eval import run as run_bridge
        suites.append(run_bridge())
    except Exception as e:
        suites.append({"suite": "bridge", "error": str(e)})

    # Generate report
    today = date.today().isoformat()
    report_path = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "reports", f"{today}-eval.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    total_passed = sum(s.get("passed", 0) for s in suites)
    total_cases = sum(s.get("total", 0) for s in suites)

    lines = [
        f"# Eval Report — {today}",
        "",
        f"**Summary:** {total_passed}/{total_cases} cases passed across {len(suites)} suites.",
        "",
        "| Suite | Passed | Total |",
        "|-------|--------|-------|",
    ]
    for s in suites:
        passed = s.get("passed", 0)
        total = s.get("total", 0)
        error = s.get("error", "")
        status = f"{passed}/{total}" if not error else f"ERROR: {error}"
        lines.append(f"| {s['suite']} | {status} | {total if not error else '-'} |")

    if any(s.get("results") for s in suites):
        lines.append("")
        lines.append("## Details")
        for s in suites:
            if s.get("results"):
                lines.append(f"### {s['suite']}")
                for r in s["results"]:
                    status = "PASS" if r.get("passed") else "FAIL"
                    extra = ""
                    if r.get("issues"):
                        extra = f" — {', '.join(r['issues'])}"
                    if r.get("topics"):
                        extra = f" — topics: {', '.join(r['topics'])}"
                    lines.append(f"- {status}: {r.get('case', '?')}{extra}")
                lines.append("")

    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
