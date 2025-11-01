# 🎯 Special Instructions for Haiku (Claude 3.5)

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

**Each commit should represent a complete, tested fix - NOT intermediate debugging steps.**

### Commit Rules:
1. **Plan before committing** - understand the full fix needed
2. **Test before committing** - verify it actually works
3. **One commit per logical fix** - batch all related changes together
4. **Never commit intermediate states** - don't push debugging output, status checks, or partial fixes
5. **Write clear commit messages** - explain WHAT was broken and WHY the fix works

### Anti-Pattern (Don't Do This):
```
❌ Commit 1: "Try adding role X"
❌ Commit 2: "That didn't work, try role Y"
❌ Commit 3: "Add IAM binding"
❌ Commit 4: "Fix workflow config"
❌ Commit 5: "Organize docs"
```

### Pattern (Do This):
```
✅ Single commit: "Fix: GitHub Actions auth by granting serviceAccountTokenCreator and fixing Workload Identity binding"
   - Includes all IAM role grants
   - Includes workflow config updates
   - Includes documentation
   - Tested and verified working
```

## 🚀 Problem-Solving Workflow

When fixing an issue:
1. **Diagnose the root cause** - use `think` tool to reason through it
2. **Gather all context** - read files, check configs, run diagnostic commands
3. **Develop complete solution** - don't just patch symptoms
4. **Verify locally** - test the fix with actual commands before committing
5. **Commit once** with comprehensive message
6. **Push to git** - only when ready

## 📋 Current Project Context

- **Project**: search-MRCONSO-service
- **Auth Method**: Workload Identity Federation (OIDC from GitHub to GCP)
- **Service Account**: gh-deployer@agents-mcp-training.iam.gserviceaccount.com
- **Repository**: AndrewMichael2020/search-MRCONSO-service
- **Issue**: GitHub Actions failing with "Permission 'iam.serviceAccounts.getAccessToken' denied"
