#!/usr/bin/env bash
# Fail if any base image in a Dockerfile is pulled by a mutable tag.
#
# A tag like `python:3.12-slim` is re-pushed upstream on every patch release, so
# two builds of the same commit can produce different runtimes with nobody
# changing a line. That is the failure this guards: not a vulnerability, a loss
# of reproducibility -- the build stops being a function of the repository.
#
# Fails closed. Anything this script cannot prove is pinned is an error, not a
# pass; an unrecognised form means extend the script, not ignore the case.
#
# Usage: scripts/check_dockerfile_pinning.sh [dockerfile ...]
#        defaults to services/api/Dockerfile
set -euo pipefail

files=("$@")
if [ ${#files[@]} -eq 0 ]; then
  files=("services/api/Dockerfile")
fi

status=0

for file in "${files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "error: $file does not exist" >&2
    status=1
    continue
  fi

  # Stage names declared by `FROM <image> AS <name>`. A later `FROM <name>` is a
  # reference to a stage built here, not a registry pull, so it needs no digest.
  stages=$(grep -oiE '^[[:space:]]*FROM[[:space:]]+\S+[[:space:]]+AS[[:space:]]+\S+' "$file" \
           | awk '{print tolower($NF)}' || true)

  while read -r image; do
    [ -n "$image" ] || continue
    lower=$(printf '%s' "$image" | tr '[:upper:]' '[:lower:]')

    # 1. Literal digest: FROM python:3.12-slim@sha256:...
    if printf '%s' "$image" | grep -qE '@sha256:[0-9a-f]{64}$'; then
      continue
    fi

    # 2. Reference to an earlier stage in the same file.
    if printf '%s\n' "$stages" | grep -qxF "$lower"; then
      continue
    fi

    # 3. Build ARG: the ARG's default value must itself carry a digest.
    if printf '%s' "$image" | grep -qE '^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$'; then
      arg=$(printf '%s' "$image" | tr -d '${}')
      if grep -qE "^[[:space:]]*ARG[[:space:]]+${arg}=.*@sha256:[0-9a-f]{64}[[:space:]]*$" "$file"; then
        continue
      fi
      echo "::error file=$file::FROM \$$arg is not digest-pinned -- ARG $arg has no 'name@sha256:<64 hex>' default" >&2
      status=1
      continue
    fi

    echo "::error file=$file::FROM $image is pinned by tag, not by digest" >&2
    status=1
  done < <(grep -oiE '^[[:space:]]*FROM[[:space:]]+\S+' "$file" | awk '{print $2}')

  if [ $status -eq 0 ]; then
    echo "ok: every base image in $file is pinned by sha256 digest"
  fi
done

exit $status
