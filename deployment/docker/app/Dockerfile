# syntax=docker/dockerfile:1.7

# =============================
# Build the React/Vite frontend
# =============================

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# =====================================================
# Shared Python/Nuitka toolchain for compiled artifacts
# =====================================================

FROM python:3.11-slim-bookworm AS python-build-base

WORKDIR /workspace

# Nuitka needs a C compiler and patchelf. ccache reduces repeated C compilation
# within BuildKit builds when API/worker/migration share generated objects.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ccache \
        patchelf \
    && rm -rf /var/lib/apt/lists/*

# Install application dependencies before source code so dependency layers remain
# reusable across normal application changes.
COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN python -m pip install --no-cache-dir \
    -r /workspace/backend/requirements.txt

# Nuitka is a build-only dependency and never reaches the runtime image.
COPY deployment/docker/app/nuitka/requirements-build.txt \
    /workspace/deployment/docker/app/nuitka/requirements-build.txt
RUN python -m pip install --no-cache-dir \
    -r /workspace/deployment/docker/app/nuitka/requirements-build.txt

ENV CCACHE_DIR=/root/.cache/ccache \
    CCACHE_BASEDIR=/workspace \
    CCACHE_COMPILERCHECK=content \
    CCACHE_MAXSIZE=2G


# ==========================================================
# Compile API, worker and migrations in independent stages.
#
# Keeping these stages independent is intentional: a change to migration-only
# build code must not invalidate the expensive API or worker compilation layers.
# BuildKit may also execute independent stages concurrently when all are needed.
# ==========================================================

FROM python-build-base AS api-builder

COPY backend/ /workspace/backend/
COPY deployment/docker/app/entrypoints/api.py \
    /workspace/deployment/docker/app/entrypoints/api.py
COPY deployment/docker/app/nuitka/common-options.txt \
    /workspace/deployment/docker/app/nuitka/common-options.txt
COPY deployment/docker/app/nuitka/build-api.sh \
    /workspace/deployment/docker/app/nuitka/build-api.sh

RUN chmod +x /workspace/deployment/docker/app/nuitka/build-api.sh
RUN --mount=type=cache,id=weave-nuitka-ccache,target=/root/.cache/ccache \
    /workspace/deployment/docker/app/nuitka/build-api.sh \
    && ccache --show-stats


FROM python-build-base AS worker-builder

COPY backend/ /workspace/backend/
COPY deployment/docker/app/entrypoints/worker.py \
    /workspace/deployment/docker/app/entrypoints/worker.py
COPY deployment/docker/app/nuitka/common-options.txt \
    /workspace/deployment/docker/app/nuitka/common-options.txt
COPY deployment/docker/app/nuitka/build-worker.sh \
    /workspace/deployment/docker/app/nuitka/build-worker.sh

RUN chmod +x /workspace/deployment/docker/app/nuitka/build-worker.sh
RUN --mount=type=cache,id=weave-nuitka-ccache,target=/root/.cache/ccache \
    /workspace/deployment/docker/app/nuitka/build-worker.sh \
    && ccache --show-stats


FROM python-build-base AS migrate-builder

COPY backend/ /workspace/backend/
COPY deployment/docker/app/entrypoints/migrate.py \
    /workspace/deployment/docker/app/entrypoints/migrate.py
COPY deployment/docker/app/nuitka/common-options.txt \
    /workspace/deployment/docker/app/nuitka/common-options.txt
COPY deployment/docker/app/nuitka/build-migrate.sh \
    /workspace/deployment/docker/app/nuitka/build-migrate.sh

RUN chmod +x /workspace/deployment/docker/app/nuitka/build-migrate.sh
RUN --mount=type=cache,id=weave-nuitka-ccache,target=/root/.cache/ccache \
    /workspace/deployment/docker/app/nuitka/build-migrate.sh \
    && ccache --show-stats


# =========================
# Shared runtime foundation
# =========================

FROM python:3.11-slim-bookworm AS runtime-base

WORKDIR /app

# Certificates are required for HTTPS calls to Weave Cloud. libstdc++ is needed
# by the compiled Nuitka executables.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p \
        /var/lib/weave-cbt/identity \
        /var/lib/weave-cbt/media \
        /var/lib/weave-cbt/branding


# =======================================================
# Migration-only runtime used by CI for an early smoke test
# =======================================================

FROM runtime-base AS migration-runtime

COPY --from=migrate-builder \
    /workspace/deployment/docker/app/build/nuitka/migrate/migrate.dist \
    /app/migrate

ENV WEAVE_ALEMBIC_CONFIG=/app/migrate/migrations/alembic.ini

CMD ["/app/migrate/weave-cbt-migrate"]


# ===============================
# Final WEAVE CBT runtime image
# ===============================

FROM runtime-base AS runtime

# Copy each independently compiled artifact into the final runtime image.
COPY --from=api-builder \
    /workspace/deployment/docker/app/build/nuitka/api/api.dist \
    /app/api
COPY --from=worker-builder \
    /workspace/deployment/docker/app/build/nuitka/worker/worker.dist \
    /app/worker
COPY --from=migrate-builder \
    /workspace/deployment/docker/app/build/nuitka/migrate/migrate.dist \
    /app/migrate

# Only built frontend assets are copied; React source and node_modules stay out.
COPY --from=frontend-builder /workspace/frontend/dist /app/web

ENV WEAVE_ALEMBIC_CONFIG=/app/migrate/migrations/alembic.ini

EXPOSE 8000

# API is the default process. Compose overrides this command for worker/migrate.
CMD ["/app/api/weave-cbt-api"]
