# Contributing

## Git Workflow

### Branch Naming

Create all branches off `develop`:

```
<type>/<initials>/<issue-number>-<description>
```

| Component      | Description                                              |
|----------------|----------------------------------------------------------|
| `type`         | `feat`, `fix`, `docs`, `refactor`, `test`, `chore`       |
| `initials`     | Your initials (e.g., `ss`)                               |
| `issue-number` | GitHub issue number                                      |
| `description`  | Short kebab-case description                             |

Examples:

```
feat/ss/1-add-config
fix/ss/5-typescript-parser
docs/ss/4-getting-started
```

### Commit Messages

Follow conventional commits:

```
<type>: <description>

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

```
feat: add TypeScript model generator
fix: handle nested optional fields correctly
docs: update CLI reference for new options
```

Guidelines:

- Keep subject line under 72 characters
- Use imperative mood ("add" not "added")
- Don't end subject with period
- Explain what and why, not how

### Development Flow

```bash
# 1. Start from develop
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feat/ss/1-add-config

# 3. Run quality checks
make check

# 4. Commit and push
git add .
git commit -m "feat: add configuration system"
git push origin feat/ss/1-add-config

# 5. Create PR to develop
gh pr create --base develop
```

### Pre-commit Hooks

Hooks run automatically on commit (see `Makefile` for installation).

What they do:

- Ruff linting and formatting
- Trailing whitespace removal
- YAML/TOML validation
- Spell checking
- Commit message format validation (conventional commits)

Manual run:

```bash
make pre-commit  # Run all hooks
```
