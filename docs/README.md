# Documentation Structure

## `/docs/instructions/`
Contains guides, documentation, and setup instructions. These files contain no sensitive information and are safe to commit.

### Files:
- **INSTRUCTIONS.md** - Complete product specifications and architecture
- **QUICKSTART.md** - Quick start guide for running the application locally
- **ARCHITECTURE.md** - System architecture overview
- **DEPLOYMENT.md** - Deployment guide and reference
- **DEPLOYMENT_FIX.md** - Details about workflow fixes applied
- **GCP_SETUP_CHECKLIST.md** - Checklist for verifying GCP setup
- **GCP_DEPLOYMENT_TROUBLESHOOTING.md** - Comprehensive troubleshooting guide

## `/docs/reports/`
Contains deployment-specific reports with configuration values and secrets. **This directory is NOT committed** to prevent exposing sensitive information.

### Files (examples, not committed):
- **DEPLOYMENT_READY.md** - Configuration summary with GitHub secret values
- **AUTHENTICATION_FIX_SUMMARY.md** - Fix summary with service account details

### How to Use Reports:
1. Generate reports locally during setup
2. Use for reference during deployment
3. Never commit these files to version control
4. Create new reports as needed for your environment

### Why Reports Are Ignored:
Reports contain:
- GitHub Actions secret values (GCP_PROJECT_ID, GCP_SA_EMAIL, etc.)
- Service account information
- Project-specific deployment details
- Credentials and authentication configuration

These should never be committed to prevent accidental exposure of sensitive data.

## Adding New Documentation

- **Generic guides/instructions** → `/docs/instructions/`
  - Commit to version control
  - Don't include specific values or secrets
  
- **Environment-specific reports** → `/docs/reports/`
  - Don't commit
  - Include specific values for your deployment
  - Use for reference only
