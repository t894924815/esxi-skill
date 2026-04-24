# Setup Command Templates (by OS)

This file documents the **split of responsibility** between Claude and the user, with OS-specific command templates.

**Core rule**: Claude auto-runs steps 1 and 2 (install + write config). The user runs step 3 (store password) in their own terminal. See `SKILL.md` § *Step 2 — First-Time Setup*.

Replace `<HOST>`, `<USER>`, `<1|0>`, `<DC>` with the values Claude collected from the user in chat.

---

## macOS

### Steps 1 & 2 — Claude runs these via the Bash tool (auto)

```bash
# 1. Install govc
command -v govc >/dev/null || brew install govc

# 2. Write non-sensitive config
mkdir -p ~/.config/esxi-skill && chmod 700 ~/.config/esxi-skill
cat > ~/.config/esxi-skill/default.env <<'EOF'
export GOVC_URL='<HOST>'
export GOVC_USERNAME='<USER>'
export GOVC_INSECURE=<1|0>
export GOVC_DATACENTER='<DC>'
export ESXI_CRED_SERVICE='govc-<HOST>'
EOF
chmod 600 ~/.config/esxi-skill/default.env
```

### Step 3 — User runs ONE of these in their own terminal

**Option A (recommended)** — `security` CLI native prompt, no shell exposure:

```bash
security add-generic-password -a '<USER>' -s 'govc-<HOST>' -U -w
```

Placing `-w` as the last arg without a value makes `security` prompt interactively (not echoed, asks to retype for confirmation). Documented in `man security`: "Specify -w as the last option to be prompted."

**Option B** — Keychain Access.app GUI:

```bash
open -a "Keychain Access"
```

Then `File ▸ New Password Item…`:
- Keychain Item Name: `govc-<HOST>`
- Account Name: `<USER>`
- Password: (type in the native secure field)

---

## Linux (with libsecret / GNOME Keyring / KDE Wallet)

### Steps 1 & 2 — Claude runs these via the Bash tool (auto)

```bash
# 1. Install govc
command -v govc >/dev/null || {
  arch=$(uname -m); case $arch in aarch64|arm64) arch=arm64 ;; x86_64) arch=x86_64 ;; esac
  curl -fsSL "https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_${arch}.tar.gz" \
    | sudo tar -C /usr/local/bin -xzf - govc
}

# 2. Write non-sensitive config
mkdir -p ~/.config/esxi-skill && chmod 700 ~/.config/esxi-skill
cat > ~/.config/esxi-skill/default.env <<'EOF'
export GOVC_URL='<HOST>'
export GOVC_USERNAME='<USER>'
export GOVC_INSECURE=<1|0>
export GOVC_DATACENTER='<DC>'
export ESXI_CRED_SERVICE='govc-<HOST>'
EOF
chmod 600 ~/.config/esxi-skill/default.env
```

### Step 3 — User runs ONE of these in their own terminal

**Option A (libsecret, recommended)** — prompts via the keyring daemon; password goes through DBus, not the shell:

```bash
secret-tool store --label="govc: <USER> @ <HOST>" \
  service 'govc-<HOST>' account '<USER>'
```

Prerequisite: `libsecret-tools` installed (`apt install libsecret-tools` on Debian/Ubuntu; `dnf install libsecret` on Fedora).

**Option B (GUI keyring)**:
- GNOME: open "Passwords and Keys" (`seahorse`) → Add Password
- KDE: open "KDE Wallet Manager" → Add item
- Set: label=`govc-<HOST>`, attributes: `service=govc-<HOST>`, `account=<USER>`

---

## Linux (no keyring — chmod-600 file fallback)

If `libsecret` is unavailable and you don't want to install it, the `g` wrapper falls back to reading from `~/.config/esxi-skill/<profile>.cred` (chmod 600).

### Step 3 — User runs in their own terminal

```bash
umask 077
read -rs -p "ESXi password: " PW && echo
printf '%s' "$PW" > ~/.config/esxi-skill/default.cred
chmod 600 ~/.config/esxi-skill/default.cred
unset PW
```

**Better long-term**: install `libsecret-tools` and use Option A above.

---

## Windows (PowerShell)

The `g` wrapper does not natively support Windows Credential Manager. Recommended: run this skill inside WSL (then follow the Linux section). If you must run on pure Windows/PowerShell, you'd need to extend the `g` wrapper to call `cmdkey` — not supported out of the box.

---

## Verification (all OSes)

After all three steps are done, Claude will run preflight to confirm:

```bash
~/.claude/skills/esxi/scripts/preflight.sh
```

Expect `{"ready": true, ...}`. If `can_connect: false`, the password or network is wrong — re-run the password step.

---

## Updating Password

Same commands as initial step 3. The `-U` flag on macOS `security` and the `secret-tool store` command both update existing entries in place. Claude does not need to be involved in password rotation.
