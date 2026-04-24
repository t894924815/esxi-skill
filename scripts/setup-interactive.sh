#!/usr/bin/env bash
# setup-interactive.sh — Interactive setup for esxi-skill.
#
# This script uses the OS's NATIVE credential input mechanism for the
# password field — not `read -s` in a terminal. Rationale:
#
#   - macOS:  osascript GUI dialog with "hidden answer" (NSSecureTextField).
#             Password is sent over AppleEvent to osascript, then directly
#             into Keychain via `security`. Never echoed in terminal, never
#             in shell history, not accessible via tmux/screen scrollback.
#
#   - Linux:  libsecret (`secret-tool`) if available; the keyring daemon
#             prompts via its own agent (gnome-keyring / KWallet).
#             Falls back to `zenity --password` GUI dialog.
#             Terminal `read -rsp` only as absolute last resort.
#
#   - Other:  terminal `read -rsp` (least secure, but standard).
#
# Non-sensitive fields (host/user/cert/datacenter) are still collected via
# regular terminal prompts since they have no confidentiality requirement.
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

Non-sensitive fields are asked here. The password is collected via the
OS's native secure-input mechanism (not via terminal).

Press [Enter] to accept defaults [in brackets].

EOF

# --- Prompt for non-sensitive fields ---
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

# --- Summary before secure password step ---
cat <<EOF

Non-sensitive fields:
  Host:        $HOST
  Username:    $USERNAME
  Insecure:    $INSECURE
  Datacenter:  $DATACENTER

EOF

read -rp "Proceed to password entry? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if ! [[ "$CONFIRM" =~ ^[Yy] ]]; then
  echo "Aborted."
  exit 1
fi

# ============================================================================
# PASSWORD STEP — OS-native secure input, write directly to system keychain.
# We do NOT capture the password into a shell variable for the macOS path.
# ============================================================================

KEYCHAIN_SERVICE="govc-$HOST"

case "$(uname)" in
  Darwin)
    # --- macOS: use osascript secure dialog + security CLI ---
    # The password is collected by osascript's hidden-answer dialog (a native
    # NSSecureTextField). We use `do shell script` inside osascript so the
    # password flows from dialog → AppleScript → `security` CLI without ever
    # passing through the user's shell environment or command history.
    echo ""
    echo "→ macOS Keychain: a password dialog will appear."
    echo "   Enter your ESXi password there. The password will be saved"
    echo "   directly to your login Keychain (service=$KEYCHAIN_SERVICE,"
    echo "   account=$USERNAME) without ever touching this shell."
    echo ""

    osascript <<APPLESCRIPT 2>/dev/null
set theAccount to "$USERNAME"
set theService to "$KEYCHAIN_SERVICE"
set thePW to text returned of (display dialog "ESXi password for " & theAccount & " @ $HOST" default answer "" with icon caution with hidden answer buttons {"Cancel", "Save"} default button "Save")
-- security will prompt for Keychain access if required.
do shell script "/usr/bin/security add-generic-password -a " & quoted form of theAccount & " -s " & quoted form of theService & " -w " & quoted form of thePW & " -U"
APPLESCRIPT

    if [ $? -ne 0 ]; then
      echo "❌ Keychain save failed or cancelled."
      exit 2
    fi
    echo "✅ Password saved to Keychain."
    ;;

  Linux)
    # --- Linux: prefer libsecret (secret-tool) or zenity GUI ---
    if command -v secret-tool >/dev/null 2>&1; then
      echo ""
      echo "→ Linux keyring (libsecret): use your keyring's prompter to enter password."
      echo "   Attribute: service=$KEYCHAIN_SERVICE account=$USERNAME"
      echo ""
      secret-tool store --label="govc: $USERNAME @ $HOST" \
        service "$KEYCHAIN_SERVICE" \
        account "$USERNAME"
      # secret-tool reads password from tty but does not echo it, and stores
      # directly in keyring via DBus.
    elif command -v zenity >/dev/null 2>&1; then
      echo "→ GUI password dialog (zenity)..."
      PW=$(zenity --password --title="ESXi password for $USERNAME @ $HOST" 2>/dev/null) || {
        echo "❌ Cancelled."
        exit 2
      }
      # Store in a simple encrypted file for now; user should use a proper keyring
      CRED_FILE="$HOME/.config/esxi-skill/$PROFILE.cred"
      mkdir -p "$(dirname "$CRED_FILE")"
      umask 077
      printf '%s' "$PW" > "$CRED_FILE"
      chmod 600 "$CRED_FILE"
      unset PW
      echo "⚠️  Password stored at $CRED_FILE (chmod 600)."
      echo "   For better security, install libsecret-tools and re-run this setup."
    else
      # Terminal fallback
      echo ""
      echo "⚠️  No libsecret or zenity found. Falling back to terminal input."
      echo "   Install libsecret-tools (apt/dnf) for native keyring support."
      echo ""
      read -rsp "Password: " PW
      echo ""
      CRED_FILE="$HOME/.config/esxi-skill/$PROFILE.cred"
      mkdir -p "$(dirname "$CRED_FILE")"
      umask 077
      printf '%s' "$PW" > "$CRED_FILE"
      chmod 600 "$CRED_FILE"
      unset PW
    fi
    ;;

  MINGW*|MSYS*|CYGWIN*)
    # --- Windows via Git Bash / WSL: recommend native PowerShell path ---
    echo ""
    echo "→ Windows: run this in PowerShell instead (uses Credential Manager):"
    echo ""
    echo "  \$cred = Get-Credential -UserName '$USERNAME' -Message 'ESXi password'"
    echo "  cmdkey /generic:$KEYCHAIN_SERVICE /user:\$cred.UserName /pass:\$cred.GetNetworkCredential().Password"
    echo ""
    echo "Then re-run this script (non-password steps only) to write the config file."
    exit 0
    ;;

  *)
    echo "⚠️  Unsupported OS: $(uname). Falling back to terminal input."
    read -rsp "Password: " PW
    echo ""
    CRED_FILE="$HOME/.config/esxi-skill/$PROFILE.cred"
    mkdir -p "$(dirname "$CRED_FILE")"
    umask 077
    printf '%s' "$PW" > "$CRED_FILE"
    chmod 600 "$CRED_FILE"
    unset PW
    ;;
esac

# --- Write config file (no password — that's in keychain) ---
echo ""
echo "→ Writing config..."

mkdir -p "$(dirname "$CONF_FILE")"
chmod 700 "$(dirname "$CONF_FILE")"
cat > "$CONF_FILE" <<EOF
# esxi-skill profile: $PROFILE
# Generated by setup-interactive.sh — edit at your own risk.
# Password location:
EOF
case "$(uname)" in
  Darwin) echo "#   macOS Keychain (service=$KEYCHAIN_SERVICE account=$USERNAME)" >> "$CONF_FILE" ;;
  Linux)
    if command -v secret-tool >/dev/null 2>&1; then
      echo "#   libsecret (service=$KEYCHAIN_SERVICE account=$USERNAME)" >> "$CONF_FILE"
    else
      echo "#   File: $HOME/.config/esxi-skill/$PROFILE.cred (chmod 600)" >> "$CONF_FILE"
    fi
    ;;
esac
cat >> "$CONF_FILE" <<EOF
export GOVC_URL='$HOST'
export GOVC_USERNAME='$USERNAME'
export GOVC_INSECURE=$INSECURE
export GOVC_DATACENTER='$DATACENTER'
export ESXI_CRED_BACKEND='$(uname)'
export ESXI_CRED_SERVICE='$KEYCHAIN_SERVICE'
EOF
chmod 600 "$CONF_FILE"
echo "✅ Config written: $CONF_FILE"

# --- Ensure govc is installed ---
if ! command -v govc >/dev/null 2>&1; then
  echo ""
  echo "→ Installing govc..."
  case "$(uname)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        brew install govc
      else
        echo "❌ Homebrew not found. Install brew first, then re-run."
        exit 3
      fi
      ;;
    Linux)
      arch=$(uname -m)
      case "$arch" in
        x86_64) arch="x86_64" ;;
        aarch64|arm64) arch="arm64" ;;
        *) echo "❌ Unsupported Linux arch: $arch"; exit 3 ;;
      esac
      tmp=$(mktemp -d); trap "rm -rf $tmp" EXIT
      curl -fsSL "https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_${arch}.tar.gz" \
        | tar -C "$tmp" -xzf - govc
      [ -w /usr/local/bin ] && mv "$tmp/govc" /usr/local/bin/govc \
                            || sudo mv "$tmp/govc" /usr/local/bin/govc
      chmod +x /usr/local/bin/govc
      ;;
  esac
fi
echo "✅ govc: $(govc version 2>&1 | head -1)"

# --- Test connection via the wrapper ---
echo ""
echo "→ Testing connection with wrapper..."
if "$SCRIPT_DIR/g" about >/dev/null 2>&1; then
  echo "✅ Connection OK."
  echo ""
  "$SCRIPT_DIR/g" about | sed 's/^/  /'
else
  echo "❌ Connection test failed. Check host / credentials."
  echo "   Try: $SCRIPT_DIR/g about"
  exit 4
fi

echo ""
echo "🎉 Setup complete. You can now ask your AI assistant to run ESXi commands."
