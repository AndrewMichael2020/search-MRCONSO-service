#!/usr/bin/env python3
"""
Example usage of the BK-tree search API.
Demonstrates how to call the FastAPI endpoints.
"""
import requests
import json


def main():
    # API base URL (adjust if needed)
    base_url = "http://localhost:8080"
    
    print("=" * 70)
    print("BK-tree Search API Example")
    print("=" * 70)
    print()
    
    # Check health
    print("1. Checking API health...")
    response = requests.get(f"{base_url}/healthz")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    # Search using BK-tree
    print("2. Searching with BK-tree (maxdist=1)...")
    search_req = {
        "query": "carditis",
        "maxdist": 1
    }
    response = requests.post(f"{base_url}/search/bktree", json=search_req)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    # Search using Python baseline
    print("3. Searching with Python baseline...")
    response = requests.post(f"{base_url}/search/python", json=search_req)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    # Run benchmarks
    print("4. Running performance benchmark...")
    response = requests.post(f"{base_url}/benchmarks/run")
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Queries: {result['queries']}")
    print(f"   BK-tree time: {result['bktree_sec']} seconds")
    print(f"   Python time: {result['python_sec']} seconds")
    print(f"   Speedup: {result['ratio_python_over_bktree']}×")
    print()
    
    print("=" * 70)
    print("Example completed successfully!")
    print("=" * 70)


if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API server.")
        print("Make sure the server is running with: uvicorn app:app")
        exit(1)
