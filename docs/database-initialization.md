# Database initialization

Provision PostgreSQL and configure `DATABASE_URL` before starting the API. The
database itself must exist and the configured role must be able to create tables
and functions in its `public` schema.

API lifespan and ARQ worker startup call the same asynchronous schema bootstrap.
On an empty database it imports the complete model registry, creates all current
tables, constraints and indexes, and installs the exam contributor triggers. A
PostgreSQL transaction advisory lock serializes concurrent workers; schema
creation and trigger installation commit together or roll back together.

On subsequent starts it validates the existing table and column definitions,
primary keys, required indexes, checks, unique constraints, foreign keys and
contributor triggers. It never drops tables, clears records, or silently repairs
a partially initialized database. A leftover migration marker by itself is a
partial schema and is rejected. An otherwise compatible existing schema may
retain its historical marker; startup does not use or change it.

From `backend/`, initialize or validate explicitly with:

```powershell
uv run python -m app.core.database_bootstrap
```

The compiled executable exposes `weave-cbt bootstrap`. Docker Compose runs that
command as a one-shot `bootstrap` service before API and worker startup. Manager
health checks require its successful exit.

Automatic creation is for fresh installation, **not schema upgrades**. Removing
the migration chain does not make SQLAlchemy alter existing columns. Future
schema changes for installations with school data require an explicit reviewed
upgrade and a backup. Never delete a school database to make startup pass.

To run the PostgreSQL integration tests, set
`WEAVE_BOOTSTRAP_TEST_DATABASE_URL` to an explicitly designated local test database
connection whose role can create databases, then run
`uv run pytest tests/test_database_bootstrap.py`. Tests create and drop only their
own uniquely named `weave_bootstrap_test_*` databases.

Before handing off or pushing the repository, run `./scripts/Cleanup.ps1` from the
repository root (`-Preview` lists targets). It removes generated caches and
frontend build output while retaining source, virtual environments, credentials,
local media, and database/runtime data.
