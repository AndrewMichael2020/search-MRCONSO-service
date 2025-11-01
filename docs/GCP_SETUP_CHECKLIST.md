# Quick GCP Setup Checklist

Use this checklist to verify your GCP setup is complete.

## ✅ Prerequisites

- [ ] GCP Project created
- [ ] Service account created
- [ ] Workload Identity Pool configured in GCP
- [ ] GitHub repository secrets configured

## ✅ Required IAM Roles

For service account `your-sa@your-project.iam.gserviceaccount.com`:

```bash
# Copy and run these commands:
export GCP_SA_EMAIL="your-sa@your-project.iam.gserviceaccount.com"
export GCP_PROJECT_ID="your-project-id"

# Grant essential roles
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

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:$GCP_SA_EMAIL \
  --role=roles/iam.securityAdmin
```

- [ ] `roles/run.admin`
- [ ] `roles/artifactregistry.writer`
- [ ] `roles/artifactregistry.reader`
- [ ] `roles/serviceusage.serviceUsageAdmin`
- [ ] `roles/iam.workloadIdentityUser` (via Workload Identity binding)

## ✅ GitHub Secrets Configuration

Set these in your GitHub repository (Settings → Secrets and variables → Actions):

- [ ] `GCP_PROJECT_ID` - Your GCP project ID
- [ ] `GCP_SA_EMAIL` - Service account email (e.g., `sa-name@project.iam.gserviceaccount.com`)
- [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER` - Full resource name of WIP
- [ ] `GCP_ARTIFACT_REPO` - Artifact Registry path (e.g., `us-central1-docker.pkg.dev/project-id/repo-name`)
- [ ] `SERVICE_NAME` - Cloud Run service name
- [ ] `GCP_REGION` - GCP region (e.g., `us-central1`)
- [ ] `GCP_LOG_LEVEL` - (Optional, default: INFO)
- [ ] `DEPLOY_ENV` - (Optional, default: prod)

## ✅ APIs Enabled in GCP

- [ ] Cloud Run API
- [ ] Artifact Registry API
- [ ] IAM Credentials API
- [ ] Cloud Resource Manager API
- [ ] Service Usage API

Enable them with:
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  --project=$GCP_PROJECT_ID
```

## ✅ Artifact Registry Setup

- [ ] Docker repository created in correct region
- [ ] Service account has read/write permissions

```bash
gcloud artifacts repositories create docker-repo \
  --repository-format=docker \
  --location=us-central1 \
  --project=$GCP_PROJECT_ID
```

## ✅ Workflow Verification

After updating the workflow:

1. Push changes to GitHub
2. Trigger a deployment (push to main or manually trigger workflow)
3. Check the "🔍 Verify authentication and permissions" step in the GitHub Actions log
4. Verify the service URL is printed at the end

## 🆘 If It Still Fails

1. Check the step "🔍 Verify authentication and permissions" output
2. Verify service account has all required roles:
   ```bash
   gcloud iam service-accounts get-iam-policy $GCP_SA_EMAIL --project=$GCP_PROJECT_ID
   ```
3. See `docs/GCP_DEPLOYMENT_TROUBLESHOOTING.md` for detailed diagnostics
