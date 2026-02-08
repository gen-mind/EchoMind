# GitHub Repository Setup Guide

This guide walks you through setting up branch protection, Actions, and other GitHub repository settings for EchoMind.

## 📋 Prerequisites

- Repository admin access
- GitHub Pro/Team (for some advanced features) or use GitHub Free with limitations

---

## 1️⃣ Create `develop` Branch

```bash
# Ensure you're on main and up-to-date
git checkout main
git pull origin main

# Create develop branch
git checkout -b develop

# Push to remote
git push origin develop

# Set develop as default branch on GitHub (optional):
# Go to Settings → Branches → Default branch → Change to 'develop'
```

**Why develop as default?** New contributors will create PRs to `develop` by default, which is what we want.

---

## 2️⃣ Configure Branch Protection

### Protect `main` Branch

**Settings → Branches → Add rule**

**Branch name pattern:** `main`

**Protect matching branches:**
- ✅ **Require a pull request before merging**
  - Number of required approvals: `1`
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (optional, if you create `.github/CODEOWNERS`)
  - ✅ Require approval of the most recent reviewable push

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - **Required status checks:** (Add after first CI run)
    - `test-python`
    - `test-web`
    - `lint-python`
    - `lint-web`
    - `build`
    - `proto-check`

- ✅ **Require conversation resolution before merging**

- ✅ **Require signed commits** (recommended for security)

- ✅ **Require linear history** (enforces rebase/squash, cleaner history)

- ✅ **Do not allow bypassing the above settings**
  - Applies rules to administrators too

- **Rules applied to everyone including administrators:**
  - ✅ Restrict who can push to matching branches
    - ❌ Allow force pushes: **Disable**
    - ❌ Allow deletions: **Disable**

**Save changes**

### Protect `develop` Branch

**Settings → Branches → Add rule**

**Branch name pattern:** `develop`

**Protect matching branches:**
- ✅ **Require a pull request before merging**
  - Number of required approvals: `1`
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require approval of the most recent reviewable push

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - **Required status checks:**
    - `test-python`
    - `test-web`
    - `lint-python`
    - `lint-web`

- ✅ **Require conversation resolution before merging**

- ✅ **Require linear history**

- **Rules applied to everyone including administrators:**
  - ❌ Allow force pushes: **Disable**
  - ❌ Allow deletions: **Disable**

**Save changes**

---

## 3️⃣ Enable GitHub Actions

**Settings → Actions → General**

**Actions permissions:**
- ✅ Allow all actions and reusable workflows

**Workflow permissions:**
- ✅ Read and write permissions
- ✅ Allow GitHub Actions to create and approve pull requests

**Fork pull request workflows:**
- ✅ Require approval for first-time contributors

**Save**

---

## 4️⃣ Configure Code Scanning (Optional but Recommended)

**Security → Code scanning → Set up**

1. **CodeQL Analysis:**
   - Click "Set up this workflow"
   - Commit `.github/workflows/codeql.yml`

2. **Dependabot:**
   - **Security → Dependabot → Enable**
   - Enables automatic security updates

---

## 5️⃣ Set Up Secrets

**Settings → Secrets and variables → Actions → New repository secret**

Add these secrets (if using automated deployments):

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `DOCKER_HUB_USERNAME` | Docker Hub username | `genmind` |
| `DOCKER_HUB_TOKEN` | Docker Hub access token | `dckr_pat_...` |
| `SSH_PRIVATE_KEY` | SSH key for demo.echomind.ch | `-----BEGIN...` |
| `HOST_IP` | Demo server IP | `65.108.201.29` |
| `CODECOV_TOKEN` | Codecov upload token | `abc123...` |

---

## 6️⃣ Configure Issue Templates

Create `.github/ISSUE_TEMPLATE/`:

**Bug Report:**
```bash
cat > .github/ISSUE_TEMPLATE/bug_report.yml << 'EOF'
name: Bug Report
description: File a bug report
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!

  - type: textarea
    id: description
    attributes:
      label: Bug Description
      description: A clear and concise description of the bug
      placeholder: Tell us what you see!
    validations:
      required: true

  - type: textarea
    id: reproduce
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior
      placeholder: |
        1. Go to '...'
        2. Click on '....'
        3. See error
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Logs
      description: Please paste any relevant logs
      render: shell

  - type: dropdown
    id: component
    attributes:
      label: Component
      options:
        - API
        - WebUI
        - Embedder
        - Ingestor
        - Connector
        - Search
        - Other
    validations:
      required: true
EOF
```

**Feature Request:**
```bash
cat > .github/ISSUE_TEMPLATE/feature_request.yml << 'EOF'
name: Feature Request
description: Suggest a new feature
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
      description: What problem does this feature solve?
      placeholder: I'm always frustrated when...
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: Describe the solution you'd like
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Any alternative solutions or features you've considered
EOF
```

---

## 7️⃣ Create CODEOWNERS File (Optional)

```bash
cat > .github/CODEOWNERS << 'EOF'
# Code owners are automatically requested for review when someone opens a pull request

# Global owners
* @your-github-username

# Component owners
/src/api/ @api-team-member
/src/web/ @frontend-team-member
/src/embedder/ @ml-team-member
/docs/ @docs-team-member

# Infrastructure
/deployment/ @devops-team-member
/.github/ @devops-team-member
EOF
```

---

## 8️⃣ Enable Discussions

**Settings → Features → Discussions**
- ✅ Enable discussions

**Categories:**
- 💡 Ideas
- 🙏 Q&A
- 📣 Announcements
- 🗣️ General

---

## 9️⃣ Configure Labels

**Issues → Labels → New label**

Recommended labels:

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | `d73a4a` | Something isn't working |
| `enhancement` | `a2eeef` | New feature or request |
| `documentation` | `0075ca` | Improvements to documentation |
| `good first issue` | `7057ff` | Good for newcomers |
| `help wanted` | `008672` | Extra attention is needed |
| `priority: high` | `d93f0b` | High priority |
| `priority: low` | `0e8a16` | Low priority |
| `wontfix` | `ffffff` | This will not be worked on |
| `duplicate` | `cfd3d7` | This issue already exists |
| `question` | `d876e3` | Further information is requested |

---

## 🔟 Verify Setup

### Test Branch Protection

1. **Try to push directly to main:**
   ```bash
   git checkout main
   echo "test" >> README.md
   git commit -am "test direct push"
   git push origin main
   ```
   **Expected:** ❌ Push rejected (branch protected)

2. **Create a PR:**
   ```bash
   git checkout develop
   git checkout -b test/branch-protection
   echo "test" >> README.md
   git commit -am "test: verify branch protection"
   git push origin test/branch-protection
   ```
   **Then:** Open PR to `develop` on GitHub
   **Expected:** ✅ CI runs, requires approval

### Test GitHub Actions

1. **Push triggers CI:**
   - Check "Actions" tab on GitHub
   - All workflows should run

2. **Status checks appear on PR:**
   - PR shows "Some checks haven't completed yet"
   - After completion, shows "All checks have passed"

---

## 📊 Monitoring

**Insights Tab:**
- **Pulse:** Activity overview
- **Contributors:** Contributor graph
- **Traffic:** Visits and clones
- **Dependency graph:** Dependencies visualization

**Security Tab:**
- **Security advisories:** CVE notifications
- **Dependabot alerts:** Vulnerable dependencies
- **Code scanning:** Security issues in code

---

## 🔄 Maintenance

### Quarterly Reviews

- **Update dependencies** (Dependabot PRs)
- **Review branch protection** rules
- **Audit access** permissions
- **Check Actions** usage (minutes quota)

### Annual Tasks

- **Rotate secrets** (Docker Hub tokens, SSH keys)
- **Review team** access levels
- **Archive stale** branches
- **Update documentation**

---

## 📚 References

- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) (GitHub Docs, official)
- [GitHub Actions](https://docs.github.com/en/actions) (GitHub Docs, official)
- [Repository Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) (GitHub Docs, 2026)
- [Conventional Commits](https://www.conventionalcommits.org/) (Official spec)

---

## ✅ Checklist

After setup, verify:

- [ ] `develop` branch created and set as default
- [ ] `main` branch protection enabled (1 approval, CI required)
- [ ] `develop` branch protection enabled (1 approval, CI required)
- [ ] GitHub Actions enabled
- [ ] Secrets configured (if needed)
- [ ] Issue templates created
- [ ] Labels configured
- [ ] CONTRIBUTING.md committed
- [ ] PR template committed
- [ ] CI workflow committed
- [ ] Tested branch protection (direct push rejected)
- [ ] Tested CI (Actions run on PR)

**Setup complete!** 🎉
