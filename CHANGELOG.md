# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-01

### Added
- Initial implementation of BK-tree fuzzy search in C++ with pybind11
- FastAPI REST API with endpoints for search and benchmarking
- CLI benchmark tool for performance comparison
- Synthetic MRCONSO sample data generator
- Unit tests with pytest
- Docker container for Cloud Run deployment
- CI/CD workflows for GitHub Actions
- Comprehensive documentation and instructions

### Features
- BK-tree implementation with Levenshtein distance
- `/healthz` health check endpoint
- `/search/bktree` endpoint for fast C++ BK-tree search
- `/search/python` endpoint for Python baseline search
- `/benchmarks/run` endpoint for performance testing
- Support for MRCONSO.RRF pipe-delimited format (column 14)
- Configurable search distance tolerance

### Documentation
- Complete product instructions (docs/INSTRUCTIONS.md)
- README with quick start guide
- Architecture overview
- API documentation and examples
