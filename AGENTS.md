# Repository Guidelines

## Project Structure & Module Organization

Product code lives under `services/api/app/`: `domain/` holds pure rules, `db/` holds SQLAlchemy and Alembic, `api/` exposes FastAPI routes, `payments/` builds VietQR payloads, and `web/` serves guests. Layer-aligned tests live in `services/api/tests/`; root `tests/` covers the repo guard. Consult `docs/decisions/` before behavior changes and `docs/architecture/` before boundary changes. `phase0/` and `docs/protocol/v1/` are frozen. CI treats currently absent `apps/mobile/` and `packages/shared/` as conditional.

## Build, Test, and Development Commands

- `pip install -r services/api/requirements-dev.txt` installs pinned Python 3.12 dependencies.
- `docker compose up -d postgres` starts PostgreSQL 16 for migrations and tests.
- `cd services/api && alembic upgrade head` migrates the configured local database.
- `cd services/api && uvicorn app.api.main:app --reload` runs the API with reload.
- `cd services/api && python3 -m app.web.preview` previews the guest page without a database.
- `python3 -m pytest services/api/tests tests -q` runs the standard suite.
- `cd services/api && ruff check . && ruff format --check .` checks style and formatting.

Copy `.env.example` to `.env` for local configuration; never commit `.env`.

## Coding Style & Naming Conventions

Use four-space indentation, double quotes, an 88-character line limit, and Python 3.12 syntax. Ruff enforces `E4`, `E7`, `E9`, `F`, `I`, `UP`, and `B`. Use `snake_case` for modules/functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. `domain/` must not import `db`, `api`, or `payments`.

Represent VND as integers, preserve exact allocation totals, and derive balances from the ledger. Propose an ADR before changing these invariants.

## Testing Guidelines

Pytest files and functions use `test_*.py` and `test_*`. Add tests beside the affected layer and extend allocator golden JSON vectors. Persistence changes require the live suite in `docs/testing/postgres-repository.md`; fake-repository tests alone are insufficient. No numeric coverage threshold is configured, so cover each changed behavior and regression.

## Commit & Pull Request Guidelines

History uses scoped summaries such as `api: ...`, `domain: ...`, `test: ...`, `fix(ci): ...`, and `docs: ...`; keep subjects short, imperative, and focused. PR descriptions must explain what changed and why, list validation performed, link relevant issues or ADRs, and include screenshots for UI changes. Do not self-review. Merge only after an independent reviewer records `APPROVE`; return `REQUEST_CHANGES` work to the author.

## Security & Data Handling

Run `scripts/setup-hooks.sh` to enable the staged repo guard. Never place real participant data, credentials, exports, or temporary copies inside any worktree—even if ignored. Follow `docs/security/repo-guard.md`; `.gitignore` and scanners are mitigation layers, not safe storage.

## Shared Team Invariants (all agents read this file)

This section is the minimum every agent — Claude, Codex, agy — must know before
touching anything. It is duplicated from `CLAUDE.md` on purpose: a clean checkout
must carry the rules, not depend on one harness loading one file.

**Three money laws.** Changing any of them requires an ADR opened first, not a
code change first.

1. Integer dong. No `float`, no `Decimal`, not even in intermediate values.
   `allocator.py` uses `Fraction` to keep exact rationals.
2. `Σ allocations == total expense`, 100%. 41 hand-computed golden vectors hold this.
3. Balances are recomputable from the ledger; a cache is never the source of truth.

Also: editing an expense creates a **new version**, never an overwrite.
`receiver_confirmed` is **not** bank evidence. `completed` is produced only by a
domain transition — there is no "mark as done" button.

**Ownership boundaries** (settled 2026-08-27). Claude owns `app/web/` and
`apps/mobile/`. Codex owns `db/`, `api/`, `payments/`, `domain/` and backend
tests. agy owns no product source — it files findings, not diffs. On the guest
page, routing and data access belong to Codex; a template never queries.

**Layer boundary, enforced by AST parsing, not by promise.** `app/domain/` must
not import `app.db`, `app.api`, `app.payments`, `sqlalchemy`, `fastapi`,
`alembic`, or `pydantic`. See `services/api/tests/test_import_boundary.py`.

**Never put in Git, and never send to an external service**: bill photos, bank
account numbers, participant names, raw transcripts, exports, a real `.env`.
`.gitignore` is not a safe place. Real data lives outside the repo and outside
every worktree. `scripts/repo_guard.py` scans what enters Git; it cannot see what
leaves via an API call.

**Language convention**: docs and commit messages in Vietnamese; code comments
and docstrings in English.

**Frozen in place**: `phase0/` and `docs/protocol/v1/`. Do not edit, do not
delete. `protocol_version` is an immutable snapshot.

**A green test suite is not behavioural evidence.** ADR-0006 gated Phase 0 by
leader decision. Read the "proves / does not prove" table in `CLAUDE.md` before
trusting any green mark.
