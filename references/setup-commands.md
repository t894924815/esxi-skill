# Password-Storage Command Reference (by OS)

`esxi.py setup` prints **one** of the following blocks to the user — whichever matches the current OS. The user pastes it into their own terminal. `esxi.py` never executes it and never sees the password.

Replace `<USER>` / `<HOST>` with the values you passed to `esxi.py setup`.

---

## macOS

Stored in login Keychain.

```bash
security add-generic-password -a '<USER>' -s 'govc-<HOST>' -U -w
```

Trailing `-w` with no value makes `security` prompt interactively (hidden input, asks to retype). Documented in `man security`: *"Specify -w as the last option to be prompted."* The password flows from TTY directly into Keychain via `security`'s C API — it never touches the shell, never enters Python, never appears in argv.

`esxi.py g` reads it back with `security find-generic-password -a <USER> -s govc-<HOST> -w`.

---

## Linux — with libsecret (`secret-tool`)

Stored in GNOME Keyring / KDE Wallet / other Secret Service implementation.

```bash
secret-tool store --label='govc: <USER> @ <HOST>' \
  service 'govc-<HOST>' account '<USER>'
```

Prompts via the keyring daemon itself (DBus IPC to the daemon); password never touches the shell. `esxi.py g` reads it back with `secret-tool lookup service govc-<HOST> account <USER>`.

Prerequisite: `libsecret-tools` package:
- `apt install libsecret-tools` — Debian/Ubuntu
- `dnf install libsecret` — Fedora/RHEL
- `apk add libsecret` — Alpine

---

## Linux — without libsecret

**esxi.py deliberately refuses to configure a keychain backend in this case.** We do NOT fall back to a chmod-600 plaintext file, because its UX looks almost identical to the Windows DPAPI block below, but its security is qualitatively worse (plaintext on disk vs. ciphertext on disk).

**Options**:

### (a) Install libsecret-tools and re-run setup (recommended)
See the package list above. Then re-run `python3 .../esxi.py setup --host ... --user ...`.

### (b) One-off / CI use: `GOVC_PASSWORD` env var
```bash
export GOVC_PASSWORD='...'
python3 .../esxi.py g ls vm
```

`esxi.py g` checks `$GOVC_PASSWORD` **before** the keychain lookup. The password lives only in that shell's env; nothing is persisted. Suitable for CI secrets, container `-e GOVC_PASSWORD=...`, short interactive sessions.

---

## Windows

Stored as a DPAPI-encrypted hex string in `%APPDATA%\esxi-skill\<profile>.cred`, with NTFS ACL restricted to the current user.

```powershell
$cf = '%APPDATA%\esxi-skill\default.cred'   # actual path printed by setup
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $cf) | Out-Null
Read-Host -AsSecureString -Prompt 'ESXi password' |
  ConvertFrom-SecureString |
  Set-Content -LiteralPath $cf -NoNewline
icacls $cf /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

**How it's secure**:
- `Read-Host -AsSecureString` hides input; stores result as `SecureString` (obfuscated in PowerShell memory).
- `ConvertFrom-SecureString` (no `-Key`) encrypts under **DPAPI** (Data Protection API), binding ciphertext to the current Windows user + current machine.
- `Set-Content` writes the hex ciphertext to disk. **Plaintext never hits disk.**
- Another user on the same machine — even an administrator not running as you — cannot decrypt without your DPAPI master key. Same user on a different machine also cannot decrypt (no roaming).
- `icacls` is defense-in-depth: reduces file visibility below what DPAPI already guarantees.

`esxi.py g` reads it back by subprocessing PowerShell: `ConvertTo-SecureString $hex` → `[Runtime.InteropServices.Marshal]::SecureStringToBSTR` → `PtrToStringBSTR`, then zeros the BSTR in `finally`.

### Future work — Windows Credential Manager

DPAPI file and Windows Credential Manager share the same cryptographic primitive (DPAPI). The file approach's only real downside vs. Credential Manager is lack of GUI visibility: you can't see the entry in the "Credential Manager" control panel.

If GUI management becomes important, the upgrade path is to extend `esxi.py` to call `CredWrite` / `CredRead` directly via stdlib `ctypes`. This keeps the "no pip dependencies" rule intact. We chose not to do this yet because the file approach is simpler, verifiable, and cryptographically equivalent.

---

## Updating an Existing Password

Same commands. `security … -U …` updates in place, `secret-tool store` overwrites entries with matching attributes, the PowerShell block overwrites the file. No need to rerun `esxi.py setup` for a password change.

---

## Verification

After storing the password:

```bash
python3 ~/.claude/skills/esxi/esxi.py preflight
```

Expect `{"ready": true, ...}`. If `can_connect: false`, the password or network is wrong.
