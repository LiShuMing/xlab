"""CLI entry point: python -m llm_research --product NAME --depth DEPTH."""
from __future__ import annotations

import argparse
from pathlib import Path

from .prompt_learner import scan_and_learn, PROMPTS_OUTPUT_PATH
from .researcher import generate_and_save


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM API Deep Research Report Generator")
    parser.add_argument("--product", required=True, help="LLM API product name")
    parser.add_argument("--depth", default="deep", choices=["standard", "deep", "executive"])
    parser.add_argument("--language", default="English")
    parser.add_argument("--learn", action="store_true", help="Re-learn prompts before generating")
    args = parser.parse_args()

    if args.learn or not PROMPTS_OUTPUT_PATH.exists():
        print("Learning prompts from reference docs...")
        scan_and_learn()

    print(f"Generating report for: {args.product} (depth={args.depth})...")
    path = generate_and_save(args.product, args.language, args.depth)
    print(f"Report saved: {path}")


if __name__ == "__main__":
    main()
