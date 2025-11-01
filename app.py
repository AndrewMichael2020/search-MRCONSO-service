"""
FastAPI app for BK-tree vs Python fuzzy search on MRCONSO terms.
Endpoints: /healthz, /search/bktree, /search/python, /benchmarks/run
"""
import os, random, time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein

app = FastAPI(title="BKTree vs Python Search", version="0.1.1")

TERMS = []
TREE = BKTree()

class SearchReq(BaseModel):
    query: str
    maxdist: int = 1

@app.on_event("startup")
async def startup():
    """Load terms from MRCONSO.RRF and build BK-tree index."""
    global TERMS, TREE

    # pick up path from env var or fallback to default
    path = os.getenv("MRCONSO_PATH", "data/umls/2025AA/META/MRCONSO.RRF")
    if not os.path.exists(path):
        raise RuntimeError(f"MRCONSO file missing: {path}")

    print(f"Loading terms from {path} ...")
    skipped = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "|" not in line:
                skipped += 1
                continue
            parts = line.split("|")
            # MRCONSO term string at position 14 (STR)
            if len(parts) > 14:
                term = parts[14].strip()
                if term:
                    TERMS.append(term)
            else:
                skipped += 1

    print(f"Loaded {len(TERMS)} terms (skipped {skipped})")

    print("Building BK-tree index ...")
    t0 = time.time()
    for t in TERMS:
        TREE.insert(t)
    print(f"BK-tree built in {time.time()-t0:.2f} s")

@app.get("/healthz")
async def health():
    return {"status": "ok", "terms": len(TERMS)}

@app.post("/search/bktree")
async def search_bktree(req: SearchReq):
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    res = TREE.search(req.query, req.maxdist)
    return {"matches": [{"term": t, "distance": d} for t, d in res]}

@app.post("/search/python")
async def search_python(req: SearchReq):
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    best = min(TERMS, key=lambda t: Levenshtein.distance(req.query, t))
    dist = int(Levenshtein.distance(req.query, best))
    return {"matches": [{"term": best, "distance": dist}]}

@app.post("/benchmarks/run")
async def run_benchmarks():
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    sample = random.sample(TERMS, min(100, len(TERMS)))

    t0 = time.time()
    for q in sample:
        TREE.search(q, 1)
    bkt_time = time.time() - t0

    t0 = time.time()
    for q in sample:
        _ = min(TERMS, key=lambda t: Levenshtein.distance(q, t))
    py_time = time.time() - t0

    return {
        "queries": len(sample),
        "bktree_sec": round(bkt_time, 3),
        "python_sec": round(py_time, 3),
        "ratio_python_over_bktree": round(py_time / max(bkt_time, 1e-9), 2)
    }
