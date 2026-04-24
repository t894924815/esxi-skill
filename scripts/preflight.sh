#!/usr/bin/env bash
# preflight.sh — Check if esxi-skill is ready to run.
#
# Exit codes:
#   0 — ready
#   1 — missing prerequisites (see JSON output for details)
#
# Output (stdout): a single JSON object.

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="${ESXI_PROFILE:-default}"
CONF_DIR="${HOME}/.config/esxi-skill"
CONF_FILE="${CONF_DIR}/${PROFILE}.env"
CRED_FILE="${CONF_DIR}/${PROFILE}.cred"

missing=()
details=()

# --- JSON output helper: produce a valid JSON string literal (handles quotes/backslashes) ---
json_str() {
  python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))' "$1"
}

# 1. govc installed?
if command -v govc >/dev/null 2>&1; then
  gv=$(govc version 2>/dev/null | head -1 || echo "unknown")
  details+=("\"govc\": $(json_str "$gv")")
else
  missing+=("govc")
fi

# 2. config file exists?
if [ -f "$CONF_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONF_FILE"
  details+=("\"profile\": $(json_str "$PROFILE")")
  details+=("\"host\": $(json_str "${GOVC_URL:-}")")
  details+=("\"user\": $(json_str "${GOVC_USERNAME:-}")")
else
  missing+=("config")
fi

# 3. credential exists in the appropriate backend for this OS?
SERVICE="${ESXI_CRED_SERVICE:-govc-${GOVC_URL:-}}"
if [ -f "$CONF_FILE" ]; then
  case "$(uname)" in
    Darwin)
      if security find-generic-password \
           -a "${GOVC_USERNAME:-}" -s "$SERVICE" >/dev/null 2>&1; then
        details+=('"keychain": "macos"')
      else
        missing+=("keychain")
      fi
      ;;
    Linux)
      if command -v secret-tool >/dev/null 2>&1 && \
         secret-tool lookup service "$SERVICE" account "${GOVC_USERNAME:-}" >/dev/null 2>&1; then
        details+=('"keychain": "libsecret"')
      elif [ -f "$CRED_FILE" ]; then
        details+=('"keychain": "file"')
      else
        missing+=("keychain")
      fi
      ;;
    *)
      # Unknown OS — only file backend supported
      if [ -f "$CRED_FILE" ]; then
        details+=('"keychain": "file"')
      else
        missing+=("keychain")
      fi
      ;;
  esac
fi

# 4. can we actually connect? Delegate to the g wrapper so we don't
#    duplicate the per-OS credential-lookup logic.
can_connect=false
if [ ${#missing[@]} -eq 0 ]; then
  if ESXI_PROFILE="$PROFILE" "$SCRIPT_DIR/g" about >/dev/null 2>&1; then
    can_connect=true
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
  printf '{'
  printf '"ready": %s' "$ready"
  if [ ${#details[@]} -gt 0 ]; then
    printf ', '
    (IFS=,; printf '%s' "${details[*]}")
  fi
  if [ ${#missing[@]} -gt 0 ]; then
    printf ', "missing": ['
    first=1
    for m in "${missing[@]}"; do
      [ $first -eq 1 ] || printf ', '
      printf '"%s"' "$m"
      first=0
    done
    printf ']'
  fi
  printf '}\n'
}

exit $status
