#=============================#
#Build the React/Vite frontend
#=============================#

FROM node:22-bookworn-slim AS frontend-builder

WORKDIR /workspace/frontend


#copies the frontend dependency file into the current workspace-dir
COPY frontend/package.json .     
COPY frontend/package-lock.json .


#automatically install dependencies from package.json 
RUN npm ci 

#copies the entire frontend files into the current workspace-dir
COPY frontend/ .

#builds the staff and student static files
RUN npm run build 







#=========================================#
#Compile the Python application with Nuitka
#=========================================#


FROM python:3.11-slim-bookworm AS python-builder

WORKDIR /workspace


#Nuitka needs a C compiler to create native Linux binaries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
            build-essential \
            patchelf \
    && rm -rf /var/lib/apt/lists/*



#Install the actual WEAVE backend dependencies first
COPY backend/requirements.txt /workspace/backend/requirements.txt

RUN python -m pip install --no-cache-dir \
    -r /workspace/backend/requirements.txt


#Copy the backend source needed during compilation
COPY backend/       /workspace/backend

#Copy the deployment entrypoints and Nuitka build scripts.
COPY deployment/docker/app/entrypoints/ \
    /workspace/deployment/docker/app/entrypoints/


COPY deployment/docker/app/nuitka/ \
    /workspace/deployment/docker/app/nuitka/


#Make the build scripts executable
#chmod +x is a linux command that makes a file executable by adding the execute permission 
#so a file can be run directly as a program/script rather than being open or read
RUN chmod +x \
    /workspace/deployment/docker/app/nuitka/build-api.sh \
    /workspace/deployment/docker/app/nuitka/build-worker.sh \
    /workspace/deployment/docker/app/nuitka/build-migrate.sh



# Compile all three production programs.
RUN /workspace/deployment/docker/app/nuitka/build-api.sh

RUN /workspace/deployment/docker/app/nuitka/build-worker.sh

RUN /workspace/deployment/docker/app/nuitka/build-migrate.sh





# =========================================#
# Prepare compiled artifacts for runtime
# =========================================#

RUN mkdir -p \
        /runtime/api \
        /runtime/worker \
        /runtime/migrate \
    && API_DIST="$(find /workspace/deployment/docker/app/build/nuitka/api -maxdepth 1 -type d -name '*.dist' -print -quit)" \
    && WORKER_DIST="$(find /workspace/deployment/docker/app/build/nuitka/worker -maxdepth 1 -type d -name '*.dist' -print -quit)" \
    && MIGRATE_DIST="$(find /workspace/deployment/docker/app/build/nuitka/migrate -maxdepth 1 -type d -name '*.dist' -print -quit)" \
    && cp -a "${API_DIST}/." /runtime/api/ \
    && cp -a "${WORKER_DIST}/." /runtime/worker/ \
    && cp -a "${MIGRATE_DIST}/." /runtime/migrate/







#===============================#
#Final WEAVE CBT runtime image
#===============================#

FROM python3.11-slim-bookworm AS runtime

WORKDIR /app


# Certificates are needed for HTTPS connections,
# for example when WEAVE communicates with the cloud API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*





# Copy ONLY the compiled backend programs.
# The original backend Python source is not copied.
COPY --from=python-builder /runtime/api /app/api
COPY --from=python-builder /runtime/worker /app/worker
COPY --from=python-builder /runtime/migrate /app/migrate





# Copy ONLY the built frontend static files.
# React source and node_modules are not copied.
COPY --from=frontend-builder /workspace/frontend/dist /app/web



# Your application expects these persistent directories.
RUN mkdir -p \
    /var/lib/weave-cbt/identity \
    /var/lib/weave-cbt/media \
    /var/lib/weave-cbt/branding






# Tell the compiled migration runner where its Alembic config lives.
ENV WEAVE_ALEMBIC_CONFIG=/app/migrate/migrations/alembic.ini


# FastAPI listens on port 8000.
EXPOSE 8000


# API is the default process.
# Docker Compose will override this for worker and migrate containers.
CMD ["/app/api/weave-cbt-api"]