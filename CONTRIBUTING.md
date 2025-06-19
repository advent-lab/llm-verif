# Contributing Guidelines

Thank you for contributing to this project! We follow a Git workflow that balances flexibility during development with stability in our mainline code. This guide will help you understand our branching model and how to contribute effectively.

---

## 🌿 Branching Model

We use a 3-tier Git branching structure:

| Branch | Purpose |
|--------|---------|
| `main` | ✅ Always working & stable. Merges only after review. |
| `develop` | 🧪 Shared development branch. Frequent updates. |
| `feature/*`, `fix/*` | 🔧 Short-lived branches for individual work. Merged into `develop`. |

---

## 🧭 Contribution Workflow

### 1. Start from `develop`

```bash
git checkout develop
git pull origin develop
```

### 2. Create a new feature or fix branch

```bash
git checkout -b feature/<your-feature-name>
# or
git checkout -b fix/<bug-description>
```

Use a descriptive branch name to explain the change.

### 3. Make your changes

- Commit early and often
- Use clear commit messages (consider [Conventional Commits](https://www.conventionalcommits.org/))

```bash
git add .
git commit -m "feat: add new login form"
```

### 4. Add tests and documentation

- Cover new logic with tests
- Update relevant documentation (e.g. `README.md` or inline comments)

### 5. (Optional) Clean up commit history before sharing

If your branch hasn’t been pushed yet:
```bash
git rebase -i develop
```

Squash related commits, reword messages, or remove any "WIP" commits.

### 6. Push your branch

```bash
git push origin feature/<your-feature-name>
```

### 7. Open a Pull Request (PR) → target: `develop`

- Go to GitHub and click “Compare & Pull Request”
- Write a clear title and description:
  - What the change does
  - Why it’s needed
  - Any related issues or tests

### 8. Review & Merge

- Wait for a review and for all CI checks to pass
- Once approved, squash-merge into `develop`
- You may delete the feature branch afterward

---

## 🔄 Promoting to `main`

- Merges into `main` are done from `develop`
- Must pass all tests, reviews, and be approved by a maintainer
- We use **Squash & Merge** or **Fast-forward Merge** to keep `main` clean

```bash
git checkout main
git pull origin main
git merge --ff-only develop
git push origin main
```

---

## 🚫 Shared Branch Rules

| Branch | Protection Rules |
|--------|------------------|
| `main` | ✅ PRs required, ✅ Status checks, ✅ No force-push |
| `develop` | ⚠ PRs recommended, ❌ No rebase or force-push after sharing |
| `feature/*`, `fix/*` | 🆓 Freely editable until pushed for review |

---

## 🧹 After Merge

After your PR is merged:
```bash
git checkout develop
git pull origin develop
git branch -d feature/<your-feature-name>
git push origin --delete feature/<your-feature-name>
```

---

Thank you for helping us build a better project! 🚀