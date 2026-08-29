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

  # One line per FROM: "<image>\t<stage name or empty>".
  #
  # `FROM [--flag ...] <image> [AS <stage>]`. Flags such as
  # `--platform=$BUILDPLATFORM` sit between the instruction and the image, so
  # reading "the first word after FROM" lands on the flag rather than on the
  # thing being pulled -- and then hands a string starting with `--` to grep,
  # which answers with its own usage screen instead of a verdict.
  froms=$(awk '
    { sub(/\r$/, "") }
    toupper($1) != "FROM" { next }
    {
      i = 2
      while (i <= NF && substr($i, 1, 2) == "--") i++
      if (i > NF) next
      stage = ""
      if (i + 2 <= NF && toupper($(i + 1)) == "AS") stage = $(i + 2)
      print $i "\t" stage
    }' "$file")

  # Stage names declared by `FROM <image> AS <name>`. A later `FROM <name>` is a
  # reference to a stage built here, not a registry pull, so it needs no digest.
  stages=$(printf '%s\n' "$froms" | awk -F'\t' 'NF > 1 && $2 != "" {print tolower($2)}')

  while read -r image; do
    [ -n "$image" ] || continue
    lower=$(printf '%s' "$image" | tr '[:upper:]' '[:lower:]')

    # 1. Literal digest: FROM python:3.12-slim@sha256:...
    if printf '%s' "$image" | grep -qE '@sha256:[0-9a-f]{64}$'; then
      continue
    fi

    # 2. Reference to an earlier stage in the same file.
    #    `-e` because an image name is data, not a place to accept options.
    if printf '%s\n' "$stages" | grep -qxF -e "$lower"; then
      continue
    fi

    # 3. Build ARG: the ARG's default value must itself carry a digest.
    if printf '%s' "$image" | grep -qE '^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$'; then
      arg=$(printf '%s' "$image" | tr -d '${}')

      # Every `ARG <name>=<value>` declaration of this name, one per line,
      # written as "=<value>" so that an empty default survives as a line.
      #
      # The value is the single whitespace-delimited word after the `=`, which
      # is what Docker resolves: `ARG X=python:3.12-slim  # was @sha256:...`
      # pulls the mutable tag, the comment notwithstanding. Anchoring the digest
      # to the end of the LINE instead of the end of the VALUE is what let that
      # line through while the gate printed "ok: ... pinned by sha256 digest".
      defaults=$(awk -v name="$arg" '
        { sub(/\r$/, "") }
        toupper($1) != "ARG" { next }
        {
          for (i = 2; i <= NF; i++) {
            if (substr($i, 1, 1) == "#") break
            eq = index($i, "=")
            if (eq > 1 && substr($i, 1, eq - 1) == name) print "=" substr($i, eq + 1)
          }
        }' "$file")

      if [ -z "$defaults" ]; then
        echo "::error file=$file::FROM \$$arg is not digest-pinned -- no 'ARG $arg=<image>@sha256:<64 hex>' declaration in $file" >&2
        status=1
        continue
      fi

      # Every declaration must be pinned, not just the last one. Which
      # declaration wins depends on where each FROM sits between them, so a file
      # that declares the same ARG twice with one value unpinned has at least
      # one FROM pulling a tag whichever way Docker resolves it.
      # A separate flag, not an empty `bad`: `ARG X=` declares an empty default,
      # which is itself unpinned and must not read as "nothing wrong found".
      bad=""
      bad_found=0
      while IFS= read -r declared; do
        value=${declared#=}
        if ! printf '%s' "$value" | grep -qE '@sha256:[0-9a-f]{64}$'; then
          bad=$value
          bad_found=1
          break
        fi
      done <<EOF
$defaults
EOF

      if [ "$bad_found" -eq 0 ]; then
        continue
      fi
      echo "::error file=$file::FROM \$$arg is not digest-pinned -- ARG $arg=$bad has no 'name@sha256:<64 hex>' value" >&2
      status=1
      continue
    fi

    echo "::error file=$file::FROM $image is pinned by tag, not by digest" >&2
    status=1
  done < <(printf '%s\n' "$froms" | cut -f1)

  if [ $status -eq 0 ]; then
    echo "ok: every base image in $file is pinned by sha256 digest"
  fi
done

exit $status
