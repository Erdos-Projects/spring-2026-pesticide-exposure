#!/usr/bin/env bash
set -euo pipefail

# Installs this repo's Python dependencies into the currently-active Python
# environment.
#
# This is intentionally "one-shot" (run once per environment) because we want
# a stable, reproducible dependency state before running notebooks/scripts.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_FILE="${REPO_ROOT}/requirements.txt"

echo "Installing project dependencies from: ${REQ_FILE}"

python -m pip install --upgrade pip
python -m pip install -r "${REQ_FILE}"

echo "Dependency install complete."

