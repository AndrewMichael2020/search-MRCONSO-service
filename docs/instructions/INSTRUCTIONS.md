# BK-tree vs Python Fuzzy Search (MRCONSO) — **Product-Ready Instructions**

**Status:** Beta · **Scope:** Capability demo (search structure & benchmarking) · **Data:** MRCONSO-like terms (no PHI) · **Target runtime:** GitHub Codespaces + GCP Cloud Run

> This file is intentionally complete so you can copy the repo skeleton, run locally/Codespaces, and deploy an API to **Cloud Run**. It includes architecture, contracts, tests, CI/CD, security, SLOs, metrics, cost notes, and screenshot placeholders.

---

## 0) What this is (and is not)
**Goal:** Compare search speed and ergonomics between a compiled **C++ BK-tree** (via pybind11) and a **pure‑Python Levenshtein** baseline across MRCONSO-like medical terms; expose both via a tiny API for interactive checks; record repeatable benchmarks.

**Non‑goals:** Production terminology governance, licensing automation, or clinical accuracy evaluation.

---

## 1) Architecture (high level)
```mermaid
flowchart LR
  A[MRCONSO-like terms
(data/mrconso_sample.txt)] --> B[Loader]
  B --> C{{BK-tree index
(C++/pybind11)}}
  B --> D[Python list]
  E[FastAPI app] -->|/search/bktree| C
  E -->|/search/python| D
  E -->|/benchmarks/run| C & D
  E --> F[Cloud Run]
```

**Insert screenshot placeholders:**
- `docs/screenshot_ui.png` — simple curl/Postman result for `/search/bktree`.
- `docs/screenshot_bench.png` — printed benchmark table.

---

## 2) Data contract & lineage
- **Input file:** pipe‑delimited text mimicking `MRCONSO.RRF`. We only need the **STR** column (index **14**) for terms.
- **Contract:** each line must contain at least 15 fields separated by `|`. Field 14 (0‑based) is extracted as the term.
- **Validation rule:** skip lines with `<15` fields; count and report skips.

**Files:**
- `data/mrconso_sample.txt` — demo sample (synthetic or public sample). 
- If you possess a UMLS license, place `MRCONSO.RRF` under `data/` and run the included slice script.

> **Note on wget**: There is **no stable public MRCONSO direct download without a UMLS license**. If you have a license, download via the NLM portal and upload to Codespaces. For quick starts, we also include a synthetic sample generator.

---

## 3) Project layout (copy/paste skeleton)
```
.
├── app.py                      # FastAPI endpoints (search & benchmark)
├── benchmark.py                # CLI benchmark runner
├── cppmatch.cpp                # pybind11 BK-tree implementation
├── setup.py                    # build config for cppmatch
├── requirements.txt
├── test_basic.py               # unit tests
├── scripts/
│   └── make_sample_from_mrconso.py
├── data/
│   ├── mrconso_sample.txt      # demo dataset (provided or generated)
│   └── README.md               # data notes
├── Dockerfile
├── .github/workflows/
│   ├── test.yml                # CI: build & tests
│   └── deploy-cloudrun.yml     # CD: optional OIDC deploy
├── .env.example
├── CHANGELOG.md
├── LICENSE
└── README.md                   # public-facing readme (short)
```

---

## 4) Environment — local & Codespaces
**Codespaces works for C++ builds and timing tests.**

```bash
# Dev tools
sudo apt update && sudo apt install -y build-essential python3-dev

# Python deps
pip install -r requirements.txt

# Build C++ extension
python setup.py build_ext --inplace

# Quick check
python -c "import cppmatch; print('cppmatch OK')"
```

`requirements.txt`:
```
fastapi
uvicorn
pybind11
rapidfuzz
pandas
pytest
python-dotenv
```

**Synthetic sample (if you lack MRCONSO):**
```bash
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 50000
```

**If you have licensed MRCONSO:** upload `MRCONSO.RRF` into `data/` and run:
```bash
python scripts/make_sample_from_mrconso.py --mrconso data/MRCONSO.RRF --out data/mrconso_sample.txt --n 50000
```

---

## 5) Core code (summaries)

### `cppmatch.cpp` (BK-tree; exposed via pybind11)
- Exposes `levenshtein(s1, s2)`, `BKTree.insert(term)`, `BKTree.search(query, maxdist)`.
- Implements distance‑band pruning: for a query distance `d`, traverse children with edges in `[d-k, d+k]`.

### `benchmark.py` (CLI)
- Loads `data/mrconso_sample.txt` → terms.
- Builds `BKTree` and a Python list.
- Samples 100 queries and times both strategies.
- Prints: runtime (s), queries/s, and ratio.

### `app.py` (API)
- `GET /healthz` → `{status: ok}`
- `POST /search/bktree` → `{matches:[{term, distance}]}`
- `POST /search/python` → same shape
- `POST /benchmarks/run` → returns JSON metrics for both paths on a fixed 100‑query set

> Insert **screenshot** of a Postman/curl call to `/search/bktree`: `docs/screenshot_ui.png`.

---

## 6) Tests (minimal but meaningful)
`test_basic.py`:
- imports `cppmatch` and asserts `BKTree` exists
- asserts `levenshtein('kitten','sitting') == 3`
- loads tiny `data/mrconso_sample.txt` (100 lines) and verifies:
  - search returns at least 1 match within distance 1 for an exact term
  - benchmark returns JSON with required keys

Run:
```bash
pytest -q
```

---

## 7) CI & CD

### CI (build + tests): `.github/workflows/test.yml`
```yaml
name: test
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt update && sudo apt install -y build-essential python3-dev
      - run: pip install -r requirements.txt
      - run: python setup.py build_ext --inplace
      - run: pytest -q
```

### CD to Cloud Run (OIDC, no long‑lived key): `.github/workflows/deploy-cloudrun.yml`
> Requires: GCP project, Artifact Registry repo, Workload Identity Federation with GitHub OIDC, and a Cloud Run service.
```yaml
name: deploy-cloudrun
on:
  workflow_dispatch: {}
  push:
    branches: [ main ]
    paths: [ 'Dockerfile', 'app.py', 'cppmatch.cpp', 'requirements.txt' ]
jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          token_format: access_token
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SA_EMAIL }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud --quiet auth configure-docker ${{ secrets.GCP_ARTIFACT_REGION }}-docker.pkg.dev
      - run: |
          IMAGE=${{ secrets.GCP_ARTIFACT_REGION }}-docker.pkg.dev/${{ secrets.GCP_PROJECT }}/containers/bktree-bench:$(git rev-parse --short HEAD)
          docker build -t $IMAGE .
          docker push $IMAGE
          gcloud run deploy bktree-bench \
            --image $IMAGE \
            --region=${{ secrets.GCP_REGION }} \
            --platform=managed \
            --allow-unauthenticated \
            --set-env-vars APP_ENV=prod
```

---

## 8) Dockerfile (Cloud Run compatible with C++)
```dockerfile
# Build stage
FROM python:3.11-slim as build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY cppmatch.cpp setup.py ./
RUN python setup.py build_ext --inplace
COPY . .

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app /app
ENV PORT=8080
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8080"]
```

---

## 9) FastAPI app (API surface)
```python
# app.py
import os, random, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein

app = FastAPI(title="BKTree vs Python Search")
TERMS = []
TREE = BKTree()

class SearchReq(BaseModel):
    query: str
    maxdist: int = 1

@app.on_event("startup")
async def startup():
    path = os.getenv("TERMS_PATH", "data/mrconso_sample.txt")
    if not os.path.exists(path):
        raise RuntimeError(f"Terms file missing: {path}")
    with open(path, "r", encoding="utf8") as f:
        for line in f:
            if '|' in line:
                parts = line.split('|')
                if len(parts) > 14:
                    TERMS.append(parts[14].strip())
    for t in TERMS:
        TREE.insert(t)

@app.get("/healthz")
async def health():
    return {"status":"ok","terms":len(TERMS)}

@app.post("/search/bktree")
async def search_bktree(req: SearchReq):
    res = TREE.search(req.query, req.maxdist)
    return {"matches": [{"term": t, "distance": d} for t,d in res]}

@app.post("/search/python")
async def search_python(req: SearchReq):
    if not TERMS:
        raise HTTPException(500, "Terms not loaded")
    # naive: best distance only (for parity keep top1)
    best = min(TERMS, key=lambda t: Levenshtein.distance(req.query, t))
    return {"matches": [{"term": best, "distance": int(Levenshtein.distance(req.query, best))}]}

@app.post("/benchmarks/run")
async def run_benchmarks():
    import time
    sample = random.sample(TERMS, min(100, len(TERMS)))
    t0 = time.time();
    for q in sample: TREE.search(q, 1)
    bkt = time.time()-t0
    t0 = time.time();
    for q in sample:
        _ = min(TERMS, key=lambda t: Levenshtein.distance(q, t))
    py = time.time()-t0
    return {"queries": len(sample), "bktree_sec": round(bkt,3), "python_sec": round(py,3), "ratio_python_over_bktree": round(py/max(bkt,1e-9),2)}
```

---

## 10) GCP: deploy to Cloud Run
Prereqs (one‑time):
```bash
PROJECT=your-project
REGION=northamerica-northeast1 # or your region
SERVICE=bktree-bench

gcloud auth login
gcloud config set project $PROJECT

# Artifact Registry (optional if you use gcloud builds directly)
gcloud artifacts repositories create containers --repository-format=docker --location=$REGION || true

# Build and deploy
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/containers/$SERVICE:latest .

gcloud run deploy $SERVICE \
  --image $REGION-docker.pkg.dev/$PROJECT/containers/$SERVICE:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars TERMS_PATH=data/mrconso_sample.txt
```

> **Insert screenshot**: Cloud Run service details page showing URL and healthy revision: `docs/screenshot_cloudrun.png`.

---

## 11) Observability & SLOs
- **Logs:** Cloud Run request logs + app logs (benchmark JSON printed by `/benchmarks/run`).
- **SLOs (beta):** p95 latency ≤ 200 ms for `/search/bktree` on single query; error rate < 0.1%.
- **Dashboards:** Optional — create a log‑based metric on latency and a basic dashboard. 

**Insert screenshot** of one successful `/benchmarks/run` JSON in Logs Explorer: `docs/screenshot_logs.png`.

---

## 12) Security, privacy, and compliance
- **No PHI**, no identifiers. Use synthetic or public samples.
- Default Cloud Run is internet‑exposed; restrict with IAP or Auth if needed.
- Prefer **GitHub OIDC → GCP Workload Identity Federation** for CI/CD (no long‑lived keys).
- Principle of least privilege for the deploy SA: `roles/run.admin`, `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser`.

---

## 13) Metrics table (fill during first run)
| Metric | Unit | Definition | Target | Result |
|---|---|---|---|---|
| Build time (ext) | s | `python setup.py build_ext` | ≤ 30 |  |
| BK-tree p95 | ms | `/search/bktree` single‑term | ≤ 200 |  |
| Python p95 | ms | `/search/python` single‑term | — |  |
| Benchmark ratio | × | Python/BK‑tree on 100 queries | ≥ 10× |  |
| Memory peak | MB | During index build | ≤ 150 |  |
| Cost (CAD) | $/mo | Cloud Run min 0, on‑demand small | ~0–few |  |

---

## 14) Cost note (CAD)
- **Codespaces:** $0 on free tier; paid tiers vary by core/hour.
- **Cloud Run:** Idle $0 at min instances=0; request‑driven costs negligible for this demo. Add egress if external clients stream large responses.

---

## 15) Runbook (incidents & recovery)
- **Symptom:** `ImportError: cppmatch` → **Fix:** rebuild extension: `python setup.py build_ext --inplace`.
- **Symptom:** `/healthz` shows few terms → **Fix:** confirm `TERMS_PATH` and file has ≥15 fields per line.
- **Symptom:** High latency → **Fix:** reduce `maxdist` to 1; lower dataset size; scale Cloud Run CPU to 2.
- **Backup:** Keep `data/mrconso_sample.txt` in repo (small); redeploy via `gcloud run deploy`.

---

## 16) README (public) — outline
Keep it short: purpose, quick start, API endpoints, screenshot links, metrics table snapshot, license.

---

## 17) CHANGELOG & versioning
`CHANGELOG.md` (start):
```
## v0.1.0 (YYYY‑MM‑DD)
- First public beta: BK‑tree vs Python benchmarks; FastAPI endpoints; Cloud Run deploy.
```
Tag the repo: `git tag v0.1.0 && git push --tags`.

---

## 18) Decision framing (stop / pilot / expand)
- **Stop** if BK-tree advantage < 5× on 100 queries.
- **Pilot (2 weeks)** if ≥ 10× and memory ≤ 150 MB.
- **Expand (6 weeks)** if pilot holds at ≥ 10× and code owners want API hardening.

---

## 19) Where to place screenshots
- `docs/screenshot_ui.png` — result from `/search/bktree` (Postman or curl output).
- `docs/screenshot_bench.png` — terminal output of `python benchmark.py` or `/benchmarks/run` JSON.
- `docs/screenshot_cloudrun.png` — Cloud Run service page.
- `docs/screenshot_logs.png` — Logs Explorer showing benchmark results.

---

## 20) License
Include `LICENSE` (MIT). Mention in README footer.

---

## 21) FAQ
- **Can I run tests in Codespaces?** Yes. `pytest -q` is part of CI and runs locally.
- **Why not a fuzzy trie?** BK-tree is simpler to ship and prunes search by edit distance efficiently.
- **Why no real MRCONSO wget?** UMLS requires a license; we avoid embedding credentials. Use the NLM portal, then upload into Codespaces. The sample generator lets you proceed immediately.

