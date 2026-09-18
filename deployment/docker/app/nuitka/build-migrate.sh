#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

BACKEND_ROOT="${REPO_ROOT}/backend"

ENTRYPOINT="${APP_DIR}/entrypoints/migrate.py"
OPTIONS_FILE="${SCRIPT_DIR}/common-options.txt"

OUTPUT_DIR="${APP_DIR}/build/nuitka/migrate"

PYTHON_BIN="${PYTHON_BIN:-python}"

# Allow imports such as:
# from app.core.settings import settings
export PYTHONPATH="${BACKEND_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"


# Read shared Nuitka options.
NUITKA_OPTIONS=()

while IFS= read -r option; do
    [[ -z "${option}" ]] && continue
    [[ "${option}" =~ ^[[:space:]]*# ]] && continue

    NUITKA_OPTIONS+=("${option}")
done < "${OPTIONS_FILE}"


# Start with a clean build.
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"


# Compile the migration runner.
"${PYTHON_BIN}" -m nuitka \
    "${NUITKA_OPTIONS[@]}" \
    --output-dir="${OUTPUT_DIR}" \
    --output-filename="weave-cbt-migrate" \
    "${ENTRYPOINT}"


# Find the standalone .dist directory Nuitka created.
DIST_DIR="$(find "${OUTPUT_DIR}" \
    -maxdepth 1 \
    -type d \
    -name "*.dist" \
    -print \
    -quit)"

if [[ -z "${DIST_DIR}" ]]; then
    echo "ERROR: Nuitka standalone output directory was not found."
    exit 1
fi


# Create the migration bundle beside the compiled executable.
MIGRATION_DIR="${DIST_DIR}/migrations"

mkdir -p "${MIGRATION_DIR}"


# Copy Alembic configuration and migration files.
cp "${BACKEND_ROOT}/alembic.ini" "${MIGRATION_DIR}/alembic.ini"
cp -R "${BACKEND_ROOT}/alembic" "${MIGRATION_DIR}/alembic"


# Alembic must be allowed to discover .pyc-only revision files.
if grep -Eq '^[[:space:]]*sourceless[[:space:]]*=' \
    "${MIGRATION_DIR}/alembic.ini"; then

    sed -i -E \
        's/^[[:space:]]*sourceless[[:space:]]*=.*$/sourceless = true/' \
        "${MIGRATION_DIR}/alembic.ini"
else
    sed -i \
        '/^\[alembic\]/a sourceless = true' \
        "${MIGRATION_DIR}/alembic.ini"
fi


# Compile Alembic Python files into bytecode files next to their source.
"${PYTHON_BIN}" -m compileall \
    -b \
    -q \
    "${MIGRATION_DIR}/alembic"


# Remove the original Python migration source files.
find "${MIGRATION_DIR}/alembic" \
    -type f \
    -name "*.py" \
    -delete


echo "Migration build created at:"
echo "${DIST_DIR}"