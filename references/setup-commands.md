# Password-Storage Command Reference (by OS)

This file documents the **password-step commands** that `esxi.py setup` prints to the user. All install/config work is done automatically by `esxi.py` — only the password storage is manual.

Replace `<HOST>`, `<USER>` with the values you passed to `esxi.py setup`.

---

## macOS

Stored in macOS login Keychain.

**Recommended** — `security` CLI native prompt (interactive, no shell exposure):

```bash
security add-generic-password -a '<USER>' -s 'govc-<HOST>' -U -w
```

Placing `-w` as the last arg without a value makes `security` prompt interactively (hidden input, asks to retype). Documented in `man security`: "Specify -w as the last option to be prompted."

**Alternative** — Keychain Access.app GUI:

```bash
open -a "Keychain Access"
```

`File ▸ New Password Item…`:
- Keychain Item Name: `govc-<HOST>`
- Account Name: `<USER>`
- Password: (type in the native secure field)

---

## Linux — with libsecret (preferred)

Stored in GNOME Keyring / KDE Wallet / other Secret Service implementation.

Prerequisite: `libsecret-tools`:
- `apt install libsecret-tools` (Debian/Ubuntu)
- `dnf install libsecret` (Fedora/RHEL)

```bash
secret-tool store --label='govc: <USER> @ <HOST>' \
  service 'govc-<HOST>' account '<USER>'
```

`secret-tool` prompts via the keyring daemon's own agent. Password never touches the shell.

**GUI alternatives**:
- GNOME: open "Passwords and Keys" (`seahorse`) → Add Password
- KDE: open "KDE Wallet Manager" → Add item
- Attributes: `service=govc-<HOST>`, `account=<USER>`

---

## Linux — no libsecret (file fallback)

Stored in `~/.config/esxi-skill/<profile>.cred` (chmod 600).

```bash
umask 077
read -rs -p 'ESXi password: ' PW && echo
printf '%s' "$PW" > ~/.config/esxi-skill/default.cred
chmod 600 ~/.config/esxi-skill/default.cred
unset PW
```

For stronger security, install `libsecret-tools` and use the libsecret path above.

---

## Windows

**Primary** — Windows Credential Manager via the `keyring` Python package. `esxi.py setup` on Windows **automatically provisions a private venv** at `%LOCALAPPDATA%\esxi-skill\venv\` and installs `keyring` into it. **No global pip install, no `pip install --user`.** Credential entries show up in Windows's "Credential Manager" control panel (Generic Credentials) and are DPAPI-encrypted under the hood.

After `esxi.py setup` finishes, it prints a uniform password command:

```powershell
python .../esxi.py set-password
```

which prompts for the password (hidden) and writes it into Credential Manager via `keyring`.

**Fallback** — if the keyring venv can't be provisioned (offline, pip blocked, corporate policy, etc.), `esxi.py` uses a DPAPI-encrypted hex file at `%APPDATA%\esxi-skill\<profile>.cred`. Password is bound to the current Windows user + current machine. To pre-populate this file without running Python:

```powershell
New-Item -ItemType Directory -Force -Path (Split-Path -Parent "$env:APPDATA\esxi-skill\default.cred") | Out-Null

Read-Host -AsSecureString -Prompt 'ESXi password' |
  ConvertFrom-SecureString |
  Set-Content -LiteralPath "$env:APPDATA\esxi-skill\default.cred" -NoNewline

# Defense-in-depth: restrict NTFS ACL to the current user.
icacls "$env:APPDATA\esxi-skill\default.cred" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

**How it's secure**: `ConvertFrom-SecureString` (no `-Key`) encrypts under DPAPI with the current user's master key. Another Windows user on the same machine — or the same user on a different machine — cannot decrypt. Same cryptographic primitive that Credential Manager uses internally.

**To skip the keyring auto-install** (e.g. in a restricted environment):
```bash
python .../esxi.py setup --host ... --user ... --no-keyring
```

---

## Updating an Existing Password

Same commands as initial setup:
- macOS `security … -U …` updates in place (the `-U` flag).
- `secret-tool store` overwrites entries with the same attributes.
- File-based: just re-run the `read -rs` / `Read-Host` block.

No need to re-run `esxi.py setup` if only the password changed.

---

## Verification

After storing the password:

```bash
python3 ~/.claude/skills/esxi/esxi.py preflight
```

Expect `{"ready": true, ...}`. If `can_connect: false`, the password or network is wrong.
