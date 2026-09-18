# =============================
# Build the React/Vite frontend
# =============================

FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /workspace/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# =========================================
# Compile the Python application with Nuitka
# =========================================

FROM python:3.11-slim-bookworm AS python-builder

WORKDIR /workspace

# Nuitka needs a C compiler and patchelf while producing standalone binaries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        patchelf \
    && rm -rf /var/lib/apt/lists/*

# Install application dependencies first so this expensive layer can be cached.
COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN python -m pip install --no-cache-dir \
    -r /workspace/backend/requirements.txt

# Nuitka is a build-only dependency and is not copied into the runtime image.
COPY deployment/docker/app/nuitka/requirements-build.txt \
    /workspace/deployment/docker/app/nuitka/requirements-build.txt
RUN python -m pip install --no-cache-dir \
    -r /workspace/deployment/docker/app/nuitka/requirements-build.txt

# Source is required only in this builder stage.
COPY backend/ /workspace/backend/
COPY deployment/docker/app/entrypoints/ \
    /workspace/deployment/docker/app/entrypoints/
COPY deployment/docker/app/nuitka/ \
    /workspace/deployment/docker/app/nuitka/

RUN chmod +x \
    /workspace/deployment/docker/app/nuitka/build-api.sh \
    /workspace/deployment/docker/app/nuitka/build-worker.sh \
    /workspace/deployment/docker/app/nuitka/build-migrate.sh

RUN /workspace/deployment/docker/app/nuitka/build-api.sh
RUN /workspace/deployment/docker/app/nuitka/build-worker.sh
RUN /workspace/deployment/docker/app/nuitka/build-migrate.sh


# ======================================
# Prepare compiled artifacts for runtime
# ======================================

RUN set -eu; \
    mkdir -p /runtime/api /runtime/worker /runtime/migrate; \
    API_DIST="$(find /workspace/deployment/docker/app/build/nuitka/api -maxdepth 1 -type d -name '*.dist' -print -quit)"; \
    WORKER_DIST="$(find /workspace/deployment/docker/app/build/nuitka/worker -maxdepth 1 -type d -name '*.dist' -print -quit)"; \
    MIGRATE_DIST="$(find /workspace/deployment/docker/app/build/nuitka/migrate -maxdepth 1 -type d -name '*.dist' -print -quit)"; \
    test -n "${API_DIST}"; \
    test -n "${WORKER_DIST}"; \
    test -n "${MIGRATE_DIST}"; \
    cp -a "${API_DIST}/." /runtime/api/; \
    cp -a "${WORKER_DIST}/." /runtime/worker/; \
    cp -a "${MIGRATE_DIST}/." /runtime/migrate/; \
    test -x /runtime/api/weave-cbt-api; \
    test -x /runtime/worker/weave-cbt-worker; \
    test -x /runtime/migrate/weave-cbt-migrate


# ===============================
# Final WEAVE CBT runtime image
# ===============================

FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Certificates are required for HTTPS calls to Weave Cloud.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Only compiled backend programs are copied into the runtime image.
COPY --from=python-builder /runtime/api /app/api
COPY --from=python-builder /runtime/worker /app/worker
COPY --from=python-builder /runtime/migrate /app/migrate

# Only built frontend assets are copied; React source and node_modules stay out.
COPY --from=frontend-builder /workspace/frontend/dist /app/web

# These directories are mounted on persistent storage by Docker Compose.
RUN mkdir -p \
    /var/lib/weave-cbt/identity \
    /var/lib/weave-cbt/media \
    /var/lib/weave-cbt/branding

ENV WEAVE_ALEMBIC_CONFIG=/app/migrate/migrations/alembic.ini

EXPOSE 8000

# API is the default process. Compose overrides this command for worker/migrate.
CMD ["/app/api/weave-cbt-api"]
