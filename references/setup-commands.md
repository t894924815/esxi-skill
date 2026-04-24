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

## Windows (PowerShell)

Stored in `%APPDATA%\esxi-skill\<profile>.cred` with NTFS ACL restricted to the current user.

```powershell
$dir = Split-Path -Parent "$env:APPDATA\esxi-skill\default.cred"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$sec = Read-Host -AsSecureString -Prompt 'ESXi password'
$pw  = [System.Net.NetworkCredential]::new('', $sec).Password
[IO.File]::WriteAllText("$env:APPDATA\esxi-skill\default.cred", $pw)
icacls "$env:APPDATA\esxi-skill\default.cred" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

**Note**: file-based storage. For Windows Credential Manager integration, install `keyring` via `pip install keyring` and extend `esxi.py`. Stronger alternative: run esxi-skill inside WSL.

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
