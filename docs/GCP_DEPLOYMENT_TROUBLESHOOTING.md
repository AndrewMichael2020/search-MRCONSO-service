# GCP Cloud Run Deployment Troubleshooting Guide

## Error: Permission 'iam.serviceAccounts.getAccessToken' denied

### Root Cause
This error occurs when the GitHub Actions workflow attempts to use Workload Identity Federation (WIF) with a service account that lacks the necessary IAM permissions.

### Prerequisites

Before deploying, ensure your GCP service account has these required **IAM roles**:

#### Essential Roles:
1. **`roles/iam.workloadIdentityUser`** - Required for Workload Identity impersonation
2. **`roles/run.admin`** - To deploy services to Cloud Run
3. **`roles/artifactregistry.writer`** - To push Docker images to Artifact Registry
4. **`roles/artifactregistry.reader`** - To pull Docker images from Artifact Registry
5. **`roles/iam.securityAdmin`** - To manage service account permissions
6. **`roles/serviceusage.serviceUsageAdmin`** - To enable required APIs

#### Quick Setup Command

```bash
# Set your variables
export GCP_PROJECT_ID="your-project-id"
export GCP_SA_EMAIL="your-service-account@your-project.iam.gserviceaccount.com"
export GITHUB_REPO_OWNER="your-github-username"
export GITHUB_REPO_NAME="search-MRCONSO-service"

# Grant essential IAM roles
gcloud iam service-accounts add-iam-policy-binding $GCP_SA_EMAIL \
  --project=$GCP_PROJECT_ID \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_ID/locations/global/workloadIdentityPools/*/attribute.repository/$GITHUB_REPO_OWNER/$GITHUB_REPO_NAME"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/artifactregistry.writer

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/serviceusage.serviceUsageAdmin
```

### Verification Steps

#### 1. Check Service Account Roles
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_SA_EMAIL="your-service-account@your-project.iam.gserviceaccount.com"

gcloud iam service-accounts get-iam-policy $GCP_SA_EMAIL \
  --project=$GCP_PROJECT_ID
```

#### 2. Verify Workload Identity Pool
```bash
gcloud iam workload-identity-pools describe "github" \
  --project=$GCP_PROJECT_ID \
  --location=global
```

#### 3. Test Service Account Impersonation Locally
```bash
gcloud iam service-accounts keys create /tmp/sa-key.json \
  --iam-account=$GCP_SA_EMAIL \
  --project=$GCP_PROJECT_ID

export GOOGLE_APPLICATION_CREDENTIALS="/tmp/sa-key.json"

gcloud services list --enabled --project=$GCP_PROJECT_ID
```

#### 4. Verify Artifact Registry Access
```bash
# List repositories
gcloud artifacts repositories list \
  --project=$GCP_PROJECT_ID \
  --location=northamerica-northeast1
```

### GitHub Actions Secrets Configuration

Ensure these secrets are properly configured in your GitHub repository:

1. **`GCP_PROJECT_ID`** - Your GCP project ID
2. **`GCP_SA_EMAIL`** - Service account email
3. **`GCP_WORKLOAD_IDENTITY_PROVIDER`** - Workload Identity Provider resource name
   - Format: `projects/{PROJECT_NUMBER}/locations/global/workloadIdentityPools/{POOL_ID}/providers/{PROVIDER_ID}`
4. **`GCP_ARTIFACT_REPO`** - Full artifact registry path
   - Format: `northamerica-northeast1-docker.pkg.dev/{PROJECT_ID}/{REPO_NAME}`
5. **`SERVICE_NAME`** - Your Cloud Run service name
6. **`GCP_REGION`** - GCP region (e.g., `us-central1`)

### Common Issues & Solutions

#### Issue 1: "Unable to acquire impersonated credentials"
**Solution:** Verify the service account has `roles/iam.workloadIdentityUser` role

#### Issue 2: "Permission denied" for API operations
**Solution:** Grant `roles/serviceusage.serviceUsageAdmin` role

#### Issue 3: "Access Denied" when pushing to Artifact Registry
**Solution:** Grant `roles/artifactregistry.writer` role

#### Issue 4: "Cloud Run API not enabled"
**Solution:** The workflow attempts to enable this automatically, but you can manually enable it:
```bash
gcloud services enable run.googleapis.com --project=$GCP_PROJECT_ID
```

### Debugging in GitHub Actions

The updated workflow now includes a verification step that runs after authentication. Check the step "🔍 Verify authentication and permissions" in your workflow runs to see:
- Active authenticated account
- Whether access tokens can be obtained
- Any specific permission errors

### Complete GCP Setup Script

If you're setting up from scratch:

```bash
#!/bin/bash

# Configuration
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export SERVICE_NAME="search-mrconso"
export SA_NAME="github-actions-deploy"
export ARTIFACT_REPO_NAME="docker-repo"
export GITHUB_REPO_OWNER="your-username"
export GITHUB_REPO_NAME="search-MRCONSO-service"

# 1. Create service account
gcloud iam service-accounts create $SA_NAME \
  --project=$GCP_PROJECT_ID \
  --display-name="GitHub Actions deployment account"

export GCP_SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# 2. Create Artifact Registry repository
gcloud artifacts repositories create $ARTIFACT_REPO_NAME \
  --project=$GCP_PROJECT_ID \
  --repository-format=docker \
  --location=$GCP_REGION

# 3. Grant IAM roles
gcloud iam service-accounts add-iam-policy-binding $GCP_SA_EMAIL \
  --project=$GCP_PROJECT_ID \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_ID/locations/global/workloadIdentityPools/*/attribute.repository/$GITHUB_REPO_OWNER/$GITHUB_REPO_NAME"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/artifactregistry.writer

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/artifactregistry.reader

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/serviceusage.serviceUsageAdmin

# 4. Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=$GCP_PROJECT_ID

# 5. Get the Workload Identity Pool ID (if already created)
# If not, you need to create it via the GCP Console or gcloud commands

echo "✅ Service account created: $GCP_SA_EMAIL"
echo "✅ Use these values in GitHub secrets:"
echo "   GCP_PROJECT_ID: $GCP_PROJECT_ID"
echo "   GCP_SA_EMAIL: $GCP_SA_EMAIL"
echo "   GCP_ARTIFACT_REPO: ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REPO_NAME}"
echo "   SERVICE_NAME: $SERVICE_NAME"
echo "   GCP_REGION: $GCP_REGION"
```

### References

- [Google Cloud Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub Actions with Google Cloud](https://github.com/google-github-actions/auth)
- [Cloud Run Deployment Guide](https://cloud.google.com/run/docs/deploying)
