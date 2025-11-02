#!/usr/bin/env python3
"""Build and persist a serialized BK-tree for MRCONSO terms.

This Cloud Run Job performs the following steps:
1. Download ``MRCONSO.RRF`` (or a compatible cache) from GCS.
2. Parse the file and construct the BK-tree in memory using the shared ``cppmatch``
    extension.
3. Serialize the constructed BK-tree to a binary blob (pickle payload).
4. Upload the artifact back to GCS for later reuse by the serving application.
5. Emit a JSON summary to stdout before exiting.

Environment variables (overridable via CLI flags):
- MRCONSO_PATH: input location (local path or gs:// bucket)
- MRCONSO_FORMAT: input format, ``rrf`` (default) or ``terms``
- BKTREE_ARTIFACT_PATH: gs:// destination for the serialized BK-tree
- MAX_TERMS: optional cap to limit the number of terms (testing only)
- JOB_TMP_DIR: optional directory for temporary downloads (defaults to ``/tmp``)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
import tempfile
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple

from google.cloud import storage

# Ensure the repository root is importable when running inside Cloud Run Jobs
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import the shared MRCONSO helpers without triggering FastAPI startup
import app  # type: ignore  # noqa: E402


logger = logging.getLogger("precompute_terms_job")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


def _ensure_local_copy(source: str, tmp_dir: str | None) -> Tuple[str, bool]:
    """Ensure the MRCONSO source is available locally, downloading if needed."""

    if not source.startswith("gs://"):
        logger.info("Using local MRCONSO source at %s", source)
        return source, False

    client = storage.Client()
    bucket_name, blob_name = source.replace("gs://", "", 1).split("/", 1)
    blob = client.bucket(bucket_name).blob(blob_name)

    tmp_dir = tmp_dir or "/tmp"
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="mrconso_", suffix=".rrf", dir=tmp_dir)
    os.close(fd)

    logger.info("Downloading MRCONSO from gs://%s/%s to %s", bucket_name, blob_name, tmp_path)
    download_start = time.time()
    blob.download_to_filename(tmp_path)
    logger.info("Download complete in %.2fs", time.time() - download_start)
    return tmp_path, True


def _build_bktree(local_path: str, source_format: str, max_terms: int) -> Tuple[app.BKTree, int]:
    """Parse MRCONSO and construct a BK-tree in memory."""

    tree = app.BKTree()
    term_count = 0
    app.MRCONSO_FORMAT = source_format.lower()

    logger.info("Building BK-tree from %s (format=%s)", local_path, app.MRCONSO_FORMAT)
    build_start = time.time()

    with open(local_path, "r", encoding="utf-8", errors="ignore") as handle:
        for idx, term in enumerate(app._iter_terms(handle), start=1):
            tree.insert(term)
            term_count = idx
            if max_terms and idx >= max_terms:
                logger.warning("Reached MAX_TERMS=%d; stopping early", max_terms)
                break
            if idx % 500_000 == 0:
                logger.info("Inserted %d terms into BK-tree", idx)

    logger.info("BK-tree build finished in %.2fs (terms=%d)", time.time() - build_start, term_count)
    return tree, term_count


def _serialize_tree(tree: app.BKTree, metadata: dict[str, Any]) -> bytes:
    """Serialize the BK-tree and metadata into a pickle payload."""

    serialize_start = time.time()
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "nodes": tree.to_serializable(),
    }
    blob = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Serialized BK-tree in %.2fs (bytes=%d)", time.time() - serialize_start, len(blob))
    return blob


def _upload_artifact(destination: str, blob: bytes) -> dict[str, Any]:
    """Persist the serialized BK-tree to the requested destination."""

    upload_start = time.time()
    info: dict[str, Any] = {
        "destination": destination,
        "bytes": len(blob),
    }

    if destination.startswith("gs://"):
        client = storage.Client()
        bucket_name, blob_name = destination.replace("gs://", "", 1).split("/", 1)
        bucket = client.bucket(bucket_name)
        artifact = bucket.blob(blob_name)
        logger.info("Uploading BK-tree artifact to gs://%s/%s", bucket_name, blob_name)
        artifact.upload_from_string(blob, content_type="application/octet-stream")
        info["bucket"] = bucket_name
        info["object"] = blob_name
    else:
        dest_path = Path(destination)
        if dest_path.parent:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(blob)
        info["local_path"] = str(dest_path)

    info["upload_seconds"] = round(time.time() - upload_start, 3)
    logger.info("Artifact upload finished in %.2fs", info["upload_seconds"])
    return info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and serialize MRCONSO BK-tree")
    parser.add_argument("--source", default=os.getenv("MRCONSO_PATH"), help="Input MRCONSO path")
    parser.add_argument("--source-format", default=os.getenv("MRCONSO_FORMAT", "rrf"), help="Input format")
    parser.add_argument("--artifact", default=os.getenv("BKTREE_ARTIFACT_PATH"), help="Artifact destination (gs:// or local)")
    parser.add_argument("--max-terms", type=int, default=int(os.getenv("MAX_TERMS", "0") or 0), help="Optional term cap")
    parser.add_argument("--tmp-dir", default=os.getenv("JOB_TMP_DIR"), help="Temporary directory for downloads")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.source:
        logger.error("MRCONSO source path is required")
        sys.exit(2)
    if not args.artifact:
        logger.error("Artifact destination (BKTREE_ARTIFACT_PATH) is required")
        sys.exit(2)

    overall_start = time.time()
    temp_path: str | None = None
    status = 0

    summary: dict[str, Any] = {
        "job": "precompute-mrconso",
        "source": args.source,
        "artifact": args.artifact,
        "max_terms": args.max_terms or None,
    }

    try:
        local_path, should_cleanup = _ensure_local_copy(args.source, args.tmp_dir)
        if should_cleanup:
            temp_path = local_path
        summary["local_source"] = local_path

        tree, term_count = _build_bktree(local_path, args.source_format, args.max_terms)
        summary["term_count"] = term_count

        metadata = {
            "source": args.source,
            "source_format": args.source_format.lower(),
            "max_terms": args.max_terms or None,
            "term_count": term_count,
        }
        artifact_blob = _serialize_tree(tree, metadata)
        summary.update(_upload_artifact(args.artifact, artifact_blob))
        summary["status"] = "success"
    except Exception as exc:  # noqa: BLE001
        logger.exception("BK-tree precomputation failed")
        summary["status"] = "error"
        summary["error"] = str(exc)
        status = 1
    finally:
        summary["elapsed_seconds"] = round(time.time() - overall_start, 3)
        print(json.dumps(summary, sort_keys=True), flush=True)
        if temp_path:
            with suppress(Exception):
                os.remove(temp_path)

    sys.exit(status)


if __name__ == "__main__":
    main()
