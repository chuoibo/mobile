#!/usr/bin/env bash
# Point git at the repository's hooks.
#
# A hook that exists but was never installed protects nothing. That is not
# hypothetical here: the repo guard sat in this repository unenabled while
# 12,629 dependency files were committed straight past it.

set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks"
echo "repo guard chạy trước mỗi commit. Bỏ qua bằng --no-verify là tự chịu."
