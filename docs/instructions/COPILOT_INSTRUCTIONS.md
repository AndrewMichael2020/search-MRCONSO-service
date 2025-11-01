# 🤖 Special Instructions for GitHub Copilot / AI Assistants

## 🔐 CRITICAL: Never Expose Secrets

- **NEVER** commit files in `docs/reports/` to git - this directory contains GCP credentials, deployment-specific values, and sensitive configuration
- Check `.gitignore` - if it says `docs/reports/*` with `!docs/reports/.gitkeep`, files there are intentionally NOT committed
- When creating files with environment-specific values (project IDs, service account emails, regions), put them in `docs/reports/`
- When creating generic documentation, put it in `docs/instructions/`

### Files to NEVER commit:
```
docs/reports/AUTHENTICATION_FIX_SUMMARY.md
docs/reports/DEPLOYMENT_READY.md
docs/reports/GCP_SETUP_CHECKLIST.md
docs/reports/GCP_DEPLOYMENT_TROUBLESHOOTING.md
docs/reports/DEPLOYMENT_FIX.md
```

## 💰 Avoid Wasting Commits

- **Each commit should represent a logical unit of work**, not intermediate debugging steps
- **Batch related changes** (e.g., all documentation updates, all IAM fixes) into a single commit
- **Do NOT commit:**
  - Temporary test files or debug scripts
  - Status check outputs or verification logs
  - Intermediate documentation while troubleshooting
- **Only commit when the fix is actually complete and tested**, not just when a step is done

### Commit Discipline:
1. Plan the complete fix before making any commits
2. Make changes locally first
3. Verify the fix actually works
4. Then commit once with a clear message explaining what was fixed and why
5. Use `git log --oneline` to verify commit history is clean

## 🚀 Real Problem-Solving Workflow

When an issue is reported:
1. **Diagnose thoroughly** - understand the root cause, don't just patch symptoms
2. **Verify the fix works** - test locally or request the user test it before committing
3. **Document the fix** - explain WHY it was broken and HOW it was fixed
4. **One commit per logical fix** - not per debugging attempt

## 📋 Current Project Context

- **Project**: search-MRCONSO-service
- **Auth Method**: Workload Identity Federation (OIDC from GitHub to GCP)
- **Service Account**: gh-deployer@agents-mcp-training.iam.gserviceaccount.com
- **Repository**: AndrewMichael2020/search-MRCONSO-service
- **Issue Being Fixed**: GitHub Actions failing with "Permission 'iam.serviceAccounts.getAccessToken' denied"
