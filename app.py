"""
FastAPI app for BK-tree vs Python fuzzy search on MRCONSO-like terms.
Endpoints: /healthz, /search/bktree, /search/python, /benchmarks/run
"""
import os
import random
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein

app = FastAPI(title="BKTree vs Python Search", version="0.1.0")

TERMS = []
TREE = BKTree()


class SearchReq(BaseModel):
    query: str
    maxdist: int = 1


@app.on_event("startup")
async def startup():
    """Load terms from file and build BK-tree index."""
    global TERMS, TREE
    
    path = os.getenv("TERMS_PATH", "data/mrconso_sample.txt")
    if not os.path.exists(path):
        raise RuntimeError(f"Terms file missing: {path}")
    
    print(f"Loading terms from {path}...")
    skipped = 0
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if '|' in line:
                parts = line.split('|')
                if len(parts) > 14:
                    term = parts[14].strip()
                    if term:
                        TERMS.append(term)
                else:
                    skipped += 1
            else:
                skipped += 1
    
    print(f"Loaded {len(TERMS)} terms (skipped {skipped} invalid lines)")
    
    print("Building BK-tree index...")
    start = time.time()
    for t in TERMS:
        TREE.insert(t)
    build_time = time.time() - start
    print(f"BK-tree built in {build_time:.2f} seconds")


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "terms": len(TERMS)}


@app.post("/search/bktree")
async def search_bktree(req: SearchReq):
    """Search using BK-tree (C++ implementation)."""
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    
    results = TREE.search(req.query, req.maxdist)
    return {"matches": [{"term": t, "distance": d} for t, d in results]}


@app.post("/search/python")
async def search_python(req: SearchReq):
    """Search using pure Python (baseline)."""
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    
    # Naive approach: find best match only
    best = min(TERMS, key=lambda t: Levenshtein.distance(req.query, t))
    dist = int(Levenshtein.distance(req.query, best))
    
    return {"matches": [{"term": best, "distance": dist}]}


@app.post("/benchmarks/run")
async def run_benchmarks():
    """Run benchmark comparing BK-tree vs Python on random queries."""
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    
    # Sample 100 random queries
    sample = random.sample(TERMS, min(100, len(TERMS)))
    
    # Benchmark BK-tree
    t0 = time.time()
    for q in sample:
        TREE.search(q, 1)
    bkt_time = time.time() - t0
    
    # Benchmark Python
    t0 = time.time()
    for q in sample:
        _ = min(TERMS, key=lambda t: Levenshtein.distance(q, t))
    py_time = time.time() - t0
    
    ratio = py_time / max(bkt_time, 1e-9)
    
    return {
        "queries": len(sample),
        "bktree_sec": round(bkt_time, 3),
        "python_sec": round(py_time, 3),
        "ratio_python_over_bktree": round(ratio, 2)
    }
