#!/usr/bin/env bash

set -euo pipefail

# Where this script itself lives:
# deployment/docker/app/nuitka/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# deployment/docker/app/
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Repository root
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

# backend/ is the Python import root for the `app` package.
BACKEND_ROOT="${REPO_ROOT}/backend"

# The Python program Nuitka will compile.
ENTRYPOINT="${APP_DIR}/entrypoints/api.py"

# Shared Nuitka settings.
OPTIONS_FILE="${SCRIPT_DIR}/common-options.txt"

# Where Nuitka should place the compiled result.
OUTPUT_DIR="${APP_DIR}/build/nuitka/api"

# Allow us to override Python later if necessary.
PYTHON_BIN="${PYTHON_BIN:-python}"

# Make backend/app importable as `app`.
export PYTHONPATH="${BACKEND_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

# Read each non-empty, non-comment line from common-options.txt.
NUITKA_OPTIONS=()

while IFS= read -r option; do
    [[ -z "${option}" ]] && continue
    [[ "${option}" =~ ^[[:space:]]*# ]] && continue

    NUITKA_OPTIONS+=("${option}")
done < "${OPTIONS_FILE}"

# Start with a clean build directory.
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Compile the API entrypoint.
"${PYTHON_BIN}" -m nuitka \
    "${NUITKA_OPTIONS[@]}" \
    --output-dir="${OUTPUT_DIR}" \
    --output-filename="weave-cbt-api" \
    "${ENTRYPOINT}"