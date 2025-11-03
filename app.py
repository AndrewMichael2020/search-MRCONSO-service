"""FastAPI service for BK-tree search on MRCONSO terms."""

import asyncio
import json
import logging
import os
import random
import tarfile
import tempfile
import time
from contextlib import asynccontextmanager, contextmanager, suppress
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Iterator

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse
from urllib.parse import urlparse, urlunparse


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("search_mrconso_service")

def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


MAX_TERMS = int(os.getenv("MAX_TERMS", "0") or 0) or None
ENABLE_PYTHON_BASELINE = _parse_bool(os.getenv("ENABLE_PYTHON_BASELINE"), default=True)
AUTO_LOAD_ON_STARTUP = _parse_bool(os.getenv("AUTO_LOAD_ON_STARTUP"))
MRCONSO_FORMAT = os.getenv("MRCONSO_FORMAT", "rrf").lower()
SHUTDOWN_AFTER_SECONDS = int(os.getenv("SHUTDOWN_AFTER_SECONDS", "0") or 0) or None
# Normalize artifact path: treat missing or whitespace-only as None to avoid false positives
_ART_RAW = os.getenv("BKTREE_ARTIFACT_PATH", "")
BKTREE_ARTIFACT_PATH = (_ART_RAW.strip() or None)
CANONICAL_BASE_URL = os.getenv("CANONICAL_BASE_URL", "").strip()

TERMS: list[str] = []
TREE = BKTree()
TERM_COUNT = 0
LOADED = False
LOADING = False
LAST_LOAD_ERROR: str | None = None
ARTIFACT_METADATA: dict[str, Any] | None = None
_load_lock = Lock()
_shutdown_task: asyncio.Task | None = None


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
        with blob.open("r", encoding="utf-8", errors="ignore", chunk_size=1 << 20) as fh:
            yield fh
    else:
        with open(path, "r", encoding="utf-8", errors="ignore", buffering=1 << 20) as fh:
            yield fh


def _ensure_local_artifact(path: str) -> tuple[Path, bool]:
    """Ensure the BK-tree artifact exists locally; download from GCS if required.

    Prefers a RAM-backed tmp directory if available to avoid filling /tmp on Cloud Run.
    Returns (local_path, should_cleanup).
    """

    if not path.startswith("gs://"):
        return Path(path), False

    from google.cloud import storage  # Lazy import to keep local runs lightweight.

    client = storage.Client()
    bucket_name, blob_name = path.replace("gs://", "", 1).split("/", 1)
    blob = client.bucket(bucket_name).blob(blob_name)

    # Choose target tmp dir: prefer BK_TMP_DIR if explicitly provided and writable,
    # otherwise default to the system temp dir (typically /tmp on Cloud Run).
    preferred_tmp = os.getenv("BK_TMP_DIR")
    tmp_root = Path(preferred_tmp) if preferred_tmp else Path(tempfile.gettempdir())
    if not tmp_root.exists() or not os.access(tmp_root, os.W_OK):
        tmp_root = Path(tempfile.gettempdir())
    tmp_root.mkdir(parents=True, exist_ok=True)

    handle = tempfile.NamedTemporaryFile(prefix="bktree_artifact_", suffix=".tar.gz", delete=False, dir=tmp_root)
    handle.close()
    tmp_path = Path(handle.name)

    logger.info("Downloading BK-tree artifact from gs://%s/%s to %s", bucket_name, blob_name, tmp_path)
    start = time.time()
    blob.download_to_filename(tmp_path.as_posix())
    try:
        size_mb = tmp_path.stat().st_size / (1024 * 1024)
    except Exception:
        size_mb = -1
    logger.info("Finished downloading BK-tree artifact (%.2f MB) in %.2fs", size_mb, time.time() - start)
    return tmp_path, True


def _load_bktree_artifact(path: str) -> tuple[BKTree, dict[str, Any]]:
    """Load a serialized BK-tree from a tar.gz artifact and return (tree, metadata).

    Stream-extracts only the required members and writes the large binary into a RAM-backed
    directory when possible to avoid exhausting /tmp disk.
    """

    local_path, should_cleanup = _ensure_local_artifact(path)
    metadata: dict[str, Any]
    tree_path: Path | None = None
    try:
        logger.info("Opening artifact tar %s", local_path)
        with tarfile.open(local_path, "r:gz") as tar:
            names = set(tar.getnames())
            if "metadata.json" not in names or "bktree.bin" not in names:
                raise RuntimeError("BK-tree artifact missing required files")

            with tar.extractfile("metadata.json") as mfh:
                if mfh is None:
                    raise RuntimeError("Failed to extract metadata.json from artifact")
                metadata = json.loads(mfh.read().decode("utf-8"))
            logger.info("Read artifact metadata: term_count=%s", metadata.get("term_count"))

            preferred_tmp = os.getenv("BK_TMP_DIR")
            tmp_root = Path(preferred_tmp) if preferred_tmp else Path(tempfile.gettempdir())
            if not tmp_root.exists() or not os.access(tmp_root, os.W_OK):
                tmp_root = Path(tempfile.gettempdir())
            tmp_root.mkdir(parents=True, exist_ok=True)

            handle = tempfile.NamedTemporaryFile(prefix="bktree_", suffix=".bin", delete=False, dir=tmp_root)
            handle.close()
            tree_path = Path(handle.name)
            logger.info("Extracting bktree.bin to %s", tree_path)

            copied = 0
            with tar.extractfile("bktree.bin") as src, open(tree_path, "wb", buffering=1 << 20) as dst:
                if src is None:
                    raise RuntimeError("Failed to extract bktree.bin from artifact")
                while True:
                    chunk = src.read(16 * 1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    if copied % (512 * 1024 * 1024) < len(chunk):
                        logger.info("...extracted %.1f GiB", copied / (1024**3))
            try:
                size_gb = tree_path.stat().st_size / (1024**3)
            except Exception:
                size_gb = -1
            logger.info("Finished extracting bktree.bin (%.2f GiB)", size_gb)

        logger.info("Loading BK-tree from %s ...", tree_path)
        start = time.time()
        tree = BKTree.load(str(tree_path))
        logger.info("BK-tree binary loaded in %.2fs", time.time() - start)
        return tree, metadata
    finally:
        # Best-effort cleanup of large temp files
        with suppress(Exception):
            if tree_path and tree_path.exists():
                tree_path.unlink()
        if should_cleanup:
            with suppress(Exception):
                local_path.unlink()


def _iter_terms(lines: Iterable[str]) -> Iterator[str]:
    skipped = 0
    if MRCONSO_FORMAT == "terms":
        for line_number, line in enumerate(lines, start=1):
            term = line.strip()
            if term:
                yield term
            else:
                skipped += 1
            if line_number % 500_000 == 0:
                logger.info("Processed %d terms from cache", line_number)
    else:
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
        logger.info("Skipped %d malformed/empty rows", skipped)


def load_terms(force: bool = False) -> int:
    """Load MRCONSO terms from local or GCS file and build BK-tree index."""
    global TERMS, TREE, TERM_COUNT, LOADED, LOADING, LAST_LOAD_ERROR, ARTIFACT_METADATA

    if LOADED and not force:
        logger.info("MRCONSO already loaded; skipping reload.")
        return TERM_COUNT
    if LOADING and not force:
        logger.info("MRCONSO load already in progress; returning current count=%d", TERM_COUNT)
        return TERM_COUNT

    acquired = _load_lock.acquire(blocking=False)
    if not acquired:
        logger.info("Another load operation is holding the lock; returning current count=%d", TERM_COUNT)
        return TERM_COUNT

    LOADING = True
    LAST_LOAD_ERROR = None
    try:
        if LOADED and not force:
            return TERM_COUNT

        artifact_path = BKTREE_ARTIFACT_PATH
        new_tree: BKTree | None = None
        metadata: dict[str, Any] | None = None
        term_count = 0
        new_terms: list[str] | None = None

        if artifact_path:
            try:
                logger.info("Attempting to load BK-tree artifact from %s", artifact_path)
                new_tree, metadata = _load_bktree_artifact(artifact_path)
                term_count = int(metadata.get("term_count", 0) or 0)
                if term_count <= 0:
                    logger.warning("Artifact metadata missing term_count; term count will be reported as 0")
                if ENABLE_PYTHON_BASELINE:
                    logger.warning("Python baseline unavailable when using BK-tree artifact; /search/python will return 503")
                new_terms = []
                logger.info("Loaded BK-tree artifact successfully (terms=%s)", term_count or "unknown")
            except Exception:
                logger.exception("Failed to load BK-tree artifact; falling back to raw MRCONSO")
                new_tree = None
                metadata = None
                term_count = 0

        if new_tree is None:
            path = os.getenv("MRCONSO_PATH", "data/umls/2025AA/MRCONSO.RRF")
            logger.info("Loading MRCONSO from %s ...", path)

            if not path.startswith("gs://") and not os.path.exists(path):
                msg = f"MRCONSO file not found at {path}"
                logger.error(msg)
                raise RuntimeError(msg)

            start = time.time()
            limit = MAX_TERMS
            new_terms = [] if ENABLE_PYTHON_BASELINE else None
            new_tree = BKTree()

            with _open_mrconso(path) as handle:
                for idx, term in enumerate(_iter_terms(handle), start=1):
                    new_tree.insert(term)
                    if new_terms is not None:
                        new_terms.append(term)
                    term_count = idx
                    if limit and idx >= limit:
                        logger.warning("Reached MAX_TERMS=%d; stopping early", limit)
                        break

            logger.info("Loaded %d terms in %.2fs", term_count, time.time() - start)
            metadata = None

        TREE = new_tree
        TERMS = new_terms or []
        TERM_COUNT = term_count
        ARTIFACT_METADATA = metadata
        LOADED = True
        return TERM_COUNT
    except Exception as exc:  # noqa: BLE001
        LAST_LOAD_ERROR = str(exc)
        TREE = BKTree()
        TERMS = []
        TERM_COUNT = 0
        LOADED = False
        ARTIFACT_METADATA = None
        logger.exception("Failed to load MRCONSO data")
        raise
    finally:
        LOADING = False
        _load_lock.release()


def _schedule_shutdown_timer() -> None:
    """Schedule a container shutdown after the configured delay."""
    global _shutdown_task

    if not SHUTDOWN_AFTER_SECONDS:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("No running event loop; cannot schedule shutdown timer yet")
        return

    if _shutdown_task and not _shutdown_task.done():
        _shutdown_task.cancel()

    async def _shutdown_worker():
        try:
            logger.info("Scheduling auto shutdown in %d seconds", SHUTDOWN_AFTER_SECONDS)
            await asyncio.sleep(SHUTDOWN_AFTER_SECONDS)
            logger.warning("Auto shutdown triggered after %d seconds", SHUTDOWN_AFTER_SECONDS)
            os._exit(0)
        except asyncio.CancelledError:
            logger.info("Auto shutdown timer cancelled")

    _shutdown_task = loop.create_task(_shutdown_worker())


@asynccontextmanager
async def _lifespan_handler(_: FastAPI):
    global _shutdown_task
    if AUTO_LOAD_ON_STARTUP:
        logger.info("AUTO_LOAD_ON_STARTUP=true: starting MRCONSO load in background")
        asyncio.create_task(_background_load_wrapper())
    else:
        logger.info("AUTO_LOAD_ON_STARTUP=false: skipping automatic load; call POST /load to load MRCONSO")

    try:
        yield
    finally:
        if _shutdown_task and not _shutdown_task.done():
            _shutdown_task.cancel()
            with suppress(Exception):
                await _shutdown_task
        _shutdown_task = None


# Create FastAPI app with lifespan handler
app = FastAPI(
    title="BKTree vs Python Search",
    version="0.2.0",
    redirect_slashes=False,
    lifespan=_lifespan_handler,
)

# Explicitly disable slash-redirects in case upstream FastAPI ignores the constructor flag.
app.router.redirect_slashes = False

# Canonical host redirection (optional; enabled only if CANONICAL_BASE_URL is set)
if CANONICAL_BASE_URL:
    parsed = urlparse(CANONICAL_BASE_URL)
    CANONICAL_NETLOC = parsed.netloc
    CANONICAL_SCHEME = parsed.scheme or "https"

    class _CanonicalHostMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Prefer X-Forwarded-Host/Proto when present (Cloud Run, proxies)
            fwd_host = request.headers.get("x-forwarded-host")
            fwd_proto = request.headers.get("x-forwarded-proto") or CANONICAL_SCHEME

            current_host = (fwd_host or request.url.hostname or "").lower()
            target_host = CANONICAL_NETLOC.lower()

            # Skip redirect if host already canonical or host unavailable (internal probes)
            if not current_host or current_host == target_host:
                return await call_next(request)

            # Build redirected absolute URL preserving path and query
            new_url = urlunparse(
                (
                    CANONICAL_SCHEME,
                    CANONICAL_NETLOC,
                    request.url.path,
                    "",
                    request.url.query,
                    "",
                )
            )
            return RedirectResponse(url=new_url, status_code=308)

    app.add_middleware(_CanonicalHostMiddleware)


@app.get("/healthz")
@app.get("/healthz/")
async def health():
    """Check readiness of the app."""
    return {
        "status": "ok",
        "terms": TERM_COUNT,
        "loaded": LOADED,
        "loading": LOADING,
        "baseline_enabled": ENABLE_PYTHON_BASELINE,
        "shutdown_after_seconds": SHUTDOWN_AFTER_SECONDS,
        "shutdown_timer_active": _shutdown_task is not None and not _shutdown_task.done(),
        "last_error": LAST_LOAD_ERROR,
        "artifact_loaded": ARTIFACT_METADATA is not None,
        "artifact_path": BKTREE_ARTIFACT_PATH,
        "artifact_term_count": ARTIFACT_METADATA.get("term_count") if ARTIFACT_METADATA else None,
    }


@app.post("/load")
async def trigger_load():
    """Trigger MRCONSO load manually (to avoid Cloud Run timeout)."""
    try:
        count = load_terms()
        _schedule_shutdown_timer()
        return {"status": "loaded", "terms": count, "baseline_enabled": ENABLE_PYTHON_BASELINE}
    except Exception as e:
        logger.exception("Failed to load MRCONSO data")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/search/bktree")
async def search_bktree(req: SearchReq):
    if not LOADED:
        raise HTTPException(503, "Terms not loaded yet")
    res = TREE.search(req.query, req.maxdist)
    return {"matches": [{"term": t, "distance": d} for t, d in res]}


@app.get("/search/bktree")
async def search_bktree_get(q: str, max_dist: int = 1, k: int | None = None):
    """Convenience GET endpoint for CLI users.

    Query params:
    - q: the query string
    - max_dist: maximum Levenshtein distance (alias for maxdist)
    - k: optional top-k results to return
    """
    if not LOADED:
        raise HTTPException(503, "Terms not loaded yet")
    results = TREE.search(q, max_dist)
    if k is not None and k >= 0:
        results = results[:k]
    return {"matches": [{"term": t, "distance": d} for t, d in results]}


@app.post("/search/python")
async def search_python(req: SearchReq):
    if not ENABLE_PYTHON_BASELINE:
        raise HTTPException(503, "Python baseline disabled (ENABLE_PYTHON_BASELINE=0)")
    if not LOADED or not TERMS:
        raise HTTPException(503, "Terms not loaded yet")
    best = min(TERMS, key=lambda t: Levenshtein.distance(req.query, t))
    dist = int(Levenshtein.distance(req.query, best))
    return {"matches": [{"term": best, "distance": dist}]}


@app.get("/search/python")
async def search_python_get(q: str):
    """Convenience GET variant for baseline search.

    Note: This will return 503 in production when baseline is disabled or when
    running with a pre-built BK-tree artifact (TERMS list not populated).
    """
    if not ENABLE_PYTHON_BASELINE:
        raise HTTPException(503, "Python baseline disabled (ENABLE_PYTHON_BASELINE=0)")
    if not LOADED or not TERMS:
        raise HTTPException(503, "Terms not loaded yet")
    best = min(TERMS, key=lambda t: Levenshtein.distance(q, t))
    dist = int(Levenshtein.distance(q, best))
    return {"matches": [{"term": best, "distance": dist}]}


@app.post("/benchmarks/run")
async def run_benchmarks():
    if not LOADED:
        raise HTTPException(503, "Terms not loaded yet")
    if not ENABLE_PYTHON_BASELINE:
        raise HTTPException(503, "Benchmarks unavailable (ENABLE_PYTHON_BASELINE=0)")
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


async def _background_load_wrapper():
    try:
        await asyncio.to_thread(load_terms)
        _schedule_shutdown_timer()
    except Exception:  # noqa: BLE001
        logger.exception("Background MRCONSO load failed")

