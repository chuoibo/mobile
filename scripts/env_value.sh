#!/bin/sh
# What value Compose will actually see for a named variable. Nothing else.
#
#   env_value.sh GEMINI_API_KEY        -> prints the effective value, or nothing
#
# Extracted from check_ai_key.sh when a second key needed the same answer
# (MOBILE_PERSON_ID_KEY, bug-140342). Two copies of a dotenv parser is two
# chances to disagree with Compose, and disagreeing with Compose is the whole
# of the bug this logic was written to fix: a gate that told somebody their key
# was missing while it sat in the container working fine. A gate that fires on
# correct behaviour gets switched off, and a switched-off gate is not there on
# the day it would have been right.
#
# Compose resolves `${NAME:-}` in docker-compose.yml from TWO sources: the shell
# environment, and `.env` in the project directory. Precedence below is
# Compose's, measured against `docker compose config`:
#   shell variable set, even to empty -> that value wins, `.env` is not consulted
#   shell variable unset              -> whatever `.env` assigns, if anything
#
# `.env` is read relative to THIS script rather than to the caller's directory,
# because that is where docker-compose.yml lives and Compose loads `.env` from
# the compose file's directory.
#
# Never echoes the name of the variable, never explains, never warns. Callers
# decide what a missing value means; this only reports. Always exits 0 -- a
# missing value is an answer, not a failure.

name=${1:?usage: env_value.sh VARIABLE_NAME}

# `eval` rather than indirect expansion: POSIX sh has no ${!name}, and this
# has to run under dash as well as bash.
if eval "[ \"\${${name}+set}\" = set ]"; then
  eval "printf '%s' \"\$${name}\""
  exit 0
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd) || exit 0
env_file="$repo_root/.env"
[ -r "$env_file" ] || exit 0

# dotenv semantics, kept narrow on purpose: skip comments, allow an `export`
# prefix, drop one layer of matching quotes, last assignment wins. Anything
# fancier would be guessing at Compose's parser instead of agreeing with it.
awk -v q="'" -v name="$name" '
  { line = $0; sub(/^[ \t]*/, "", line) }
  line ~ /^#/ { next }
  { sub(/^export[ \t]+/, "", line) }
  index(line, name) != 1 { next }
  {
    rest = substr(line, length(name) + 1)
    sub(/^[ \t]*/, "", rest)
    if (index(rest, "=") != 1) next
    sub(/^=/, "", rest)
    sub(/[ \t\r]+$/, "", rest)
    first = substr(rest, 1, 1); last = substr(rest, length(rest), 1)
    if (length(rest) > 1 && first == last && (first == "\"" || first == q))
      rest = substr(rest, 2, length(rest) - 2)
    value = rest
  }
  END { printf "%s", value }
' "$env_file"
