#!/usr/bin/env python3
"""
CLI benchmark runner for BK-tree vs Python fuzzy search.
Loads MRCONSO-like terms, builds indices, and compares performance.
"""
import os
import sys
import time
import random
from cppmatch import BKTree
from rapidfuzz.distance import Levenshtein


def load_terms(path):
    """Load terms from MRCONSO-like file."""
    terms = []
    skipped = 0
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '|' in line:
                parts = line.split('|')
                if len(parts) > 14:
                    term = parts[14].strip()
                    if term:
                        terms.append(term)
                else:
                    skipped += 1
            else:
                skipped += 1
    
    print(f"Loaded {len(terms)} terms (skipped {skipped} invalid lines)")
    return terms


def build_bktree(terms):
    """Build BK-tree index."""
    tree = BKTree()
    start = time.time()
    
    for term in terms:
        tree.insert(term)
    
    build_time = time.time() - start
    print(f"BK-tree built in {build_time:.2f} seconds")
    return tree, build_time


def benchmark_bktree(tree, queries, maxdist=1):
    """Benchmark BK-tree search."""
    start = time.time()
    
    for query in queries:
        _ = tree.search(query, maxdist)
    
    elapsed = time.time() - start
    return elapsed


def benchmark_python(terms, queries):
    """Benchmark pure Python search."""
    start = time.time()
    
    for query in queries:
        _ = min(terms, key=lambda t: Levenshtein.distance(query, t))
    
    elapsed = time.time() - start
    return elapsed


def main():
    # Configuration
    terms_path = os.getenv("TERMS_PATH", "data/mrconso_sample.txt")
    num_queries = 100
    maxdist = 1
    
    if not os.path.exists(terms_path):
        print(f"Error: Terms file not found at {terms_path}", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 70)
    print("BK-tree vs Python Fuzzy Search Benchmark")
    print("=" * 70)
    print()
    
    # Load terms
    print(f"Loading terms from {terms_path}...")
    terms = load_terms(terms_path)
    print()
    
    # Build BK-tree
    print("Building BK-tree index...")
    tree, build_time = build_bktree(terms)
    print()
    
    # Sample queries
    queries = random.sample(terms, min(num_queries, len(terms)))
    print(f"Running benchmark with {len(queries)} random queries (maxdist={maxdist})...")
    print()
    
    # Benchmark BK-tree
    print("Benchmarking BK-tree...")
    bkt_time = benchmark_bktree(tree, queries, maxdist)
    bkt_qps = len(queries) / bkt_time
    print(f"  Time: {bkt_time:.3f} seconds")
    print(f"  QPS:  {bkt_qps:.1f}")
    print()
    
    # Benchmark Python
    print("Benchmarking Python baseline...")
    py_time = benchmark_python(terms, queries)
    py_qps = len(queries) / py_time
    print(f"  Time: {py_time:.3f} seconds")
    print(f"  QPS:  {py_qps:.1f}")
    print()
    
    # Results
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Dataset size:          {len(terms):,} terms")
    print(f"BK-tree build time:    {build_time:.2f} seconds")
    print(f"Queries:               {len(queries)}")
    print(f"Max distance:          {maxdist}")
    print()
    print(f"BK-tree time:          {bkt_time:.3f} s  ({bkt_qps:.1f} QPS)")
    print(f"Python time:           {py_time:.3f} s  ({py_qps:.1f} QPS)")
    print(f"Speedup (Python/BK):   {py_time/bkt_time:.2f}×")
    print("=" * 70)


if __name__ == '__main__':
    main()
