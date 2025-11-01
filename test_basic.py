"""
Basic unit tests for BK-tree fuzzy search.
Tests cppmatch module and basic functionality.
"""
import os
import pytest
from cppmatch import BKTree, levenshtein


def test_levenshtein_distance():
    """Test Levenshtein distance calculation."""
    # Classic example
    assert levenshtein('kitten', 'sitting') == 3
    
    # Identical strings
    assert levenshtein('hello', 'hello') == 0
    
    # Empty strings
    assert levenshtein('', 'test') == 4
    assert levenshtein('test', '') == 4
    
    # Single character difference
    assert levenshtein('cat', 'bat') == 1


def test_bktree_exists():
    """Test that BKTree class can be instantiated."""
    tree = BKTree()
    assert tree is not None


def test_bktree_insert_and_search():
    """Test BK-tree insertion and exact search."""
    tree = BKTree()
    
    terms = ['apple', 'apply', 'apricot', 'banana', 'bandana']
    for term in terms:
        tree.insert(term)
    
    # Exact match (distance 0)
    results = tree.search('apple', 0)
    assert len(results) == 1
    assert results[0][0] == 'apple'
    assert results[0][1] == 0


def test_bktree_fuzzy_search():
    """Test BK-tree fuzzy search with distance tolerance."""
    tree = BKTree()
    
    terms = ['apple', 'apply', 'apricot', 'banana', 'bandana']
    for term in terms:
        tree.insert(term)
    
    # Search with distance 1
    results = tree.search('apple', 1)
    # Should find 'apple' (dist=0) and 'apply' (dist=1)
    assert len(results) >= 2
    
    # Results should be sorted by distance
    assert results[0][1] <= results[-1][1]


def test_bktree_no_duplicates():
    """Test that BK-tree doesn't insert duplicates."""
    tree = BKTree()
    
    tree.insert('test')
    tree.insert('test')
    tree.insert('test')
    
    results = tree.search('test', 0)
    assert len(results) == 1


def test_load_sample_data():
    """Test loading MRCONSO-like sample data."""
    # Check if sample file exists
    path = os.getenv("TERMS_PATH", "data/mrconso_sample.txt")
    
    if not os.path.exists(path):
        pytest.skip(f"Sample data not found at {path}")
    
    terms = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '|' in line:
                parts = line.split('|')
                if len(parts) > 14:
                    term = parts[14].strip()
                    if term:
                        terms.append(term)
    
    assert len(terms) > 0, "No terms loaded from sample data"
    
    # Build tree with sample terms
    tree = BKTree()
    for term in terms[:100]:  # Use first 100 for quick test
        tree.insert(term)
    
    # Search for one of the terms
    if terms:
        results = tree.search(terms[0], 1)
        assert len(results) >= 1


def test_bktree_search_returns_sorted():
    """Test that search results are sorted by distance."""
    tree = BKTree()
    
    terms = ['test', 'testing', 'tested', 'tester', 'tests']
    for term in terms:
        tree.insert(term)
    
    results = tree.search('test', 3)
    
    # Check that results are sorted by distance
    for i in range(len(results) - 1):
        assert results[i][1] <= results[i+1][1]
