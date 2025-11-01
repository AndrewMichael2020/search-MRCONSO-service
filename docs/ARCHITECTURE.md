# Architecture

## Overview

The BK-tree search application is a high-performance medical term search system that compares C++ BK-tree implementation against Python baseline for fuzzy string matching on MRCONSO-like medical terminology.

## System Components

### 1. Data Layer

**Input:** MRCONSO-like pipe-delimited files
- Format: 18 fields separated by `|`
- Key field: STR (index 14) - medical term string
- Sample size: 5,000 - 50,000 terms

**Data Generator:** `scripts/make_sample_from_mrconso.py`
- Generates synthetic medical terms
- Extracts from real MRCONSO.RRF (with license)
- Creates valid pipe-delimited format

### 2. Core Search Engine

**C++ BK-tree Implementation** (`cppmatch.cpp`)
```cpp
class BKTree {
    // Levenshtein distance calculation
    int levenshtein(s1, s2)
    
    // Tree operations
    void insert(term)
    vector<pair<string, int>> search(query, maxdist)
}
```

**Features:**
- Efficient distance-based pruning
- O(log n) average search complexity
- Levenshtein edit distance metric
- Sorted results by distance

**Python Baseline**
- Uses `rapidfuzz` library
- Linear scan through all terms
- O(n) search complexity
- Used for performance comparison

### 3. API Layer (FastAPI)

**Endpoints:**

```python
GET  /healthz                    # Health check
POST /search/bktree              # BK-tree search
POST /search/python              # Python baseline search
POST /benchmarks/run             # Performance benchmark
```

**Request/Response Schema:**
```json
{
  "query": "carditis",
  "maxdist": 1
}
→
{
  "matches": [
    {"term": "Carditis", "distance": 0},
    {"term": "Cardiitis", "distance": 1}
  ]
}
```

### 4. Build System

**C++ Extension Build** (`setup.py`)
- Uses pybind11 for Python bindings
- Compiles with `-std=c++11`
- Produces `.so` shared library

**Dependencies** (`requirements.txt`)
- FastAPI - Web framework
- uvicorn - ASGI server
- pybind11 - C++/Python bindings
- rapidfuzz - Python fuzzy matching
- pytest - Testing framework

## Data Flow

```
MRCONSO file → Parser → Terms list
                             ↓
                    ┌────────┴────────┐
                    ↓                 ↓
              BK-tree Index    Python List
                    ↓                 ↓
              Fast Search      Baseline Search
                    ↓                 ↓
              API Response     API Response
```

## Performance Characteristics

### BK-tree
- **Build time:** O(n log n)
- **Search time:** O(log n) average
- **Space complexity:** O(n)
- **Actual performance:** ~10,000 QPS

### Python Baseline
- **Build time:** O(1) - just a list
- **Search time:** O(n)
- **Space complexity:** O(n)
- **Actual performance:** ~700 QPS

### Speedup Factor
- Target: ≥ 10×
- Achieved: 13-14× on 5,000 terms
- Scales with dataset size

## Deployment Architecture

```
GitHub → CI/CD → Container Registry → Cloud Run
  ↓
Code + Tests
  ↓
Docker Build (Multi-stage)
  ↓
C++ Compilation + Runtime
  ↓
HTTPS Endpoint
```

### Container Structure

**Build Stage:**
- Base: python:3.11-slim
- Install: build-essential, python3-dev
- Compile: C++ extension
- Size: ~1.5 GB

**Runtime Stage:**
- Base: python:3.11-slim
- Install: libstdc++6 (C++ runtime)
- Copy: compiled extension + app
- Size: ~400 MB

## Security Architecture

### Data Privacy
- No PHI (Protected Health Information)
- Synthetic or public sample data only
- MRCONSO.RRF excluded from git

### Authentication
- Cloud Run: IAM or unauthenticated (demo)
- CI/CD: GitHub OIDC → GCP Workload Identity
- No long-lived service account keys

### Network
- HTTPS only on Cloud Run
- Health checks on /healthz
- Optional: Cloud Armor for DDoS protection

## Monitoring & Observability

### Metrics
- Request latency (p50, p95, p99)
- Throughput (QPS)
- Error rate
- Memory usage

### Logging
- Application logs (startup, errors)
- Request logs (Cloud Run)
- Benchmark results (structured JSON)

### Health Checks
- `/healthz` endpoint
- Returns: term count, status
- Used by Cloud Run for liveness

## Testing Strategy

### Unit Tests (`test_basic.py`)
- Levenshtein distance calculation
- BK-tree insert/search operations
- Data loading and parsing
- Result sorting and filtering

### Integration Tests
- API endpoint responses
- Benchmark consistency
- Docker container build

### Performance Tests
- Benchmark script
- API benchmark endpoint
- Comparison against baseline

## Scalability Considerations

### Horizontal Scaling
- Cloud Run: Auto-scales instances
- Stateless design
- Concurrent request handling

### Vertical Scaling
- CPU: 1-4 vCPUs on Cloud Run
- Memory: 512Mi - 4Gi
- BK-tree builds once per instance

### Dataset Size
- Tested: 5,000 terms
- Expected: 50,000 - 100,000 terms
- Build time scales linearly
- Search time scales logarithmically

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI | REST endpoints |
| Server | uvicorn | ASGI server |
| Search | C++ (pybind11) | BK-tree implementation |
| Baseline | Python + rapidfuzz | Comparison baseline |
| Container | Docker | Deployment packaging |
| CI/CD | GitHub Actions | Automated testing/deployment |
| Cloud | GCP Cloud Run | Serverless hosting |
| Storage | Artifact Registry | Container images |

## Design Decisions

### Why BK-tree?
- Edit distance-based pruning
- Logarithmic search complexity
- Well-suited for fuzzy matching
- Simpler than alternatives (trie, etc.)

### Why pybind11?
- Modern C++ bindings
- Type conversions handled automatically
- Good performance
- Easy to maintain

### Why FastAPI?
- Modern async framework
- Auto-generated docs
- Type validation with Pydantic
- Easy to test and deploy

### Why Cloud Run?
- Serverless (pay per use)
- Auto-scaling
- C++ runtime support
- Easy CI/CD integration
- Low operational overhead

## Future Enhancements

1. **Caching:** Redis for frequent queries
2. **Batching:** Bulk search endpoint
3. **Pagination:** Large result sets
4. **Fuzzy variants:** Other distance metrics
5. **Monitoring:** Cloud Monitoring integration
6. **A/B testing:** Different algorithms
7. **Multi-index:** Support multiple term files
