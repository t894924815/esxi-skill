#!/usr/bin/env bash
# preflight.sh — Check if esxi-skill is ready to run.
#
# Exit codes:
#   0 — ready
#   1 — missing prerequisites (see JSON output for details)
#
# Output (stdout): a single JSON object.

set -euo pipefail

PROFILE="${ESXI_PROFILE:-default}"
CONF_DIR="${HOME}/.config/esxi-skill"
CONF_FILE="${CONF_DIR}/${PROFILE}.env"

missing=()
details=()

# 1. govc installed?
if command -v govc >/dev/null 2>&1; then
  govc_version=$(govc version 2>/dev/null | head -1 || echo "unknown")
  details+=("\"govc\": \"${govc_version}\"")
else
  missing+=("govc")
fi

# 2. config file exists?
if [ -f "$CONF_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONF_FILE"
  details+=("\"profile\": \"${PROFILE}\"")
  details+=("\"host\": \"${GOVC_URL:-}\"")
  details+=("\"user\": \"${GOVC_USERNAME:-}\"")
else
  missing+=("config")
fi

# 3. keychain entry exists? (only on macOS, only if config loaded)
if [ -f "$CONF_FILE" ] && [ "$(uname)" = "Darwin" ]; then
  if security find-generic-password \
       -a "${GOVC_USERNAME:-}" \
       -s "govc-${GOVC_URL:-}" >/dev/null 2>&1; then
    details+=("\"keychain\": true")
  else
    missing+=("keychain")
  fi
fi

# 4. can we actually connect? (only if everything else is ready)
can_connect=false
if [ ${#missing[@]} -eq 0 ]; then
  PW=$(security find-generic-password \
         -a "$GOVC_USERNAME" -s "govc-$GOVC_URL" -w 2>/dev/null || true)
  if [ -n "$PW" ]; then
    if GOVC_PASSWORD="$PW" govc about >/dev/null 2>&1; then
      can_connect=true
    fi
  fi
fi
details+=("\"can_connect\": ${can_connect}")

# Build output
if [ ${#missing[@]} -eq 0 ] && [ "$can_connect" = "true" ]; then
  status=0
  ready="true"
else
  status=1
  ready="false"
fi

{
  echo -n '{'
  echo -n "\"ready\": ${ready}"
  if [ ${#details[@]} -gt 0 ]; then
    echo -n ', '
    (IFS=,; echo -n "${details[*]}")
  fi
  if [ ${#missing[@]} -gt 0 ]; then
    echo -n ', "missing": ['
    first=1
    for m in "${missing[@]}"; do
      [ $first -eq 1 ] || echo -n ', '
      echo -n "\"${m}\""
      first=0
    done
    echo -n ']'
  fi
  echo '}'
}

exit $status
