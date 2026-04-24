#!/usr/bin/env bash
# setup-interactive.sh — Interactive setup for esxi-skill.
#
# Run this in YOUR OWN terminal. It prompts for host/user/cert/password,
# reads the password silently (no echo, no arg, no chat log), and hands
# off to setup.sh. Password never leaves your terminal.
#
# Usage:
#   bash ~/.claude/skills/esxi/scripts/setup-interactive.sh
#
# Optional env overrides:
#   ESXI_PROFILE=<name>   — write to a non-default profile

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="${ESXI_PROFILE:-default}"
CONF_FILE="$HOME/.config/esxi-skill/$PROFILE.env"

# --- Preload existing defaults (if re-running setup) ---
DEFAULT_HOST=""
DEFAULT_USER="root"
DEFAULT_INSECURE="Y"
DEFAULT_DC="ha-datacenter"

if [ -f "$CONF_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONF_FILE"
  DEFAULT_HOST="${GOVC_URL:-}"
  DEFAULT_USER="${GOVC_USERNAME:-root}"
  DEFAULT_DC="${GOVC_DATACENTER:-ha-datacenter}"
  [ "${GOVC_INSECURE:-1}" = "0" ] && DEFAULT_INSECURE="N" || DEFAULT_INSECURE="Y"
fi

cat <<EOF
┌───────────────────────────────────────────────────────────────┐
│  esxi-skill interactive setup                                 │
│  Profile: $PROFILE
│  Config target: $CONF_FILE
└───────────────────────────────────────────────────────────────┘

Press [Enter] to accept the default in [brackets].

EOF

# --- Prompt for fields ---
read -rp "ESXi / vCenter host [${DEFAULT_HOST:-esxi.lab}]: " HOST
HOST="${HOST:-${DEFAULT_HOST:-esxi.lab}}"

read -rp "Username [$DEFAULT_USER]: " USERNAME
USERNAME="${USERNAME:-$DEFAULT_USER}"

read -rp "Self-signed cert (insecure)? [$DEFAULT_INSECURE/n]: " CERT_ANSWER
CERT_ANSWER="${CERT_ANSWER:-$DEFAULT_INSECURE}"
case "$CERT_ANSWER" in
  [YyTt1]* ) INSECURE=1 ;;
  [NnFf0]* ) INSECURE=0 ;;
  * ) INSECURE=1 ;;
esac

read -rp "Datacenter [$DEFAULT_DC]: " DATACENTER
DATACENTER="${DATACENTER:-$DEFAULT_DC}"

# Silent password read
echo ""
read -rsp "Password (input hidden): " PASSWORD
echo ""
if [ -z "$PASSWORD" ]; then
  read -rsp "Confirm: password is empty — press Ctrl-C to abort, or Enter to proceed: " _
  echo ""
fi

# --- Summary ---
cat <<EOF

Summary:
  Host:        $HOST
  Username:    $USERNAME
  Insecure:    $INSECURE
  Datacenter:  $DATACENTER
  Password:    ($(printf %s "$PASSWORD" | wc -c | tr -d ' ') chars, will be saved to Keychain)

EOF

read -rp "Proceed? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if ! [[ "$CONFIRM" =~ ^[Yy] ]]; then
  echo "Aborted."
  exit 1
fi

# --- Hand off to setup.sh via stdin ---
echo ""
echo "Running setup..."
echo ""
ESXI_PROFILE="$PROFILE" "$SCRIPT_DIR/setup.sh" "$HOST" "$USERNAME" "$INSECURE" "$DATACENTER" <<< "$PASSWORD"

# --- Clear password from memory (best effort) ---
unset PASSWORD

echo ""
echo "✅ Done. You can now ask your AI assistant to run ESXi commands."
echo "   Quick test: $SCRIPT_DIR/g about"
