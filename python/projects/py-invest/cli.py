#!/usr/bin/env python3
"""CLI interface for py-invest investment analysis."""

import argparse
import asyncio
import sys
from datetime import datetime


async def analyze_stock(stock_code: str, query: str, verbose: bool = False) -> int:
    """Run investment analysis on a stock.

    Args:
        stock_code: Stock ticker symbol (e.g., sh600519, AAPL).
        query: Analysis request (e.g., "综合分析", "技术分析").
        verbose: Show detailed progress.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from agents.orchestrator import SimpleAgentOrchestrator
        from modules.report_generator.formatter import ReportFormatter, ReportFormat

        if verbose:
            print(f"正在分析股票：{stock_code}", file=sys.stderr)
            print(f"分析请求：{query}", file=sys.stderr)
            print(file=sys.stderr)

        orchestrator = SimpleAgentOrchestrator()
        state = await orchestrator.analyze(stock_code, query)

        if state.error:
            print(f"分析失败：{state.error}", file=sys.stderr)
            return 1

        if state.report:
            # Output the markdown report to stdout
            print(ReportFormatter.format(state.report, ReportFormat.MARKDOWN))

            if verbose:
                print(file=sys.stderr)
                print(f"✓ 分析完成", file=sys.stderr)
                print(f"  股票代码：{state.report.stock_code}", file=sys.stderr)
                print(f"  目标价格：{state.report.target_price or 'N/A'}", file=sys.stderr)
                print(f"  评级：{state.report.rating or 'N/A'}", file=sys.stderr)
                print(f"  章节数：{len(state.report.sections)}", file=sys.stderr)
        else:
            # Fallback to final_response for backward compatibility
            if state.final_response:
                print(state.final_response)
            else:
                print("分析完成，但没有生成报告", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """Handle the 'analyze' command."""
    return asyncio.run(analyze_stock(args.code, args.query, args.verbose))


def cmd_version(args: argparse.Namespace) -> int:
    """Handle the 'version' command."""
    print("py-invest v0.1.0")
    return 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="py-invest",
        description="AI-powered investment analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze sh600519 "综合分析"
  %(prog)s analyze AAPL "估值分析" -v
  %(prog)s analyze 00700.HK "技术分析"
  %(prog)s version
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a stock",
        description="Run investment analysis on a specified stock"
    )
    analyze_parser.add_argument(
        "code",
        help="Stock ticker symbol (e.g., sh600519, AAPL, 00700.HK)"
    )
    analyze_parser.add_argument(
        "query",
        nargs="?",
        default="综合分析",
        help="Analysis request (default: 综合分析)"
    )
    analyze_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress"
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version info"
    )
    version_parser.set_defaults(func=cmd_version)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
