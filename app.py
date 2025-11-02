"""
FastAPI app for BK-tree vs Python fuzzy search on MRCONSO terms.
Endpoints:
    /healthz
    /load              -> trigger MRCONSO load (manual or from startup task)
    /search/bktree
    /search/python
    /benchmarks/run
"""

import logging
import os
import random
import time
from contextlib import contextmanager
from typing import Iterable, Iterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("search_mrconso_service")

# Create FastAPI app
app = FastAPI(title="BKTree vs Python Search", version="0.2.0", redirect_slashes=False)

# Explicitly disable slash-redirects in case upstream FastAPI ignores the constructor flag.
app.router.redirect_slashes = False

TERMS = []
TREE = BKTree()
LOADED = False
MAX_TERMS = int(os.getenv("MAX_TERMS", "0") or 0) or None


class SearchReq(BaseModel):
    query: str
    maxdist: int = 1


@contextmanager
def _open_mrconso(path: str):
    if path.startswith("gs://"):
        from google.cloud import storage  # Lazy import to keep local runs lightweight.

        client = storage.Client()
        bucket_name, blob_name = path.replace("gs://", "", 1).split("/", 1)
        blob = client.bucket(bucket_name).blob(blob_name)
        logger.info("Streaming MRCONSO directly from GCS blob gs://%s/%s", bucket_name, blob_name)
        with blob.open("r", encoding="utf-8", errors="ignore") as fh:
            yield fh
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            yield fh


def _iter_terms(lines: Iterable[str]) -> Iterator[str]:
    skipped = 0
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("|")
        if len(parts) > 14:
            term = parts[14].strip()
            if term:
                yield term
        else:
            skipped += 1
        if line_number % 500_000 == 0:
            logger.info("Processed %d lines from MRCONSO", line_number)
    if skipped:
        logger.info("Skipped %d malformed MRCONSO rows", skipped)


def load_terms():
    """Load MRCONSO terms from local or GCS file and build BK-tree index."""
    global TERMS, TREE, LOADED

    if LOADED:
        logger.info("MRCONSO already loaded; skipping reload.")
        return len(TERMS)

    path = os.getenv("MRCONSO_PATH", "data/umls/2025AA/MRCONSO.RRF")
    logger.info("Loading MRCONSO from %s ...", path)

    if not path.startswith("gs://") and not os.path.exists(path):
        msg = f"MRCONSO file not found at {path}"
        logger.error(msg)
        raise RuntimeError(msg)

    loaded_terms = []
    start = time.time()
    limit = MAX_TERMS
    with _open_mrconso(path) as handle:
        for idx, term in enumerate(_iter_terms(handle), start=1):
            loaded_terms.append(term)
            if limit and idx >= limit:
                logger.warning("Reached MAX_TERMS=%d; stopping early", limit)
                break

    logger.info("Loaded %d terms in %.2fs", len(loaded_terms), time.time() - start)

    logger.info("Building BK-tree index ...")
    t0 = time.time()
    TREE = BKTree()  # Reset tree in case we are reloading after failure.
    for term in loaded_terms:
        TREE.insert(term)
    logger.info("BK-tree built in %.2fs", time.time() - t0)

    TERMS = loaded_terms
    LOADED = True
    return len(TERMS)


@app.get("/healthz")
@app.get("/healthz/")
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
        logger.exception("Failed to load MRCONSO data")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
