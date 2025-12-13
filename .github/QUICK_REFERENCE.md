# CI/CD Quick Reference

## 🚀 One-Line Summary
**GitHub Actions automatically runs tests on every push to catch bugs before they reach production.**

---

## 📋 What You Have Now

```
┌─────────────────────────────────────────────────────────┐
│  Developer pushes code to GitHub                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions detects changes                         │
└────┬────────────────────────────────────────────────────┘
     │
     ├──▶ Backend changed? ──▶ Run pytest (2 min) ──▶ ✅/❌
     │
     ├──▶ Frontend changed? ─▶ Build + Lint (3 min) ─▶ ✅/❌
     │
     └──▶ Manual deploy? ────▶ Package Lambda ──────▶ 📦
```

---

## 🎯 Quick Commands

### Before Pushing (Local Testing)
```bash
# Test backend
cd backend
python -m pytest test_*.py -v

# Test frontend
cd frontend
npm run build
npm run lint
```

### Push to GitHub (Triggers CI/CD)
```bash
git add .
git commit -m "Your commit message"
git push origin main
```

### View Results
Go to: `https://github.com/YOUR_USERNAME/YOUR_REPO/actions`

---

## 📁 File Locations

| File | Purpose |
|------|---------|
| `.github/workflows/backend-tests.yml` | Backend CI config |
| `.github/workflows/frontend-build.yml` | Frontend CI config |
| `.github/workflows/lambda-deploy.yml` | Deployment CD config |
| `.github/CICD_SETUP_GUIDE.md` | **START HERE** - Setup guide |
| `.github/CI_CD_SUMMARY.md` | Complete summary |
| `.github/TESTING_CHECKLIST.md` | Pre-push checklist |
| `.github/workflows/README.md` | Detailed docs |

---

## ✅ Success Checklist

- [ ] Push code to GitHub
- [ ] See workflows in Actions tab
- [ ] Green checkmark for passing tests
- [ ] Receive email on failures
- [ ] Tests run automatically on every push

---

## 🐛 Common Issues

| Problem | Fix |
|---------|-----|
| No workflows visible | Push `.github/workflows/*.yml` files |
| Workflow doesn't run | Check branch name (main/develop) |
| Tests fail in CI | Check Python 3.11 / Node 18 versions |

---

## 📚 Documentation Order

1. **QUICK_REFERENCE.md** ← You are here
2. **CICD_SETUP_GUIDE.md** ← Read this next
3. **CI_CD_SUMMARY.md** ← Complete overview
4. **TESTING_CHECKLIST.md** ← Before pushing
5. **workflows/README.md** ← Deep dive

---

## 💡 Remember

- ✅ Tests run **automatically** on push
- ✅ Fast feedback in **2-3 minutes**
- ✅ Catch bugs **before code review**
- ✅ **Free** for public repos
- ✅ Industry **standard practice**

---

**Next:** Read `CICD_SETUP_GUIDE.md` to activate your CI/CD pipeline! 🚀

