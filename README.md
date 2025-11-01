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

| Metric | Target | Result |
|--------|--------|--------|
| BK-tree build time | ≤ 30s | _(run benchmark)_ |
| BK-tree p95 latency | ≤ 200ms | _(run benchmark)_ |
| Python baseline | - | _(run benchmark)_ |
| Speedup ratio | ≥ 10× | _(run benchmark)_ |

Run `python benchmark.py` or call `/benchmarks/run` endpoint to fill in results.

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
