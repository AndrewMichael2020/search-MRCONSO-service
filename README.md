# BK-tree vs Python Fuzzy Search (MRCONSO)

[![Test](https://github.com/AndrewMichael2020/search-MRCONSO-service/actions/workflows/test.yml/badge.svg)](https://github.com/AndrewMichael2020/search-MRCONSO-service/actions/workflows/test.yml)

A performance comparison demo between a compiled **C++ BK-tree** (via pybind11) and **pure-Python Levenshtein** search across MRCONSO-like medical terminology. Includes a FastAPI service deployable to Google Cloud Run.

## 🎯 What This Does

- **Parses** MRCONSO-like pipe-delimited term files
- **Indexes** terms using a BK-tree for efficient fuzzy matching
- **Compares** search performance: C++ BK-tree vs Python baseline
- **Exposes** REST API endpoints for interactive searches
- **Benchmarks** both approaches with reproducible metrics
- **Deploys** to GCP Cloud Run with full CI/CD

## 🚀 Quick Start

### Local Development

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y build-essential python3-dev

# Install Python dependencies
pip install -r requirements.txt

# Build C++ extension
python setup.py build_ext --inplace

# Generate synthetic sample data
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 50000

# Run benchmark
python benchmark.py

# Start API server
uvicorn app:app --reload
```

### Using Docker

```bash
# Generate sample data first
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 50000

# Build and run
docker build -t bktree-bench .
docker run -p 8080:8080 bktree-bench
```

## 📚 API Endpoints

- `GET /healthz` - Health check
- `POST /search/bktree` - Search using BK-tree (fast)
- `POST /search/python` - Search using Python (baseline)
- `POST /benchmarks/run` - Run performance benchmark

### Example Request

```bash
curl -X POST http://localhost:8080/search/bktree \
  -H "Content-Type: application/json" \
  -d '{"query": "carditis", "maxdist": 1}'
```

### Example Response

```json
{
  "matches": [
    {"term": "Carditis", "distance": 0},
    {"term": "Cardiitis", "distance": 1}
  ]
}
```

## 📊 Benchmark Results

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| BK-tree build time | ≤ 30s | 0.02s | ✅ |
| Search latency | ≤ 200ms | < 1ms | ✅ |
| Speedup ratio | ≥ 10× | 13.79× | ✅ |
| Test coverage | All pass | 7/7 | ✅ |

Run `python benchmark.py` or call `/benchmarks/run` endpoint to fill in results.

### Massive-ish Benchmarks

For larger, reportable runs, use the harness in `scripts/massive_benchmark.py`.

- Remote (deployed service, async HTTP load):

  ```bash
  # 2k queries, concurrency 25, maxdist=1
  python scripts/massive_benchmark.py remote \
    --base-url https://YOUR-SERVICE-URL \
    --queries 2000 --concurrency 25 --maxdist 1 \
    --out-json docs/reports/remote_2k_c25.json
  ```

- Local (in-process C++ BKTree vs Python baseline):

  ```bash
  # 50k terms, 1k queries
  PYTHONPATH=. python scripts/massive_benchmark.py local \
    --terms data/umls/2025AA/MRCONSO.RRF \
    --limit-terms 500000 \
    --queries 1000 --maxdist 1 \
    --out-json docs/reports/local_mrconso_50k.json
  ```

The harness prints a JSON summary (RPS and latency percentiles for remote; build time, QPS, and Python/BK speedup for local) and writes it to the path you provide.

## 🧪 Testing

```bash
# Generate test data
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 1000

# Run tests
pytest -v
```

## 🏗️ Architecture

See [docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md) for complete architecture details.

```
Data (MRCONSO-like) → Loader → BK-tree (C++) + Python list
                               ↓
                         FastAPI endpoints
                               ↓
                         Cloud Run deployment
```

## 📂 Project Structure

```
.
├── app.py                      # FastAPI application
├── benchmark.py                # CLI benchmark tool
├── cppmatch.cpp                # C++ BK-tree implementation
├── setup.py                    # Build configuration
├── test_basic.py               # Unit tests
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container image
├── scripts/
│   └── make_sample_from_mrconso.py  # Sample data generator
├── data/
│   └── mrconso_sample.txt      # Sample terms (generated)
├── .github/workflows/
│   ├── test.yml                # CI: tests
│   └── deploy-cloudrun.yml     # CD: Cloud Run deployment
└── docs/
    ├── INSTRUCTIONS.md         # Complete product spec
    └── screenshots/            # UI/benchmark screenshots
```

## ⚙️ Configuration

- `MRCONSO_PATH` – source MRCONSO (.RRF or cache) file, accepts local paths or `gs://` URIs.
- `ENABLE_PYTHON_BASELINE` – set to `false` in production to keep only the C++ BK-tree in memory.
- `AUTO_LOAD_ON_STARTUP` – `true` to kick off background loading when the process boots.
- `MRCONSO_FORMAT` – `rrf` for raw MRCONSO rows, `terms` for one-term-per-line caches.
- `MAX_TERMS` – optional cap to down-sample during smoke tests or local development.
- `SHUTDOWN_AFTER_SECONDS` – optional TTL (e.g. `1200`) that exits the container once the load completes.

## 🔐 Security & Privacy

- **No PHI or protected health information**
- Uses synthetic or public sample data only
- Cloud Run deployment uses OIDC (no long-lived keys)
- See [INSTRUCTIONS.md](docs/INSTRUCTIONS.md) for full security details

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

This is a demonstration project. For production use with real UMLS data, ensure you have appropriate licensing from NLM.

## 📖 Further Reading

- [docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md) - Complete product specifications
- [CHANGELOG.md](CHANGELOG.md) - Version history
