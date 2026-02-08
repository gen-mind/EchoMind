# Contributing to EchoMind

Thank you for your interest in contributing to EchoMind! 🎉

We welcome contributions of all kinds: bug reports, feature requests, documentation improvements, and code contributions.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Getting Help](#getting-help)

---

## 📜 Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+** with conda/miniforge
- **Docker** and **Docker Compose**
- **Node.js 18+** and **npm** (for WebUI)
- **Git**

### Environment Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/echo-mind.git
   cd echo-mind
   ```

2. **Create conda environment:**
   ```bash
   conda env create -f environment.yml
   conda activate echomind
   ```

3. **Install dependencies:**
   ```bash
   # Python dependencies
   cd src/echomind_lib
   pip install -e ".[dev]"

   # WebUI dependencies (if working on frontend)
   cd ../web
   npm install
   ```

4. **Set up local environment:**
   ```bash
   cd deployment/docker-cluster
   cp .env.example .env
   # Edit .env with your local settings
   ```

5. **Start local cluster:**
   ```bash
   ./cluster.sh -L start
   ```

---

## 🔄 Development Workflow

We use a **simplified GitHub Flow with staging**:

```
main (production)
 ↑
develop (staging - demo.echomind.ch)
 ↑
feature/your-feature-name (your work)
```

### Branch Naming Convention

Use descriptive branch names with prefixes:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/add-langfuse-integration` |
| `fix/` | Bug fixes | `fix/healthcheck-localhost-issue` |
| `docs/` | Documentation only | `docs/update-contributing-guide` |
| `refactor/` | Code refactoring | `refactor/service-architecture` |
| `test/` | Test improvements | `test/add-unit-tests-for-embedder` |
| `chore/` | Maintenance tasks | `chore/update-dependencies` |

### Creating a Feature Branch

1. **Ensure you're on `develop` and it's up-to-date:**
   ```bash
   git checkout develop
   git pull origin develop
   ```

2. **Create your feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes and commit regularly:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

4. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

---

## 🔍 Pull Request Process

### Before Submitting

- [ ] Code follows our [coding standards](#coding-standards)
- [ ] All tests pass locally (`pytest tests/` for Python, `npm test` for WebUI)
- [ ] New code has tests (100% coverage for new code)
- [ ] Documentation is updated (if applicable)
- [ ] Commit messages follow [conventional commits](#commit-message-guidelines)
- [ ] No merge conflicts with `develop`

### Submitting a PR

1. **Push your branch to your fork**

2. **Open a PR on GitHub:**
   - **Base:** `develop` (NOT `main`)
   - **Compare:** `your-fork:feature/your-feature-name`
   - **Title:** Clear, descriptive summary (50 chars max)
   - **Description:** Use the PR template (auto-populated)

3. **Wait for review:**
   - **Automated checks** will run (tests, linting, type checking)
   - **Maintainer review** required (1 approval minimum)
   - **Response time:** Typically 1-3 days for initial feedback

4. **Address feedback:**
   - Make requested changes
   - Push new commits (don't force-push during review)
   - Reply to comments to let reviewers know changes are ready

5. **Merge:**
   - Once approved and CI passes, a maintainer will merge your PR
   - Your branch will be automatically deleted

### PR Checklist

Your PR will be reviewed for:
- ✅ Code quality and adherence to project patterns
- ✅ Test coverage (must not decrease overall coverage)
- ✅ Documentation updates (if features/APIs changed)
- ✅ No breaking changes (unless discussed in issue first)
- ✅ Performance impact (no significant regressions)

---

## 💻 Coding Standards

### Python

- **Style:** Follow PEP 8
- **Type hints:** Required for all functions
- **Docstrings:** Google style for all public functions/classes
- **Imports:** Absolute imports from `echomind_lib`
- **Logging:** Use emoji logging pattern (see `.claude/rules/logging.md`)
- **Error handling:** Always use `raise ... from e` for exception chaining

**Example:**
```python
from echomind_lib.models.document import Document

def process_document(doc: Document) -> dict[str, Any]:
    """Process a document and return metadata.

    Args:
        doc: The document to process

    Returns:
        Dictionary containing document metadata

    Raises:
        ValidationError: If document is invalid
    """
    try:
        return {"id": doc.id, "title": doc.title}
    except Exception as e:
        raise ValidationError("Invalid document") from e
```

### TypeScript/React (WebUI)

- **Style:** Prettier + ESLint configuration
- **Components:** Functional components with TypeScript
- **Naming:** PascalCase for components, camelCase for functions
- **Props:** Define explicit interfaces
- **State:** Use hooks (useState, useEffect, etc.)

### Protobuf

- **Never edit generated code** in `echomind_lib/models/` or `web/src/models/`
- **Regenerate after `.proto` changes:** `./scripts/generate_proto.sh`

---

## 🧪 Testing Requirements

### Python Tests

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run with coverage
PYTHONPATH=src pytest tests/ --cov --cov-report=term-missing

# Run specific test file
PYTHONPATH=src pytest tests/unit/embedder/test_encoder.py -v
```

**Requirements:**
- ✅ **100% coverage** for new code
- ✅ Unit tests for all new functions/classes
- ✅ Mock all external dependencies (DB, APIs, queues)
- ✅ Use descriptive test names (`test_embed_batch_with_empty_input_raises_error`)

### JavaScript/TypeScript Tests

```bash
cd src/web
npm test                    # Run all tests
npm test -- --coverage      # With coverage
npm test Button.test.tsx    # Specific file
```

**Requirements:**
- ✅ Test user interactions
- ✅ Test component rendering
- ✅ Mock API calls

---

## 📝 Commit Message Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(api): add document upload endpoint` |
| `fix` | Bug fix | `fix(embedder): handle empty input gracefully` |
| `docs` | Documentation only | `docs: update API usage examples` |
| `style` | Code style (formatting, no logic change) | `style(api): fix indentation` |
| `refactor` | Code refactoring | `refactor(connector): simplify auth logic` |
| `perf` | Performance improvement | `perf(embedder): cache model loading` |
| `test` | Add/update tests | `test(api): add tests for auth middleware` |
| `chore` | Maintenance tasks | `chore: update dependencies` |
| `ci` | CI/CD changes | `ci: add GitHub Actions workflow` |

### Examples

**Good commits:**
```
feat(langfuse): add OTLP integration for trace collection

Integrates Langfuse v3 for LLM observability with RAGAS evaluation support.
Configures ClickHouse for trace storage and MinIO for event uploads.

Closes #123
```

```
fix(healthcheck): use 0.0.0.0 instead of localhost

Next.js binds to 0.0.0.0 but not to 127.0.0.1, causing healthcheck failures.
Changed healthcheck target to 0.0.0.0:3000 for both web and worker.

Fixes #456
```

**Bad commits:**
```
fixed stuff
update
WIP
asdfasdf
```

### Rules

- ✅ Use imperative mood ("add", not "added" or "adds")
- ✅ First line ≤ 72 characters
- ✅ Reference issues/PRs in footer (`Closes #123`, `Fixes #456`)
- ✅ Include breaking changes: `BREAKING CHANGE: ...`

---

## 🆘 Getting Help

- **Questions:** Open a [Discussion](https://github.com/gen-mind/echo-mind/discussions)
- **Bugs:** Open an [Issue](https://github.com/gen-mind/echo-mind/issues)
- **Security:** Email security@echomind.ch (do NOT open public issues)
- **Chat:** [Join our Discord](#) (if available)

---

## 🎯 Good First Issues

Look for issues labeled [`good first issue`](https://github.com/gen-mind/echo-mind/labels/good%20first%20issue) - these are perfect for new contributors!

---

## 📚 Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [API Specification](docs/api-spec.md)
- [Database Schema](docs/db-schema.md)
- [Proto Definitions](docs/proto-definitions.md)
- [CLAUDE.md](CLAUDE.md) - Development guidelines for AI assistants

---

## 🙏 Recognition

Contributors are recognized in:
- **README.md** Contributors section
- **CHANGELOG.md** for each release
- **GitHub Insights** contributor graph

Thank you for making EchoMind better! 💙
