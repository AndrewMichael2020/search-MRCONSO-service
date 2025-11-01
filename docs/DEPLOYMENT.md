# Deployment Guide

This guide covers deploying the BK-tree search application to various environments.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Google Cloud Run](#google-cloud-run)
4. [GitHub Actions CI/CD](#github-actions-cicd)
5. [Environment Variables](#environment-variables)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Local Development

### Prerequisites

- Python 3.11+
- GCC/G++ (for C++ compilation)
- pip

### Setup

```bash
# Clone repository
git clone https://github.com/AndrewMichael2020/search-MRCONSO-service.git
cd search-MRCONSO-service

# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y build-essential python3-dev

# Install Python dependencies
pip install -r requirements.txt

# Build C++ extension
python setup.py build_ext --inplace

# Generate sample data
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 5000

# Run tests
pytest -v

# Start server
uvicorn app:app --reload
```

### Verify Installation

```bash
# Check C++ module
python -c "import cppmatch; print('cppmatch OK')"

# Run benchmark
python benchmark.py

# Test API
curl http://localhost:8000/healthz
```

---

## Docker Deployment

### Build Container

```bash
# Generate sample data first
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 50000

# Build image
docker build -t bktree-bench:latest .

# Run container
docker run -p 8080:8080 bktree-bench:latest
```

### Test Container

```bash
# Health check
curl http://localhost:8080/healthz

# Search test
curl -X POST http://localhost:8080/search/bktree \
  -H "Content-Type: application/json" \
  -d '{"query": "Neuritis", "maxdist": 1}'

# Benchmark
curl -X POST http://localhost:8080/benchmarks/run
```

### Multi-stage Build Details

The Dockerfile uses a multi-stage build:

**Build Stage:**
- Compiles C++ extension
- Installs build tools
- ~1.5 GB

**Runtime Stage:**
- Minimal runtime dependencies
- Copies compiled artifacts
- ~400 MB final image

---

## Google Cloud Run

### Prerequisites

- GCP Project with billing enabled
- gcloud CLI installed and configured
- Artifact Registry repository created

### One-Time Setup

```bash
# Set variables
export PROJECT_ID=your-project-id
export REGION=northamerica-northeast1
export SERVICE_NAME=bktree-bench

# Configure gcloud
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create containers \
  --repository-format=docker \
  --location=$REGION \
  --description="Container images"
```

### Manual Deployment

```bash
# Build and push image
gcloud builds submit \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/containers/$SERVICE_NAME:latest

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/containers/$SERVICE_NAME:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars TERMS_PATH=data/mrconso_sample.txt,APP_ENV=prod
```

### Get Service URL

```bash
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format 'value(status.url)'
```

### Test Deployment

```bash
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

# Health check
curl $SERVICE_URL/healthz

# Search test
curl -X POST $SERVICE_URL/search/bktree \
  -H "Content-Type: application/json" \
  -d '{"query": "Carditis", "maxdist": 1}'
```

### Configure Authentication (Optional)

```bash
# Restrict to authenticated users
gcloud run services remove-iam-policy-binding $SERVICE_NAME \
  --region $REGION \
  --member "allUsers" \
  --role "roles/run.invoker"

# Grant access to specific user
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --region $REGION \
  --member "user:email@example.com" \
  --role "roles/run.invoker"
```

---

## GitHub Actions CI/CD

### Setup Workload Identity Federation

This allows GitHub Actions to authenticate to GCP without service account keys.

```bash
# Create Workload Identity Pool
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions Pool"

# Create Provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --workload-identity-pool=github-pool \
  --location=global \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='AndrewMichael2020/search-MRCONSO-service'"

# Create Service Account
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Bind Workload Identity
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/AndrewMichael2020/search-MRCONSO-service"
```

**Note:** Replace `PROJECT_NUMBER` with your actual GCP project number, which you can get with:
```bash
gcloud projects describe $PROJECT_ID --format='value(projectNumber)'
```

**Important:** The workflow uses Application Default Credentials (ADC) for authentication. If you need to use explicit access tokens (by adding `token_format: access_token` to the auth step), you must also grant the service account permission to impersonate itself:

```bash
# Only needed if using token_format: access_token
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="serviceAccount:github-actions-sa@$PROJECT_ID.iam.gserviceaccount.com"
```

### Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `GCP_PROJECT`: Your GCP project ID
- `GCP_REGION`: Deployment region (e.g., `northamerica-northeast1`)
- `GCP_ARTIFACT_REGION`: Artifact Registry region
- `GCP_SA_EMAIL`: Service account email (`github-actions-sa@PROJECT_ID.iam.gserviceaccount.com`)
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: Full provider resource name

### Trigger Deployment

Deployment is triggered automatically on:
- Push to `main` branch
- Changes to: Dockerfile, app.py, cppmatch.cpp, requirements.txt, setup.py
- Manual workflow dispatch

```bash
# Manual trigger via GitHub CLI
gh workflow run deploy-cloudrun.yml
```

### View Deployment Status

```bash
# Via GitHub CLI
gh run list --workflow=deploy-cloudrun.yml

# Via web
# https://github.com/AndrewMichael2020/search-MRCONSO-service/actions
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMS_PATH` | `data/mrconso_sample.txt` | Path to terms file |
| `APP_ENV` | `dev` | Environment (dev/staging/prod) |
| `PORT` | `8080` | Server port |

### Setting in Cloud Run

```bash
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars TERMS_PATH=data/custom_terms.txt,APP_ENV=prod
```

---

## Monitoring

### Cloud Run Metrics

View in GCP Console:
- Cloud Run → Services → bktree-bench → Metrics

Key metrics:
- Request count
- Request latency
- Instance count
- CPU utilization
- Memory utilization

### Logs

```bash
# View recent logs
gcloud run services logs read $SERVICE_NAME \
  --region $REGION \
  --limit 50

# Stream logs
gcloud run services logs tail $SERVICE_NAME \
  --region $REGION
```

### Custom Monitoring

Create log-based metric for benchmark results:

```bash
gcloud logging metrics create benchmark_latency \
  --description="BK-tree search latency from benchmarks" \
  --log-filter='resource.type="cloud_run_revision"
    jsonPayload.bktree_sec>0'
```

---

## Troubleshooting

### Build Failures

**Problem:** C++ compilation errors

```bash
# Check compiler version
gcc --version

# Install build dependencies
sudo apt-get install -y build-essential python3-dev

# Clean and rebuild
rm -rf build *.so
python setup.py build_ext --inplace
```

**Problem:** pybind11 not found

```bash
# Reinstall pybind11
pip install --upgrade pybind11
```

### Runtime Errors

**Problem:** `ImportError: cppmatch`

```bash
# Verify .so file exists
ls -l *.so

# Check Python can load it
python -c "import cppmatch"
```

**Problem:** Terms file not found

```bash
# Check file exists
ls -l data/mrconso_sample.txt

# Generate if missing
python scripts/make_sample_from_mrconso.py --out data/mrconso_sample.txt --n 5000
```

### Cloud Run Issues

**Problem:** Container fails to start

```bash
# Check logs
gcloud run services logs read $SERVICE_NAME --region $REGION --limit 100

# Common issues:
# - Missing data file → include in Docker image
# - Port mismatch → ensure PORT=8080
# - Memory limit → increase to 512Mi or 1Gi
```

**Problem:** High latency

```bash
# Increase CPU
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --cpu 2

# Increase memory
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --memory 1Gi
```

### Performance Issues

**Problem:** Slow BK-tree build

- Reduce dataset size
- Build once per container, not per request
- Use startup event in FastAPI

**Problem:** High search latency

- Reduce `maxdist` parameter
- Optimize term file parsing
- Consider caching frequent queries

---

## Security Considerations

### Production Checklist

- [ ] Enable authentication (remove `--allow-unauthenticated`)
- [ ] Use HTTPS only (automatic on Cloud Run)
- [ ] Rotate service account keys (use OIDC instead)
- [ ] Enable Cloud Armor for DDoS protection
- [ ] Set up VPC connector for private access
- [ ] Configure secrets in Secret Manager (not env vars)
- [ ] Enable audit logging
- [ ] Set up alerting for errors and latency

### Data Privacy

- Never commit MRCONSO.RRF files (requires UMLS license)
- Use synthetic data for testing
- No PHI in logs or error messages
- Comply with HIPAA if handling real medical data

---

## Cost Optimization

### Cloud Run Pricing (Approximate)

- Free tier: 2M requests/month
- Beyond free: ~$0.40 per 1M requests
- CPU: $0.00002400/vCPU-second
- Memory: $0.00000250/GiB-second
- Idle instances: No charge with min=0

### Tips

- Set `--min-instances=0` for dev/staging
- Set `--max-instances=10` to prevent runaway costs
- Use `--concurrency=80` for optimal resource use
- Monitor with budget alerts

---

## Next Steps

1. **Production Setup**: Configure authentication and monitoring
2. **Data Integration**: Upload real MRCONSO data (with license)
3. **Performance Tuning**: Optimize for your dataset size
4. **Custom Metrics**: Set up dashboards and alerts
5. **Backup**: Implement data backup strategy
6. **Documentation**: Update with your specific configuration

---

## Support

- Documentation: See [INSTRUCTIONS.md](INSTRUCTIONS.md)
- Architecture: See [ARCHITECTURE.md](ARCHITECTURE.md)
- Issues: https://github.com/AndrewMichael2020/search-MRCONSO-service/issues
