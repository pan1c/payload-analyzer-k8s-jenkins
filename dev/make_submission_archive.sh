#!/bin/bash
# Archive the project for submission according to the challenge requirements.
# Python solution: all code is in Python.
# Includes: only files tracked by git (git ls-files), i.e., respects .gitignore and .dockerignore if they are in the repo.

set -e

ARCHIVE_NAME="payload-analyzer-submission-$(date +%Y%m%d)-python"

# Clean up Python cache files before archiving
find app/ tests/ -type d -name '__pycache__' -exec rm -rf {} +
find app/ tests/ -type f -name '*.pyc' -delete

cd "$(dirname "$0")/.."

# Use zip instead of tar, exclude macOS resource fork files (._*)
git ls-files -z | grep -zv '^\._' | xargs -0 zip -q "$ARCHIVE_NAME.zip"

echo "Created archive: $ARCHIVE_NAME.zip"
