# Setup Command Templates (by OS)

These are copy-pasteable command blocks Claude should output to the user when setting up esxi-skill. Replace `<HOST>`, `<USER>`, `<1|0>`, `<DC>` with the values collected in chat.

**Claude should never run these via the Bash tool** — they are for the user to paste into their own terminal.

---

## macOS

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

# 3. Store password — pick ONE:

# Option A (recommended): Keychain Access.app
#   open -a "Keychain Access"
#   File ▸ New Password Item…
#     Keychain Item Name: govc-<HOST>
#     Account Name:       <USER>
#     Password:           (type in native secure field)

# Option B: CLI with silent prompt
IFS= read -rs -p "ESXi password: " PW && echo && \
  security add-generic-password -a '<USER>' -s 'govc-<HOST>' -w "$PW" -U && \
  unset PW && echo "✓ saved to Keychain"
```

---

## Linux (with libsecret / GNOME Keyring / KDE Wallet)

```bash
# 1. Install govc
arch=$(uname -m); case $arch in aarch64|arm64) arch=arm64 ;; x86_64) arch=x86_64 ;; esac
curl -fsSL "https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_${arch}.tar.gz" \
  | sudo tar -C /usr/local/bin -xzf - govc

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

# 3. Store password — pick ONE:

# Option A (recommended): GNOME Keyring / KDE Wallet GUI
#   GNOME: open "Passwords and Keys" (seahorse) → Add Password
#   KDE:   open "KDE Wallet Manager" → Add item
#   Set: label=govc-<HOST>, attributes: service=govc-<HOST>, account=<USER>

# Option B: secret-tool CLI (prompts via keyring daemon)
secret-tool store --label="govc: <USER> @ <HOST>" \
  service 'govc-<HOST>' account '<USER>'
```

**Prerequisite for Option B**: `libsecret-tools` installed (`apt install libsecret-tools` on Debian/Ubuntu).

---

## Linux (no keyring — fall back to encrypted file)

```bash
# Same config write as above, then:
read -rs -p "ESXi password: " PW && echo && \
  install -m 600 /dev/stdin ~/.config/esxi-skill/default.cred <<< "$PW" && \
  unset PW && echo "✓ saved to ~/.config/esxi-skill/default.cred (chmod 600)"
```

Better long-term: install `libsecret-tools` and use the keyring.

---

## Windows (PowerShell)

```powershell
# 1. Install govc (via Chocolatey, Scoop, or manual download)
#    Chocolatey:  choco install govc
#    Scoop:       scoop install govc
#    Manual:      https://github.com/vmware/govmomi/releases/latest

# 2. Write config ($HOME\.config\esxi-skill\default.env, still bash-style
#    since the g wrapper uses bash. If running on WSL, use Linux block above.)
New-Item -Type Directory -Force -Path "$HOME\.config\esxi-skill" | Out-Null
@"
export GOVC_URL='<HOST>'
export GOVC_USERNAME='<USER>'
export GOVC_INSECURE=<1|0>
export GOVC_DATACENTER='<DC>'
export ESXI_CRED_SERVICE='govc-<HOST>'
"@ | Set-Content -Path "$HOME\.config\esxi-skill\default.env"

# 3. Store password in Windows Credential Manager
$cred = Get-Credential -UserName '<USER>' -Message 'ESXi password'
cmdkey /generic:"govc-<HOST>" /user:"$($cred.UserName)" /pass:"$($cred.GetNetworkCredential().Password)"
```

The `g` wrapper would need extending to read from Credential Manager on Windows; currently it expects macOS Keychain or Linux libsecret. For now, Windows users are best served running this skill under WSL.

---

## Verification (all OSes)

After setup, always have the user run preflight to confirm:

```bash
~/.claude/skills/esxi/scripts/preflight.sh
```

Expect `{"ready": true, ...}`. If `can_connect: false`, the password or network is wrong.

---

## Updating Password

Same commands as initial setup — the `-U` flag on macOS `security` and the `secret-tool store` command both update existing entries. On Windows, `cmdkey` overwrites an existing credential with the same target.
