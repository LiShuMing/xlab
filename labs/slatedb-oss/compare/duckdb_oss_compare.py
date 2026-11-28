#!/usr/bin/env python3
"""Same-bucket DuckDB + Parquet (columnar) vs SlateDB (row LSM KV) comparison on Aliyun OSS.

Uses the exact same non-versioned OSS bucket (`xlab-slatedb-dev`) under an isolated
`compare/` prefix, runs columnar Parquet write + point/scan/aggregate queries over
DuckDB's S3/httpfs interface, emits a structured JSON report, and cleans up all
temporary objects afterward. Never prints credentials.
"""

from __future__ import annotations

import argparse
import base64
import email.utils
import hashlib
import hmac
import json
import os
import statistics
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import duckdb


def load_oss_config(bucket_override: str | None) -> dict[str, str]:
    env_file = Path.home() / ".env"
    file_env: dict[str, str] = {}
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            file_env[k.strip()] = v.strip().strip('"').strip("'")

    def pick(*keys: str, default: str | None = None) -> str:
        for k in keys:
            val = os.environ.get(k) or file_env.get(k)
            if val and val.strip():
                return val.strip()
        if default is not None:
            return default
        raise RuntimeError(f"Missing required OSS setting (tried: {', '.join(keys)})")

    endpoint = (
        pick("SLATEDB_OSS_ENDPOINT", "DB_RADAR_OSS_ENDPOINT", "OSS_ENDPOINT")
        .replace("https://", "")
        .replace("http://", "")
        .strip("/")
    )
    region = endpoint.split(".")[0] if endpoint.startswith("oss-") else "oss-cn-beijing"
    return {
        "access_key_id": pick(
            "SLATEDB_OSS_ACCESS_KEY_ID", "DB_RADAR_OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_ID"
        ),
        "access_key_secret": pick(
            "SLATEDB_OSS_ACCESS_KEY_SECRET",
            "DB_RADAR_OSS_ACCESS_KEY_SECRET",
            "OSS_ACCESS_KEY_SECRET",
        ),
        "endpoint": endpoint,
        "region": region,
        "bucket": bucket_override or pick("SLATEDB_OSS_BUCKET", default="xlab-slatedb-dev"),
    }


def oss_signed_request(
    cfg: dict[str, str],
    method: str,
    path: str,
    query: str = "",
    subresource: str = "",
) -> tuple[int, bytes]:
    date_str = email.utils.formatdate(usegmt=True)
    host = f"{cfg['bucket']}.{cfg['endpoint']}"
    canon_res = f"/{cfg['bucket']}{path}" + (f"?{subresource}" if subresource else "")
    sts = f"{method}\n\n\n{date_str}\n{canon_res}"
    sig = base64.b64encode(
        hmac.new(cfg["access_key_secret"].encode(), sts.encode(), hashlib.sha1).digest()
    ).decode()
    url = f"https://{host}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(
        url,
        headers={"Date": date_str, "Authorization": f"OSS {cfg['access_key_id']}:{sig}"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read()


def cleanup_oss_prefix(cfg: dict[str, str], prefix: str) -> int:
    q = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    st, data = oss_signed_request(cfg, "GET", "/", query=q)
    if st != 200:
        return 0
    root = ET.fromstring(data)
    ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    deleted = 0
    for c in root.findall(f"{ns}Contents"):
        key = c.findtext(f"{ns}Key")
        if key:
            oss_signed_request(cfg, "DELETE", "/" + urllib.parse.quote(key, safe="/"))
            deleted += 1
    return deleted


def run_duckdb_compare(cfg: dict[str, str], rows: int, point_queries: int) -> dict[str, Any]:
    prefix = f"compare/duckdb-{uuid.uuid4().hex[:10]}"
    s3_uri = f"s3://{cfg['bucket']}/{prefix}/dataset.parquet"

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        """
        CREATE SECRET oss_secret (
            TYPE S3,
            KEY_ID $ak,
            SECRET $sk,
            REGION $region,
            ENDPOINT $endpoint,
            URL_STYLE 'vhost',
            USE_SSL true
        );
        """,
        {
            "ak": cfg["access_key_id"],
            "sk": cfg["access_key_secret"],
            "region": cfg["region"],
            "endpoint": cfg["endpoint"],
        },
    )

    try:
        # 1. Batch columnar Parquet write to OSS
        t0 = time.perf_counter()
        con.execute(
            f"""
            COPY (
                SELECT
                    printf('k_%06d', i) AS k,
                    repeat('x', 256) AS v,
                    i % 100 AS grp,
                    i * 1.5 AS metric
                FROM range({rows}) t(i)
            ) TO '{s3_uri}' (FORMAT PARQUET, COMPRESSION ZSTD);
            """
        )
        write_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 2. Point lookups over Parquet on OSS
        point_lats: list[float] = []
        for i in range(point_queries):
            target = f"k_{(i * max(1, rows // max(1, point_queries))):06d}"
            ts = time.perf_counter()
            row = con.execute(
                f"SELECT k, length(v) FROM read_parquet('{s3_uri}') WHERE k = ?", [target]
            ).fetchone()
            assert row is not None and row[0] == target
            point_lats.append((time.perf_counter() - ts) * 1000.0)
        point_lats.sort()

        # 3. Full analytical group-by scan over OSS Parquet
        t_agg = time.perf_counter()
        agg_rows = con.execute(
            f"SELECT grp, count(*), sum(metric) FROM read_parquet('{s3_uri}') GROUP BY grp"
        ).fetchall()
        agg_ms = round((time.perf_counter() - t_agg) * 1000.0, 2)
        assert len(agg_rows) == min(100, rows)

        return {
            "lab": "duckdb-oss-compare",
            "bucket": cfg["bucket"],
            "endpoint": cfg["endpoint"],
            "prefix": prefix,
            "rows": rows,
            "batch_parquet_write_ms": write_ms,
            "point_queries": point_queries,
            "point_lookup_p50_ms": round(statistics.median(point_lats), 2),
            "point_lookup_mean_ms": round(statistics.mean(point_lats), 2),
            "full_groupby_scan_ms": agg_ms,
        }
    finally:
        con.close()
        deleted = cleanup_oss_prefix(cfg, prefix)
        print(f"[CLEANUP] Deleted {deleted} objects under `{prefix}`.")


def main() -> None:
    parser = argparse.ArgumentParser(description="DuckDB + Parquet over Aliyun OSS comparison.")
    parser.add_argument("--bucket", default=None, help="OSS bucket (default: xlab-slatedb-dev)")
    parser.add_argument("--rows", type=int, default=10000, help="Rows to write to Parquet")
    parser.add_argument("--point-queries", type=int, default=5, help="Point lookup iterations")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()

    cfg = load_oss_config(args.bucket)
    report = run_duckdb_compare(cfg, rows=args.rows, point_queries=args.point_queries)
    print(json.dumps(report, indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
