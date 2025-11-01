# Quick Reference Guide

## Essential Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Build C++ extension
python setup.py build_ext --inplace

# Generate sample data
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 5000

# Run tests
pytest -v
```

### Development
```bash
# Start API server
uvicorn app:app --reload

# Run benchmark
python benchmark.py

# Run example
python examples/benchmark_example.py
```

### API Endpoints

**Health Check**
```bash
curl http://localhost:8000/healthz
```

**BK-tree Search**
```bash
curl -X POST http://localhost:8000/search/bktree \
  -H "Content-Type: application/json" \
  -d '{"query": "carditis", "maxdist": 1}'
```

**Python Search**
```bash
curl -X POST http://localhost:8000/search/python \
  -H "Content-Type: application/json" \
  -d '{"query": "carditis", "maxdist": 1}'
```

**Run Benchmark**
```bash
curl -X POST http://localhost:8000/benchmarks/run
```

### Docker
```bash
# Build
docker build -t bktree-bench .

# Run
docker run -p 8080:8080 bktree-bench

# Test
curl http://localhost:8080/healthz
```

### Cloud Run
```bash
# Deploy
gcloud run deploy bktree-bench \
  --source . \
  --region northamerica-northeast1 \
  --allow-unauthenticated

# Get URL
gcloud run services describe bktree-bench \
  --region northamerica-northeast1 \
  --format 'value(status.url)'
```

## Performance Targets

| Metric | Target | Achieved |
|--------|--------|----------|
| BK-tree build time | ≤ 30s | 0.02s ✅ |
| BK-tree p95 latency | ≤ 200ms | < 1ms ✅ |
| Speedup ratio | ≥ 10× | 13.79× ✅ |

## File Locations

- **Application:** `app.py`
- **C++ Code:** `cppmatch.cpp`
- **Tests:** `test_basic.py`
- **Benchmark:** `benchmark.py`
- **Data:** `data/mrconso_sample.txt`
- **Docs:** `docs/INSTRUCTIONS.md`

## Troubleshooting

**Import Error: cppmatch**
```bash
python setup.py build_ext --inplace
```

**Missing data file**
```bash
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 5000
```

**Tests failing**
```bash
# Regenerate data and rebuild
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 1000
python setup.py build_ext --inplace
pytest -v
```

## Environment Variables

```bash
export TERMS_PATH=data/mrconso_sample.txt
export APP_ENV=dev
export PORT=8080
```

## Links

- [Full Instructions](INSTRUCTIONS.md)
- [Architecture](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [GitHub Repository](https://github.com/AndrewMichael2020/search-MRCONSO-service)
