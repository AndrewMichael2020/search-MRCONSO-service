#!/usr/bin/env python3
"""
Massive-ish benchmark harness for BK-tree service and local engine.

Two modes:
  1) remote: load tests the deployed FastAPI service /search/bktree with async HTTP
  2) local: benchmarks in-process BKTree vs Python baseline

Outputs summary metrics and optionally writes a JSON report.

Examples:
  # Remote service benchmark (2000 queries, concurrency 25)
  python scripts/massive_benchmark.py remote \
    --base-url https://search-mrconso-service-160858128371.northamerica-northeast1.run.app \
    --queries 2000 --concurrency 25 --maxdist 1 --out-json docs/reports/remote_bench.json

  # Local benchmark (100k terms, 1000 queries)
  python scripts/massive_benchmark.py local \
    --terms data/mrconso_sample.txt --limit-terms 100000 --queries 1000 --maxdist 1 \
    --out-json docs/reports/local_bench.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


def _percentiles(values: List[float], points=(50, 90, 95, 99)) -> dict:
    if not values:
        return {f"p{p}": None for p in points}
    vals = sorted(values)
    n = len(vals)
    def at(pct: float) -> float:
        k = (pct / 100.0) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            return vals[f]
        d = k - f
        return vals[f] * (1 - d) + vals[c] * d
    return {f"p{p}": at(p) for p in points}


# --------------------------- Remote benchmark ---------------------------------

async def _remote_worker(client, sem, base_url: str, endpoint: str, payload: dict, results: list):
    url = base_url.rstrip("/") + f"/search/{endpoint}"
    async with sem:
        t0 = time.perf_counter()
        try:
            r = await client.post(url, json=payload, timeout=30)
            latency = (time.perf_counter() - t0) * 1000.0
            ok = r.status_code == 200
            results.append({
                "status": r.status_code,
                "ok": ok,
                "latency_ms": latency,
                "count": len(r.json().get("matches", [])) if ok else 0,
            })
        except Exception as e:  # noqa: BLE001
            latency = (time.perf_counter() - t0) * 1000.0
            results.append({"status": -1, "ok": False, "latency_ms": latency, "error": str(e)})


async def run_remote_bench(args) -> dict:
    import httpx  # lazy import

    # Warm-up: check health and ensure loaded
    health_url = args.base_url.rstrip("/") + "/healthz/"
    async with httpx.AsyncClient(timeout=30) as client:
        hr = await client.get(health_url)
        hr.raise_for_status()
        h = hr.json()
        if not h.get("loaded"):
            raise RuntimeError("Service not loaded. Call /load first or enable AUTO_LOAD_ON_STARTUP.")

    # Build a query set: use either provided terms file or synthetic generator
    queries = []
    if args.query_terms and os.path.exists(args.query_terms):
        with open(args.query_terms, "r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if args.limit_terms and i >= args.limit_terms:
                    break
                term = line.strip()
                if "|" in term:
                    parts = term.split("|")
                    if len(parts) > 14:
                        term = parts[14].strip()
                    else:
                        continue
                if term:
                    queries.append(term)
    else:
        # Synthetic medical-like tokens as fallback
        prefixes = ["cardio", "neuro", "gastro", "hepato", "nephro", "osteo", "derma", "pulmo"]
        suffixes = ["itis", "osis", "pathy", "plasty", "ectomy", "algia", "megaly", "stenosis"]
        for _ in range(max(1000, args.queries)):
            base = random.choice(prefixes) + random.choice(suffixes)
            queries.append(base)

    if not queries:
        raise RuntimeError("No queries available to run")

    # Randomly sample the requested number of queries and add noisy variants
    base_queries = random.sample(queries, min(args.queries, len(queries)))

    def mutate(s: str) -> str:
        if not s:
            return s
        ops = ["sub", "ins", "del"]
        op = random.choice(ops)
        pos = random.randrange(len(s))
        ch = random.choice("abcdefghijklmnopqrstuvwxyz")
        if op == "sub":
            return s[:pos] + ch + s[pos + 1:]
        if op == "ins":
            return s[:pos] + ch + s[pos:]
        # del
        return s[:pos] + s[pos + 1:]

    prepared = []
    for q in base_queries:
        q2 = mutate(q) if args.maxdist >= 1 else q
        prepared.append({"query": q2, "maxdist": args.maxdist})

    sem = asyncio.Semaphore(args.concurrency)
    results: list = []
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [asyncio.create_task(_remote_worker(client, sem, args.base_url, args.endpoint, p, results)) for p in prepared]
        await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - started

    latencies = [r["latency_ms"] for r in results]
    pcts = _percentiles(latencies)
    success = sum(1 for r in results if r.get("ok"))
    fail = len(results) - success
    rps = len(results) / elapsed if elapsed > 0 else 0.0

    summary = {
        "mode": "remote",
        "endpoint": args.endpoint,
        "base_url": args.base_url,
        "queries": len(results),
        "concurrency": args.concurrency,
        "maxdist": args.maxdist,
        "duration_sec": round(elapsed, 3),
        "rps": round(rps, 2),
        "success": success,
        "fail": fail,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else None,
            "avg": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
            **{k: (round(v, 2) if v is not None else None) for k, v in pcts.items()},
        },
    }
    return summary


# --------------------------- Local benchmark ----------------------------------

def load_terms(path: str, limit: int | None) -> List[str]:
    terms: List[str] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                break
            if "|" in line:
                parts = line.split("|")
                if len(parts) > 14:
                    t = parts[14].strip()
                    if t:
                        terms.append(t)
            else:
                t = line.strip()
                if t:
                    terms.append(t)
    return terms


def run_local_bench(args) -> dict:
    from cppmatch import BKTree
    from rapidfuzz.distance import Levenshtein

    if not args.terms or not os.path.exists(args.terms):
        raise RuntimeError("--terms is required for local mode and must exist")

    terms = load_terms(args.terms, args.limit_terms)
    if not terms:
        raise RuntimeError("No terms loaded")

    # Build BK-tree
    t0 = time.time()
    tree = BKTree()
    for t in terms:
        tree.insert(t)
    build_sec = time.time() - t0

    # Prepare queries
    n = min(args.queries, len(terms))
    queries = random.sample(terms, n)

    # BK-tree benchmark
    t0 = time.time()
    for q in queries:
        _ = tree.search(q, args.maxdist)
    bkt_sec = time.time() - t0

    # Python baseline (optional)
    py_sec = None
    if not args.skip_python:
        t0 = time.time()
        for q in queries:
            _ = min(terms, key=lambda t: Levenshtein.distance(q, t))
        py_sec = time.time() - t0

    summary = {
        "mode": "local",
        "terms": len(terms),
        "maxdist": args.maxdist,
        "queries": n,
        "build_sec": round(build_sec, 3),
        "bkt_sec": round(bkt_sec, 3),
        "bkt_qps": round(n / max(bkt_sec, 1e-9), 2),
        "python_sec": round(py_sec, 3) if py_sec is not None else None,
        "python_qps": round(n / max(py_sec, 1e-9), 2) if py_sec is not None else None,
        "speedup_py_over_bkt": round(py_sec / bkt_sec, 2) if py_sec is not None else None,
    }
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Massive-ish benchmark harness")
    sub = p.add_subparsers(dest="mode", required=True)

    # remote subcommand
    pr = sub.add_parser("remote", help="Load test the deployed service via HTTP")
    pr.add_argument("--base-url", required=True, help="Service base URL (e.g., https://...run.app)")
    pr.add_argument("--queries", type=int, default=2000, help="Number of requests to send")
    pr.add_argument("--concurrency", type=int, default=25, help="Concurrent requests")
    pr.add_argument("--maxdist", type=int, default=1, help="Levenshtein max distance")
    pr.add_argument("--endpoint", choices=["bktree", "python"], default="bktree", help="Remote endpoint to test")
    pr.add_argument("--query-terms", help="Optional local file with terms to seed requests (RRF or terms)")
    pr.add_argument("--limit-terms", type=int, help="Optional cap when reading --query-terms")
    pr.add_argument("--out-json", help="Write summary JSON to this path")

    # local subcommand
    pl = sub.add_parser("local", help="Benchmark in-process BKTree vs Python baseline")
    pl.add_argument("--terms", required=True, help="Terms file (RRF or terms)")
    pl.add_argument("--limit-terms", type=int, help="Optional cap when reading terms file")
    pl.add_argument("--queries", type=int, default=1000, help="Number of queries")
    pl.add_argument("--maxdist", type=int, default=1, help="Levenshtein max distance")
    pl.add_argument("--skip-python", action="store_true", help="Skip the Python baseline timing")
    pl.add_argument("--out-json", help="Write summary JSON to this path")

    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "remote":
        summary = asyncio.run(run_remote_bench(args))
    else:
        summary = run_local_bench(args)

    print("\n==== BENCHMARK SUMMARY ====")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nWrote report to {out_path}")


if __name__ == "__main__":
    main()
