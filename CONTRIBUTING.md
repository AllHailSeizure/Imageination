# Contributing

Imageination is a small, solo-maintainer project. This guide keeps setup, validation, and conventions in one place.

## Setup

```bash
git clone <repo-url>
cd Imageination
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Run the app

```bash
python run_imageination.py
```

## Run tests

```bash
pytest
```

## Format and lint

Ruff handles both formatting and linting.

```bash
ruff format .
ruff check .
```

CI runs `ruff format --check .`, `ruff check .`, and `pytest` on every push to `master` and every pull request.

## Branch and PR conventions

- Keep branches and PRs focused on one issue or change.
- Write descriptive commit messages explaining *why*, not just *what*.
- Link related issues in the PR description (e.g. `Closes #4`).
- Fill out the PR template's validation and checklist sections.

## Definition of done

- `pytest` passes.
- `ruff format --check .` and `ruff check .` are clean.
- README (or this file) is updated if user-facing behavior or workflow changed.

## Labels

Labels aren't auto-created by tooling; create them in the repo's GitHub UI (Issues → Labels) using this taxonomy:

**Type**
- `bug` — something isn't working
- `feature` — new functionality
- `chore` — tooling, docs, refactors with no behavior change

**Priority**
- `priority: high`
- `priority: medium`
- `priority: low`

**Status**
- `status: triage` — needs a decision before work starts
- `status: ready` — scoped and ready to pick up
- `status: in-progress`
- `status: blocked`
