#!/usr/bin/env python3
"""
Example benchmark usage demonstrating BK-tree vs Python performance.
This can be run directly to see the performance comparison.
"""
import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
from cppmatch import BKTree, levenshtein
from rapidfuzz.distance import Levenshtein


def load_sample_terms(n=10000):
    """Load or generate sample terms."""
    terms_path = "data/mrconso_sample.txt"
    
    if os.path.exists(terms_path):
        print(f"Loading terms from {terms_path}...")
        terms = []
        with open(terms_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) > 14:
                        terms.append(parts[14].strip())
        print(f"Loaded {len(terms)} terms")
        return terms
    else:
        print(f"Sample data not found. Generating {n} synthetic terms...")
        # Simple synthetic terms for demo
        prefixes = ["cardio", "neuro", "gastro", "hepato", "nephro"]
        suffixes = ["itis", "osis", "pathy", "plasty", "ectomy"]
        terms = [f"{p}{s}" for p in prefixes for s in suffixes]
        
        # Expand with variations
        while len(terms) < n:
            base = random.choice(terms[:len(prefixes) * len(suffixes)])
            variation = base + str(random.randint(1, 100))
            terms.append(variation)
        
        return terms[:n]


def main():
    print("=" * 70)
    print("BK-tree vs Python Benchmark Example")
    print("=" * 70)
    print()
    
    # Load terms
    terms = load_sample_terms(10000)
    print()
    
    # Build BK-tree
    print("Building BK-tree...")
    tree = BKTree()
    start = time.time()
    for term in terms:
        tree.insert(term)
    build_time = time.time() - start
    print(f"Built in {build_time:.2f} seconds")
    print()
    
    # Prepare test queries
    num_queries = 100
    queries = random.sample(terms, min(num_queries, len(terms)))
    print(f"Testing with {len(queries)} queries...")
    print()
    
    # Benchmark BK-tree
    print("Benchmarking BK-tree search...")
    start = time.time()
    for query in queries:
        results = tree.search(query, 1)
    bkt_time = time.time() - start
    print(f"  Time: {bkt_time:.3f} seconds")
    print(f"  QPS: {len(queries)/bkt_time:.1f}")
    print()
    
    # Benchmark Python
    print("Benchmarking Python search...")
    start = time.time()
    for query in queries:
        best = min(terms, key=lambda t: Levenshtein.distance(query, t))
    py_time = time.time() - start
    print(f"  Time: {py_time:.3f} seconds")
    print(f"  QPS: {len(queries)/py_time:.1f}")
    print()
    
    # Summary
    speedup = py_time / bkt_time
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Dataset: {len(terms)} terms")
    print(f"Queries: {len(queries)}")
    print(f"BK-tree: {bkt_time:.3f}s ({len(queries)/bkt_time:.1f} QPS)")
    print(f"Python:  {py_time:.3f}s ({len(queries)/py_time:.1f} QPS)")
    print(f"Speedup: {speedup:.2f}×")
    print("=" * 70)
    
    if speedup >= 10:
        print("✓ BK-tree shows ≥10× speedup - excellent!")
    elif speedup >= 5:
        print("✓ BK-tree shows ≥5× speedup - good")
    else:
        print("⚠ Speedup less than 5× - consider dataset size or query complexity")


if __name__ == '__main__':
    main()
