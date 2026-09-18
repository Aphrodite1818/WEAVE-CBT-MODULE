#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

BACKEND_ROOT="${REPO_ROOT}/backend"

ENTRYPOINT="${APP_DIR}/entrypoints/worker.py"
OPTIONS_FILE="${SCRIPT_DIR}/common-options.txt"

OUTPUT_DIR="${APP_DIR}/build/nuitka/worker"

PYTHON_BIN="${PYTHON_BIN:-python}"

export PYTHONPATH="${BACKEND_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

NUITKA_OPTIONS=()

while IFS= read -r option; do
    [[ -z "${option}" ]] && continue
    [[ "${option}" =~ ^[[:space:]]*# ]] && continue

    NUITKA_OPTIONS+=("${option}")
done < "${OPTIONS_FILE}"

rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

"${PYTHON_BIN}" -m nuitka \
    "${NUITKA_OPTIONS[@]}" \
    --output-dir="${OUTPUT_DIR}" \
    --output-filename="weave-cbt-worker" \
    "${ENTRYPOINT}"