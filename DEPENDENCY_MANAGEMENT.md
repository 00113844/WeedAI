# Dependency Management Strategy for WeedAI

## Overview
This document outlines how dependencies are managed across the WeedAI monorepo using `uv` workspace mode. The strategy prioritizes **isolation**, **reproducibility**, and **minimal conflicts**.

## Table of Contents
1. [Core Principles](#core-principles)
2. [Workspace Structure](#workspace-structure)
3. [Adding Dependencies](#adding-dependencies)
4. [Dependency Resolution](#dependency-resolution)
5. [Guardrails-Specific Strategy](#guardrails-specific-strategy)
6. [Common Issues](#common-issues)

---

## Core Principles

### 1. Separate, Composable Dependencies
Each component has its own `pyproject.toml` with only required dependencies.

**Benefits:**
- Minimal installation footprint (install only what you need)
- Easier version management (upgrade one component without affecting others)
- Clear dependency boundaries (fewer hidden transitive dependencies)
- Reduced risk of version conflicts

### 2. Single Lockfile for Reproducibility
Root `uv.lock` file provides reproducible builds across all environments.

**Benefits:**
- Deterministic builds (same lock = same binaries)
- CI/CD consistency (staging ≈ production)
- Easy rollback (git revert uv.lock)

### 3. Workspace-Mode Coordination
Root `pyproject.toml` declares all members; `uv` resolves versions globally.

**Benefits:**
- Single dependency source of truth
- Transitive dependency management
- Simplified CI/CD

---

## Workspace Structure

### Root Structure

```
WeedAI/
├── pyproject.toml                 # Workspace root (no dependencies)
│   [tool.uv.workspace]
│   members = [
│       "apps/api",
│       "apps/web",
│       "apps/simulation-sidecar",
│       "packages/core",
│       "packages/graph",
│       "packages/guardrails",     # NEW: Isolated guardrails
│   ]
│
├── uv.lock                        # SINGLE lockfile for all members
├── apps/
│   ├── api/pyproject.toml         # FastAPI + LangGraph deps
│   ├── web/pyproject.toml         # Next.js + Node deps (separate)
│   └── simulation-sidecar/pyproject.toml
│
└── packages/
    ├── core/pyproject.toml        # Shared utilities
    ├── graph/pyproject.toml       # LangGraph + Neo4j
    └── guardrails/pyproject.toml  # NeMo Guardrails (isolated)
```

### Each Component's pyproject.toml

**Example: `packages/guardrails/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "guardrails"
version = "0.1.0"
description = "NeMo Guardrails for WeedAI"
requires-python = ">=3.11"
dependencies = [
    "nemo-guardrails[langchain]==0.10.0",  # Pinned major.minor
    "pydantic>=2.0,<3.0",                   # Compatible release
    "python-dotenv>=1.0",
    "langchain>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
]
```

**Version Pinning Strategy:**
| Pattern | Use Case | Example |
|---------|----------|---------|
| `==X.Y.Z` | Critical, breaking versions | `nemo-guardrails==0.10.0` |
| `>=X.Y` | Stable APIs | `pydantic>=2.0,<3.0` |
| `>=X.Y.Z` | Bugfixes allowed | `python-dotenv>=1.0` |

---

## Adding Dependencies

### Adding to a Specific Component

```bash
# Add to guardrails package
uv add nemo-guardrails --package packages/guardrails

# Add dev dependency
uv add pytest --package packages/guardrails --group dev

# Add to API
uv add fastapi --package apps/api
```

### Adding to Multiple Components

```bash
# Add to both core and graph
uv add pydantic --package packages/core --package packages/graph

# Add dev tool to all packages
uv add mypy --package packages/{core,graph,guardrails} --group dev
```

### Important: Don't Add to Root

```bash
# ❌ DON'T do this (pollutes all components)
uv add package-name

# ✅ DO this (specific to component)
uv add package-name --package packages/guardrails
```

---

## Dependency Resolution

### How `uv` Resolves Versions

1. **Reads all `pyproject.toml` files** (root + all members)
2. **Collects dependency specs** from all components
3. **Resolves conflicts** using SAT solver
4. **Writes single `uv.lock`** with exact pinned versions
5. **Installs** from lock file (reproducible)

### Example Resolution Conflict

**Scenario:** Two packages require incompatible LangChain versions

```
packages/core:       langchain>=0.1.0,<0.2.0
packages/guardrails: langchain>=0.2.0,<0.3.0
```

**Resolution Error:**
```
error: unsatisfiable requirement langchain>=0.2.0
  required by: packages/guardrails
  conflicts with: packages/core/langchain<0.2.0
```

**Solution:** Negotiate compatible versions in both packages

```
packages/core:       langchain>=0.1.0,<0.3.0  # Relax upper bound
packages/guardrails: langchain>=0.1.0,<0.3.0  # Tighten lower bound
```

---

## Guardrails-Specific Strategy

### Why Separate Dependencies?

**Problem:** NeMo Guardrails has strict dependency requirements:
- Requires specific LangChain versions
- Pulls in heavyweight deps (Colang runtime, model loaders)
- May conflict with API layer (different FastAPI versions)

**Solution:** Isolate in `packages/guardrails`

### Installation Scenarios

**Scenario 1: Full Stack (Development)**
```bash
# Install all packages
uv pip install -e packages/core
uv pip install -e packages/graph
uv pip install -e packages/guardrails
uv pip install -e apps/api
```

**Scenario 2: API Only (Lightweight)**
```bash
# Skip guardrails if not needed
uv pip install -e packages/core
uv pip install -e packages/graph
uv pip install -e apps/api
```

**Scenario 3: Guardrails Only (Testing)**
```bash
# Test guardrails in isolation
uv pip install -e packages/guardrails
pytest packages/guardrails/tests/
```

### Guardrails Dependencies

```toml
[project]
dependencies = [
    # Core NeMo
    "nemo-guardrails[langchain]==0.10.0",
    
    # LangChain (used by NeMo)
    "langchain>=0.1.0",
    "langchain-core>=0.1.0",
    
    # Config/Validation
    "pydantic>=2.0,<3.0",
    "python-dotenv>=1.0",
    
    # Don't list transitive deps (let NeMo declare them)
    # FastAPI is NOT listed here (pulled in by apps/api separately)
]
```

---

## Common Issues

### Issue 1: "Unsatisfiable Requirement"

**Error:**
```
error: unsatisfiable requirement pydantic>=2.0,<3.0
  required by: packages/core
  conflicts with: pydantic<2.0 from packages/guardrails
```

**Solution:**
1. Check which component is pinning old version
2. Update to compatible version OR
3. Use `uv pip compile --universal` to see all conflicts

```bash
uv pip compile --universal
```

### Issue 2: "Dependency Not Found"

**Error:**
```
error: package 'some-package' not found
  required by: packages/guardrails
```

**Solution:**
1. Check spelling
2. Verify package exists: `uv pip search some-package`
3. Ensure added to correct `pyproject.toml`

### Issue 3: Lock File Conflicts in Git

**Error:**
```
Auto-merging uv.lock
CONFLICT (content): Merge conflict in uv.lock
```

**Solution:**
1. Don't manually edit `uv.lock`
2. Resolve dependency conflict in `pyproject.toml` files
3. Regenerate lock: `uv lock --refresh`

```bash
# Resolve conflict in pyproject.toml files
git checkout --theirs packages/guardrails/pyproject.toml
git checkout --theirs packages/core/pyproject.toml

# Regenerate lock
uv lock --refresh

# Re-add and commit
git add uv.lock packages/*/pyproject.toml
git commit -m "Resolve dependency conflicts"
```

### Issue 4: "Package Installed But Not Found"

**Error:**
```
ModuleNotFoundError: No module named 'nemo_guardrails'
```

**Solution:**
1. Ensure installed with `-e` (editable mode):
   ```bash
   uv pip install -e packages/guardrails
   ```
2. Check Python path: `python -c "import sys; print(sys.path)"`
3. Verify package is in `uv.lock`: `grep nemo-guardrails uv.lock`

---

## Best Practices

### ✅ DO

- ✅ Pin major.minor for critical packages: `package==1.2.0`
- ✅ Use compatible release for stable packages: `package>=1.2,<2.0`
- ✅ Commit `uv.lock` to version control
- ✅ Run `uv lock --refresh` after manual edits to `pyproject.toml`
- ✅ Test each component in isolation: `cd packages/guardrails && pytest`
- ✅ Document dependency rationale (why this version?)

### ❌ DON'T

- ❌ Edit `uv.lock` manually
- ❌ Add dependencies to root `pyproject.toml`
- ❌ Use `pip install` (use `uv pip install` instead)
- ❌ Assume transitive dependencies are pinned (they're not)
- ❌ Ignore version conflicts (they will fail in CI)

### Pre-Commit Hook

**`.pre-commit-config.yaml`** (optional):
```yaml
- repo: local
  hooks:
    - id: uv-lock
      name: uv lock check
      entry: bash -c 'uv lock --check'
      language: system
      pass_filenames: false
      stages: [commit]
```

---

## Guardrails Dependency Timeline

| Phase | Action | Command |
|-------|--------|---------|
| **Phase 1** | Create guardrails package | `mkdir -p packages/guardrails/src` |
| **Phase 1** | Create pyproject.toml | Create file with NeMo deps |
| **Phase 2** | Add to workspace | Edit root `pyproject.toml` workspace.members |
| **Phase 2** | Regenerate lock | `uv lock --refresh` |
| **Phase 3** | Install for development | `uv pip install -e packages/guardrails` |
| **Phase 4** | Test isolation | `cd packages/guardrails && pytest` |
| **Phase 5** | Integrate with LangGraph | Ensure LangChain versions compatible |

---

## FAQ

**Q: Should guardrails be a separate package?**  
A: Yes—NeMo has specific dependencies that may conflict with API/web layers. Isolation reduces risk.

**Q: Can I install only the API without guardrails?**  
A: Yes. Installing `apps/api` alone will pull only API dependencies. Guardrails is optional.

**Q: How do I know if there are dependency conflicts?**  
A: Run `uv lock --refresh` and check error messages. Or use `uv pip compile --universal`.

**Q: Can I use different Python versions for different packages?**  
A: No—workspace requires single Python version. All packages must satisfy `requires-python`.

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-07  
**Owner:** Backend Team
