"""Disposable UI audit server: never use the owner's application tables or blobs."""

from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from pathlib import Path

import uvicorn
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panming.app import create_app  # noqa: E402
from panming.storage import ROOT, Store, database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm", action="store_true", help="显式启用现有 LLM 服务；仅用于授权合成输入测试"
    )
    args = parser.parse_args()
    schema = "panming_ui_audit_" + uuid.uuid4().hex
    admin = create_engine(database_url())
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    store = None
    try:
        with tempfile.TemporaryDirectory(prefix="ui-audit-", dir=ROOT / "data") as folder:
            store = Store(database_url(), Path(folder), {"options": f"-csearch_path={schema}"})
            # 5178 is an already-allowed local developer Origin; production 8788 stays untouched.
            print("隔离测试工作台：http://127.0.0.1:5178", flush=True)
            uvicorn.run(
                create_app(store, start_worker=True, enable_llm=args.llm),
                host="127.0.0.1",
                port=5178,
                log_level="warning",
            )
    finally:
        if store:
            store.engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
        print("已清理本次隔离测试 schema 与临时原件；用户数据未改动。", flush=True)


if __name__ == "__main__":
    main()
