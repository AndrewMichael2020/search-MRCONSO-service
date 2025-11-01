"""
FastAPI app for BK-tree vs Python fuzzy search on MRCONSO terms.
Endpoints:
  /healthz
  /load              -> trigger MRCONSO load (manual or from startup task)
  /search/bktree
  /search/python
  /benchmarks/run
"""

import os
import random
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein

# Create FastAPI app
app = FastAPI(title="BKTree vs Python Search", version="0.2.0")

TERMS = []
TREE = BKTree()
LOADED = False


class SearchReq(BaseModel):
    query: str
    maxdist: int = 1


def load_terms():
    """Load MRCONSO terms from local or GCS file and build BK-tree index."""
    global TERMS, TREE, LOADED

    if LOADED:
        print("MRCONSO already loaded.")
        return len(TERMS)

    path = os.getenv("MRCONSO_PATH", "data/umls/2025AA/META/MRCONSO.RRF")
    print(f"Loading MRCONSO from {path} ...")

    text_lines = []
    if path.startswith("gs://"):
        from google.cloud import storage
        client = storage.Client()
        bucket_name, blob_name = path.replace("gs://", "").split("/", 1)
        blob = client.bucket(bucket_name).blob(blob_name)
        print("Downloading MRCONSO.RRF from GCS (this may take a while)...")
        data = blob.download_as_text(encoding="utf-8", errors="ignore").splitlines()
        text_lines = data
    elif os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text_lines = f.readlines()
    else:
        raise RuntimeError(f"MRCONSO file not found at {path}")

    skipped = 0
    for line in text_lines:
        parts = line.split("|")
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
    print(f"BK-tree built in {time.time() - t0:.2f}s")

    LOADED = True
    return len(TERMS)


@app.get("/healthz")
async def health():
    """Check readiness of the app."""
    return {"status": "ok", "terms": len(TERMS), "loaded": LOADED}


@app.post("/load")
async def trigger_load():
    """Trigger MRCONSO load manually (to avoid Cloud Run timeout)."""
    try:
        count = load_terms()
        return {"status": "loaded", "terms": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        "ratio_python_over_bktree": round(py_time / max(bkt_time, 1e-9), 2),
    }


# Local test entrypoint (Cloud Run uses Gunicorn)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
