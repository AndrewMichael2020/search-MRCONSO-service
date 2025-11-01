# Screenshots

This directory contains screenshots and output examples demonstrating the BK-tree search application.

## Files

### ui.txt
Example API request/response showing the BK-tree search endpoint in action.

### bench.txt
Complete output from the CLI benchmark showing performance comparison between BK-tree and Python baseline.

### logs.txt
Example output from the `/benchmarks/run` API endpoint showing performance metrics.

### cloudrun.txt
Mock deployment information for Google Cloud Run, showing what a production deployment would look like.

## Actual Screenshots

When deploying to production or demonstrating the application, capture these screenshots:

1. **API Usage (ui.png)**
   - Use Postman or similar tool
   - Make POST request to `/search/bktree`
   - Show request body and JSON response

2. **Benchmark Results (bench.png)**
   - Run `python benchmark.py`
   - Capture terminal output showing speedup metrics

3. **Cloud Run Dashboard (cloudrun.png)**
   - Navigate to Cloud Run console
   - Show service details page with URL
   - Display health status and recent deployments

4. **Logs Explorer (logs.png)**
   - Open GCP Logs Explorer
   - Filter for benchmark results
   - Show structured JSON log entries

## Generating Screenshots

### Local API Screenshot

```bash
# Start server
uvicorn app:app

# In another terminal, make request and save output
curl -X POST http://localhost:8000/search/bktree \
  -H "Content-Type: application/json" \
  -d '{"query": "Neuritis", "maxdist": 2}' | jq '.'

# Use screenshot tool (Postman, Insomnia, or terminal screenshot)
```

### Benchmark Screenshot

```bash
# Run benchmark and capture output
python benchmark.py > benchmark_output.txt

# Or screenshot terminal directly
```

### Cloud Run Screenshots

1. Deploy to Cloud Run following [DEPLOYMENT.md](../DEPLOYMENT.md)
2. Navigate to Cloud Run console: https://console.cloud.google.com/run
3. Click on service name
4. Screenshot the overview page
5. Click "Logs" tab and screenshot log entries

## Screenshot Specifications

For consistency, screenshots should:
- Be in PNG format (lossless)
- Include timestamps when relevant
- Show request/response headers
- Highlight key metrics or values
- Use readable font sizes (≥ 12pt)
- Include terminal prompts for CLI examples

## Note

The `.txt` files in this directory serve as placeholders and documentation until actual screenshots are captured. They contain the same information that would appear in real screenshots.
