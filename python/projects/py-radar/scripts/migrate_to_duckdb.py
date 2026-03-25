#!/usr/bin/env python3
"""Migration script: Convert JSON files to DuckDB storage.

Usage:
    python scripts/migrate_to_duckdb.py [--dry-run] [--json-dir DIR] [--data-dir DIR]

Options:
    --dry-run       Preview migration without writing
    --json-dir      Source JSON directory (default: ./out)
    --data-dir      Target DuckDB directory (default: ./data)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbradar.storage import DuckDBStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Migrate JSON files to DuckDB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=Path("out"),
        help="Source JSON directory (default: ./out)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Target DuckDB directory (default: ./data)",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default="items.duckdb",
        help="Database filename (default: items.duckdb)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("DB Radar Storage Migration")
    print("=" * 60)
    print(f"Source: {args.json_dir.absolute()}")
    print(f"Target: {args.data_dir.absolute()}/{args.db_name}")
    print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE MIGRATION'}")
    print("=" * 60)
    print()

    # Verify source exists
    if not args.json_dir.exists():
        logger.error(f"JSON directory not found: {args.json_dir}")
        sys.exit(1)

    # Initialize store
    store = DuckDBStore(
        data_dir=args.data_dir,
        db_name=args.db_name,
    )

    # Run migration
    stats = store.migrate_from_json(args.json_dir, dry_run=args.dry_run)

    print()
    print("=" * 60)
    print("Migration Results")
    print("=" * 60)
    print(f"JSON files found:  {stats['total_files']}")
    print(f"Items parsed:      {stats['total_items']}")
    print(f"Items inserted:    {stats['inserted']}")
    print(f"Errors:            {stats['errors']}")
    print("=" * 60)

    if not args.dry_run:
        # Show final stats
        final_stats = store.get_stats()
        print()
        print("Storage Statistics:")
        print(f"  Total items: {final_stats['total_count']}")
        print(f"  Database size: {final_stats['db_size_mb']:.2f} MB")
        print(f"  Database path: {final_stats['db_path']}")

        date_range = final_stats['date_range']
        if date_range[0] and date_range[1]:
            print(f"  Date range: {date_range[0]} to {date_range[1]}")

        if final_stats['by_content_type']:
            print("  By content type:")
            for ct, count in sorted(final_stats['by_content_type'].items()):
                print(f"    - {ct}: {count}")

    store.close()

    print()
    if args.dry_run:
        print("Dry run complete. Run without --dry-run to perform migration.")
    else:
        print("Migration complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
