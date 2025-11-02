import asyncio
import importlib
import json
import sys
import tarfile
from typing import Dict

import pytest
from fastapi.testclient import TestClient
from cppmatch import BKTree


def _reload_app(monkeypatch: pytest.MonkeyPatch, env: Dict[str, str | None]):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    sys.modules.pop("app", None)
    return importlib.import_module("app")


def _write_terms_cache(path, terms):
    path.write_text("\n".join(terms) + "\n", encoding="utf-8")


def _write_rrf(path, terms):
    rows = []
    for idx, term in enumerate(terms, start=1):
        row = [
            f"C{idx:07d}",
            "ENG",
            "P",
            f"L{idx:07d}",
            "PF",
            f"S{idx:07d}",
            "Y",
            f"A{idx:08d}",
            "",
            "",
            "",
            "SNOMED",
            "PT",
            f"CODE{idx}",
            term,
            "0",
            "N",
            "",
        ]
        rows.append("|".join(row))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _make_bktree_artifact(tmp_dir, terms):
    tree = BKTree()
    for term in terms:
        tree.insert(term)

    bin_path = tmp_dir / "bktree.bin"
    tree.save(str(bin_path))

    metadata = {
        "schema_version": 1,
        "term_count": len(terms),
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    metadata_path = tmp_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    tar_path = tmp_dir / "artifact.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(bin_path, arcname="bktree.bin")
        tar.add(metadata_path, arcname="metadata.json")

    return tar_path, metadata


def test_load_terms_from_artifact(monkeypatch, tmp_path):
    artifact_path, metadata = _make_bktree_artifact(tmp_path, ["Alpha", "Bravo", "Charlie"])

    app_module = _reload_app(
        monkeypatch,
        {
            "BKTREE_ARTIFACT_PATH": str(artifact_path),
            "MRCONSO_PATH": str(tmp_path / "unused.txt"),
            "ENABLE_PYTHON_BASELINE": "1",
            "AUTO_LOAD_ON_STARTUP": "0",
            "SHUTDOWN_AFTER_SECONDS": "0",
        },
    )

    count = app_module.load_terms(force=True)
    assert count == metadata["term_count"] == 3
    assert app_module.TERM_COUNT == 3
    assert app_module.ARTIFACT_METADATA == metadata
    assert app_module.TERMS == []

    with TestClient(app_module.app) as client:
        health = client.get("/healthz")
        payload = health.json()
        assert payload["artifact_loaded"] is True
        assert payload["artifact_term_count"] == 3

        bktree = client.post("/search/bktree", json={"query": "Alpha", "maxdist": 1})
        assert bktree.status_code == 200
        matches = {item["term"] for item in bktree.json()["matches"]}
        assert "Alpha" in matches

        python_baseline = client.post("/search/python", json={"query": "Alpha", "maxdist": 1})
        assert python_baseline.status_code == 503


def test_load_terms_without_baseline(monkeypatch, tmp_path):
    terms_path = tmp_path / "terms.txt"
    _write_terms_cache(terms_path, ["Alpha", "Beta", "Gamma"])

    app_module = _reload_app(
        monkeypatch,
        {
            "MRCONSO_PATH": str(terms_path),
            "MRCONSO_FORMAT": "terms",
            "ENABLE_PYTHON_BASELINE": "0",
            "AUTO_LOAD_ON_STARTUP": "0",
            "SHUTDOWN_AFTER_SECONDS": "0",
        },
    )

    count = app_module.load_terms(force=True)
    assert count == 3
    assert app_module.TERM_COUNT == 3
    assert app_module.ENABLE_PYTHON_BASELINE is False
    assert app_module.TERMS == []

    with TestClient(app_module.app) as client:
        response = client.post("/load")
        assert response.status_code == 200
        payload = response.json()
        assert payload["terms"] == 3
        assert payload["baseline_enabled"] is False

        bktree = client.post("/search/bktree", json={"query": "Alpha", "maxdist": 1})
        assert bktree.status_code == 200
        matches = bktree.json()["matches"]
        assert any(item["term"] == "Alpha" for item in matches)

        python_baseline = client.post("/search/python", json={"query": "Alpha", "maxdist": 1})
        assert python_baseline.status_code == 503


def test_load_terms_with_baseline(monkeypatch, tmp_path):
    rrf_path = tmp_path / "MRCONSO.RRF"
    _write_rrf(rrf_path, ["Delta", "Epsilon"])

    app_module = _reload_app(
        monkeypatch,
        {
            "MRCONSO_PATH": str(rrf_path),
            "MRCONSO_FORMAT": "rrf",
            "ENABLE_PYTHON_BASELINE": "1",
            "AUTO_LOAD_ON_STARTUP": "0",
            "SHUTDOWN_AFTER_SECONDS": "0",
        },
    )

    count = app_module.load_terms(force=True)
    assert count == 2
    assert app_module.LOADING is False
    assert app_module.LOADED is True
    assert app_module.TERMS == ["Delta", "Epsilon"]

    with TestClient(app_module.app) as client:
        search_python = client.post("/search/python", json={"query": "Delta", "maxdist": 1})
        assert search_python.status_code == 200
        assert search_python.json()["matches"][0]["term"] == "Delta"

        search_bktree = client.post("/search/bktree", json={"query": "Epsilon", "maxdist": 2})
        assert search_bktree.status_code == 200
        terms = {item["term"] for item in search_bktree.json()["matches"]}
        assert "Epsilon" in terms


def test_shutdown_timer_reports_health(monkeypatch, tmp_path):
    terms_path = tmp_path / "terms.txt"
    _write_terms_cache(terms_path, ["Zeta"])

    app_module = _reload_app(
        monkeypatch,
        {
            "MRCONSO_PATH": str(terms_path),
            "MRCONSO_FORMAT": "terms",
            "ENABLE_PYTHON_BASELINE": "0",
            "AUTO_LOAD_ON_STARTUP": "0",
            "SHUTDOWN_AFTER_SECONDS": "2",
        },
    )

    called: dict[str, int] = {}

    def fake_exit(code: int):
        called["code"] = code

    async def runner():
        monkeypatch.setattr(app_module.os, "_exit", fake_exit)

        app_module.load_terms(force=True)
        app_module._schedule_shutdown_timer()

        assert app_module._shutdown_task is not None
        await asyncio.sleep(0)

        health = await app_module.health()
        assert health["shutdown_after_seconds"] == 2
        assert health["shutdown_timer_active"] is True

        app_module._shutdown_task.cancel()
        await asyncio.sleep(0)

        health_after = await app_module.health()
        assert health_after["shutdown_timer_active"] is False
        assert called == {}

    asyncio.run(runner())