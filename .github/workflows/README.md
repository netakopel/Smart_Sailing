# CI/CD Workflows for Smart Sailing Route Planner

This directory contains GitHub Actions workflows that automate testing and deployment for the project.

## 📋 Available Workflows

### 1. Backend Tests (`backend-tests.yml`)
**Triggers:** Push or PR to `main`/`develop` branches (when backend files change)

**What it does:**
- Sets up Python 3.11 environment
- Installs dependencies from `requirements.txt`
- Runs all test files (`test_*.py`) with pytest
- Reports test results

**Status Badge:**
```markdown
![Backend Tests](https://github.com/YOUR_USERNAME/YOUR_REPO/workflows/Backend%20Tests/badge.svg)
```

### 2. Frontend Build & Lint (`frontend-build.yml`)
**Triggers:** Push or PR to `main`/`develop` branches (when frontend files change)

**What it does:**
- Sets up Node.js 18 environment
- Installs npm dependencies
- Runs ESLint for code quality checks
- Builds the React app with TypeScript + Vite
- Verifies no build errors

**Status Badge:**
```markdown
![Frontend Build](https://github.com/YOUR_USERNAME/YOUR_REPO/workflows/Frontend%20Build%20%26%20Lint/badge.svg)
```

### 3. Lambda Deploy (`lambda-deploy.yml`) - OPTIONAL
**Triggers:** Manual only (workflow_dispatch) by default

**What it does:**
- Packages backend code for AWS Lambda
- Creates `lambda_package.zip`
- (Optional) Auto-deploys to AWS Lambda

**To enable auto-deployment:**
1. Add GitHub Secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION` (e.g., `il-central-1`)
2. Uncomment the AWS deployment steps in the workflow file
3. Uncomment the `on: push` trigger

## 🚀 How to Use

### First Time Setup
1. Push this repository to GitHub
2. Workflows will automatically run on the next push
3. View results in the "Actions" tab on GitHub

### Daily Development
- **Make changes** → **Push to GitHub** → **Workflows run automatically**
- See test results in pull requests
- Green checkmark ✅ = All tests passed
- Red X ❌ = Tests failed (check logs)

### Viewing Results
1. Go to your GitHub repository
2. Click the "Actions" tab
3. Click on any workflow run to see details
4. Expand steps to see full logs

## 🎯 Benefits

| Benefit | Description |
|---------|-------------|
| **Catch bugs early** | Tests run on every commit before merging |
| **Safe refactoring** | Complex algorithms can be improved with confidence |
| **Code quality** | ESLint catches TypeScript issues automatically |
| **Consistent builds** | Same environment every time (no "works on my machine") |
| **Fast feedback** | See test results in ~2-3 minutes |
| **Free** | GitHub Actions is free for public repos |

## 🔧 Customization

### Run tests on different branches
Edit the `on:` section in workflow files:
```yaml
on:
  push:
    branches: [ main, develop, feature/* ]
```

### Add code coverage
Add to `backend-tests.yml`:
```yaml
- name: Run tests with coverage
  run: |
    cd backend
    python -m pytest test_*.py --cov=. --cov-report=term
```

### Add notifications
Use GitHub Actions marketplace actions for:
- Slack notifications
- Email alerts
- Discord webhooks

## 📊 Current Test Coverage

**Backend Tests:**
- `test_dev_server.py` - API endpoint tests
- `test_isochrone_simple.py` - Routing algorithm tests
- `test_cone.py` - Cone generation tests
- `test_heading_180.py` - Heading calculation tests
- `test_pruning_debug.py` - Pruning logic tests

**Frontend Checks:**
- TypeScript compilation
- ESLint code quality
- Vite build process

## 🐛 Troubleshooting

### Tests fail locally but pass in CI
- Check Python/Node versions match
- Ensure all dependencies are in requirements.txt/package.json

### Tests pass locally but fail in CI
- CI uses clean environment (no cached data)
- Check for hardcoded paths or environment variables

### Workflow doesn't trigger
- Check the `paths:` filter in workflow file
- Ensure you're pushing to the correct branch

## 📚 Learn More

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [ESLint Documentation](https://eslint.org/)

