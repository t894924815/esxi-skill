---
name: esxi
description: "VMware ESXi / vSphere management via govc CLI. Use when: managing ESXi hosts or vCenter, VM lifecycle operations (create/clone/power/delete), snapshot management, datastore operations, network/port group config, host inventory queries, ISO/OVA import, VMDK operations, or any vSphere automation task. TRIGGER when: user mentions ESXi, vSphere, vCenter, govc, VMware VM, .vmx, .vmdk, snapshot, datastore, or wants to automate VMware infrastructure. Prefer govc over PowerCLI for LLM-driven automation (structured JSON output, fast startup, Unix-native)."
---

# VMware ESXi / vSphere Management

Manage VMware ESXi hosts and vCenter via `govc` — VMware's official Go CLI built on `govmomi`. Optimized for LLM-driven automation: structured JSON output, zero-dependency binary, Unix-native.

## Platform Support

The implementation is **a single Python 3 module** (`esxi.py`). Python 3.7+ is required on all platforms.

| Platform | Status | govc install | Credential backend |
|---|---|---|---|
| **macOS** | Primary, tested | `brew install govc` (auto) | login Keychain via `security` |
| **Linux** | Best-effort (untested end-to-end) | GitHub tarball to `/usr/local/bin` or `~/.local/bin` (auto) | libsecret (`secret-tool`) if installed; else chmod-600 cred file |
| **Linux** (no libsecret) | **Not supported** by default | same | esxi-skill deliberately refuses to fall back to a plaintext file. Install libsecret-tools, OR set `GOVC_PASSWORD` env var per session |
| **Windows** | Supported | Manual (`winget` / `scoop` / `choco`) | **DPAPI-encrypted hex file** at `%APPDATA%\esxi-skill\<profile>.cred`, written by PowerShell's native `Read-Host -AsSecureString \| ConvertFrom-SecureString`. Plaintext never hits disk; only the same Windows user on the same machine can decrypt. See `references/setup-commands.md` for future Credential Manager work. |

---

## 🚀 Before Running Any ESXi Command (CRITICAL)

This skill is implemented in a single Python module `esxi.py` at the skill root. There is **no shell wrapper** — Claude invokes it directly.

### Step 0 — Verify Python 3 is available

Before anything else:

```bash
python3 --version   # or: python --version
```

If Python 3 is missing, tell the user to install it (do NOT try to auto-install Python — that's an OS-level concern). Per-OS install hints:

| OS | Install command |
|---|---|
| macOS | `brew install python3` (or `xcode-select --install`) |
| Debian/Ubuntu | `sudo apt install python3` |
| Fedora/RHEL | `sudo dnf install python3` |
| Alpine | `apk add python3` |
| Windows | `winget install Python.Python.3` (or Microsoft Store) |

### Step 1 — Preflight

Run the preflight subcommand:

```bash
python3 ~/.claude/skills/esxi/esxi.py preflight
```

Output is a JSON object:
- `{"ready": true, ...}` → proceed to the actual user request using `esxi.py g <args>`
- `{"ready": false, "missing": [...]}` → follow **First-Time Setup** below

### Step 2 — First-Time Setup (when preflight returns ready=false)

The `missing` field lists what's absent. Possible values: `govc`, `config`, `keychain`.

**🔐 CRITICAL SECURITY RULES:**

- DO NOT ask the user for their password in chat.
- DO NOT auto-trigger GUI dialogs, `read -rsp` prompts, or anything that spawns interactive input from a subprocess Claude started.
- DO NOT include, echo, or reference any real password in:
  - any file written to disk (commit, script, log, tempfile)
  - any `git commit -m` message or PR description
  - any response shown to the user (redact with `<redacted>` if ever surfaced from a tool error)
- DO NOT send the password to external agents (codex, other LLMs) for review — review the code, not the runtime state.
- Claude's role here is purely **advisory**: print copy-pasteable commands for the user to review and run themselves in their own terminal. The user chooses the input method for the password (Keychain Access.app, OS password manager, or a CLI prompt they themselves type). Claude never sees or handles the password.

**CORE PRINCIPLE — Split of Responsibility**:

| Action | Who does it | Why |
|---|---|---|
| Install govc | **Claude auto-runs** `esxi.py setup` | No secret; standard package install |
| Write config file (host/user/cert/dc) | **Claude auto-runs** `esxi.py setup` | Values are non-sensitive; user already told Claude them |
| Store password | **USER runs** in their own terminal | Password must never pass through Claude |

Only the password step is handed back to the user. Everything else is handled by a single `esxi.py setup` invocation, which prints the OS-appropriate password command for the user to run.

**What Claude MUST do, in order**:

1. **Verify Python 3** (Step 0 above). If missing, stop and help the user install it.

2. **Run preflight**:
   ```bash
   python3 ~/.claude/skills/esxi/esxi.py preflight
   ```

3. **If preflight reports `missing: ["govc", "config"]` (first-time setup), ask the user for the non-sensitive fields** (one short chat prompt; wait for reply):
   - ESXi / vCenter host (e.g. `esxi.lab` or `10.0.0.2`)
   - Username (default `root`)
   - Self-signed cert? y/n (→ `--insecure 1` or `0`)
   - Datacenter (default `ha-datacenter` for standalone ESXi)

4. **Run setup** (Claude invokes this via Bash; it auto-installs govc and writes config, then PRINTS the OS-appropriate password command):
   ```bash
   python3 ~/.claude/skills/esxi/esxi.py setup \
     --host <HOST> --user <USER> --insecure <1|0> --datacenter <DC>
   ```

5. **Relay the password command to the user.** The output of `esxi.py setup` contains a block between `━━━` lines — this is what the user must run in their own terminal. Just show the user that block verbatim. Do NOT run it yourself.

6. **Wait for the user to confirm** ("done"/"好了"/etc.). Don't run anything else while waiting.

7. **Re-run preflight**. If `ready: true`, proceed to Step 3 (run the actual user request). If still failing, show the JSON and help debug.

**Password command printed by `esxi.py setup` (one per OS)**:

| OS | Command |
|---|---|
| **macOS** | `security add-generic-password -a <USER> -s govc-<HOST> -U -w` — security's own interactive prompt; password flows TTY → security C API → Keychain. Never enters Python. |
| **Linux + libsecret** | `secret-tool store --label='…' service govc-<HOST> account <USER>` — prompts via keyring daemon (GNOME Keyring / KDE Wallet / etc.). |
| **Linux no libsecret** | esxi.py refuses to configure a credential store. User must install `libsecret-tools`, or set `GOVC_PASSWORD` env var per session. |
| **Windows** | PowerShell block: `Read-Host -AsSecureString \| ConvertFrom-SecureString \| Set-Content <cred>` + `icacls` ACL. Stores DPAPI-encrypted hex (not plaintext). |

**Critical design decision**: `esxi.py` is a **read-only credential consumer**. It never writes passwords. The commands it prints to the user are OS-native CLIs the user can audit in seconds. This avoids the two failure modes a `set-password` subcommand would have:
1. **Path portability** — `python3 <absolute-path>/esxi.py set-password` breaks when the skill is moved or reinstalled elsewhere.
2. **Trust** — users shouldn't have to audit an LLM-recommended Python script before typing their password into it.

**Why this split**:
- **Auto for non-secrets** = less friction. Typing `brew install govc` and a multi-line heredoc by hand would annoy users for no security gain.
- **User-manual for password via native OS CLI** = the password never passes through Claude's chat log, Bash tool calls, Python process memory, or any file esxi.py wrote.
- The `g` wrapper reads the password from the OS keychain on each invocation; Claude doesn't need to know it.
- For CI / containers / Linux without libsecret: `GOVC_PASSWORD` env var is the escape hatch. `esxi.py g` checks `$GOVC_PASSWORD` before the keychain lookup.

### Step 3 — Run the Actual Request

Use the `g` subcommand, not raw `govc`:

```bash
python3 ~/.claude/skills/esxi/esxi.py g ls vm
python3 ~/.claude/skills/esxi/esxi.py g vm.info -json 'web-01'
python3 ~/.claude/skills/esxi/esxi.py g about
```

`esxi.py g` reads config + pulls password from the OS keychain, builds a minimal env, and `os.execvpe`'s to govc. The Python process is replaced — the password only lives in govc's env after exec.

### Multi-profile (optional)

For multiple ESXi hosts, use `--profile` or `ESXI_PROFILE`:

```bash
# Option 1: CLI flag
python3 .../esxi.py --profile prod preflight
python3 .../esxi.py --profile prod g ls vm

# Option 2: env var
ESXI_PROFILE=prod python3 .../esxi.py g ls vm
```

To create a new profile, run setup with `--profile <name>`.

---

## Why govc over PowerCLI

| | govc | PowerCLI |
|---|---|---|
| Startup | ~50ms | 3–8s (PowerShell + module load) |
| Output | JSON via `-json` flag | .NET objects, text by default |
| Install | Single binary | pwsh + VMware.PowerCLI module |
| LLM-friendly | ✅ structured, scriptable | ❌ verbose, hard to parse |

**Always prefer govc unless a specific feature is only in PowerCLI** (a small list: some vSAN / HCX / NSX-T operations).

## Installation & Authentication

**Don't install or configure manually — `esxi.py setup` handles it all.** See the [First-Time Setup](#step-2--first-time-setup-when-preflight-returns-readyfalse) section at the top of this file.

- `esxi.py preflight` — JSON status check; run this first, every invocation.
- `esxi.py setup --host X --user Y ...` — installs govc, writes config, prints per-OS password command.
- `esxi.py g <govc-args>` — govc wrapper: loads config + keychain password, then `os.execvpe`'s govc.

The underlying env-var model is standard govc:
`GOVC_URL`, `GOVC_USERNAME`, `GOVC_PASSWORD`, `GOVC_INSECURE`, `GOVC_DATACENTER` — `esxi.py g` builds this env from config + keychain on each call; you shouldn't need to set them yourself.

## Core Command Categories

Run `govc <category>.<action>` — tab completion after `govc ` lists all. Key categories:

| Category | Purpose |
|---|---|
| `vm.*` | VM lifecycle — info, create, clone, power, destroy, migrate |
| `snapshot.*` | Create, list, revert, remove snapshots |
| `datastore.*` | List, upload, download files; disk operations |
| `host.*` | ESXi host info, maintenance mode, service control |
| `network.*` / `dvs.*` | Standard / distributed port groups |
| `pool.*` | Resource pools |
| `folder.*` | VM / host folders |
| `license.*` | License management |
| `events` / `tasks` | Event log, running tasks |
| `ls` / `find` | Inventory traversal (like `ls`/`find` on a tree) |
| `import.*` / `export.*` | OVA/OVF import/export |

See [references/govc-reference.md](references/govc-reference.md) for the full command list with arguments.

## Quick Recipes

> **Note**: the examples below show `govc` as shorthand. When actually running, prefix with the Python wrapper so credentials are loaded from the keychain:
> `python3 ~/.claude/skills/esxi/esxi.py g <govc-args>`

### Inventory

```bash
# List everything under datacenter
govc ls

# Find all VMs
govc find -type m

# VM details as JSON
govc vm.info -json '<vm-name>'

# All VMs' power state + IP (note: govc 0.30+ returns camelCase keys)
govc ls -json vm | jq -r '.elements[].Object | "\(.name)\t\(.runtime.powerState)\t\(.guest.ipAddress // "-")"'
```

### Power operations

```bash
govc vm.power -on   '<vm-name>'
govc vm.power -off  '<vm-name>'   # hard off
govc vm.power -s    '<vm-name>'   # guest shutdown (needs tools)
govc vm.power -r    '<vm-name>'   # reset
govc vm.power -reboot '<vm-name>' # guest reboot
```

### Snapshots

```bash
govc snapshot.create -vm '<vm>' -m=true -q=false 'snap-name'   # -m=memory -q=quiesce
govc snapshot.tree   -vm '<vm>'
govc snapshot.revert -vm '<vm>' 'snap-name'
govc snapshot.remove -vm '<vm>' 'snap-name'
```

### Create a VM from scratch

```bash
govc vm.create -m 4096 -c 2 -g ubuntu64Guest \
  -net 'VM Network' -disk 40GB -on=false 'new-vm'

govc vm.disk.create -vm 'new-vm' -name 'new-vm/data' -size 100GB

# Attach ISO
govc device.cdrom.insert -vm 'new-vm' -device cdrom-3000 'iso-datastore/ubuntu.iso'
govc device.connect      -vm 'new-vm' cdrom-3000

govc vm.power -on 'new-vm'
```

### Clone

```bash
govc vm.clone -vm 'source-vm' -on=false -link=true 'clone-name'
```
`-link=true` creates a linked clone (fast, shares base disk).

### Datastore

```bash
govc datastore.ls
govc datastore.ls -ds=datastore1 /                   # files in datastore
govc datastore.upload -ds=datastore1 local.iso iso/local.iso
govc datastore.download -ds=datastore1 path/file.log ./file.log
```

### Host maintenance

```bash
govc host.info
govc host.maintenance.enter -host '<host>'
govc host.maintenance.exit  -host '<host>'
govc host.esxcli.run -host '<host>' network ip interface list
```

More patterns in [references/common-operations.md](references/common-operations.md).

## Safety Rules (CRITICAL)

VMware operations touch production-critical infrastructure. Follow these rules:

1. **Destructive ops require explicit confirmation**: `vm.destroy`, `snapshot.remove`, `datastore.rm`, `host.maintenance.enter` on the last host — never run these without the user's explicit green light. If in doubt, print the command with `-dry-run` semantics (i.e., show the command you would run) and ask first.
2. **Always `vm.power -off` before `vm.destroy`** — govc will error otherwise, but confirm the VM is the right one (`vm.info` first).
3. **Snapshots are not backups** — warn the user if they treat snapshots as long-term safety net. Long-lived snapshots cause disk bloat and performance degradation.
4. **Batch operations**: when acting on multiple VMs (`find` + loop), first list and show the user what will be affected.
5. **Maintenance mode on clusters**: entering maintenance on an ESXi host will attempt to migrate VMs; this can fail if DRS/shared storage not set up. Verify with `host.info` first.
6. **-k / GOVC_INSECURE**: only in dev/lab. For production vCenter with real CA, drop `-k` so cert validation happens.

## Output parsing

All `govc` commands accept `-json`. Pipe **directly** to `jq` (do not capture to a shell variable first — bash's `echo` on macOS silently eats backslash sequences in the JSON and breaks `jq`).

```bash
# ✅ Correct — direct pipe
govc vm.info -json 'debian*' | jq '.virtualMachines[] | {name: .name, cpu: .config.hardware.numCPU, mem: .config.hardware.memoryMB}'

# ❌ Wrong — echoing a variable mangles the JSON
OUT=$(govc ls -json vm); echo "$OUT" | jq ...   # breaks on complex output
```

Key wrapper paths (govc 0.30+ uses **camelCase** for all fields):

| Command | Wrapper | Element path |
|---|---|---|
| `ls -json <type>` | `.elements[]` | `.Object.{camelCase fields}` |
| `vm.info -json` | `.virtualMachines[]` | directly `.{camelCase fields}` |
| `host.info -json` | `.hostSystems[]` | directly `.{camelCase fields}` |
| `datastore.info -json` | `.datastores[]` | directly `.{camelCase fields}` |

If `jq` reports "control characters must be escaped", you captured the JSON into a bash variable and then echoed it. Fix: pipe directly. If the data really does have control chars (rare), fall back to `python3 -c 'import json,sys; …'` which is more lenient.

For non-JSON table output, use `-dump` (Go struct pretty-print) or default human format.

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `x509: certificate signed by unknown authority` | Self-signed cert | Add `-k` or `GOVC_INSECURE=1` |
| `ServerFaultCode: Permission to perform this operation was denied` | User lacks role | Use admin account, or grant role in vSphere |
| `ServerFaultCode: The object has already been deleted` | Stale reference after rename/move | Re-query the object by current name |
| `invalid argument (-vm): <name>` | VM name not unique or not found | Use full path: `/Datacenter/vm/Folder/<name>` |
| Connection refused / timeout | Wrong port or firewall | ESXi uses 443 (HTTPS) by default; vCenter also 443 |

More in [references/troubleshooting.md](references/troubleshooting.md).

## When to escalate to PowerCLI or API

govc covers 90% of ops. Fall back to these for:

- **vSAN management** → PowerCLI (`Get-VsanClusterConfiguration`) or vSAN REST API
- **HCX / NSX-T** → dedicated CLIs or REST
- **Complex workflow with retries/conditions** → write Python with `pyvmomi` or Go with `govmomi` directly
- **Bulk provisioning via templates** → `vm.clone` in govc handles this; PowerCLI only needed if you need VMware Customization Specs

## Related

- govc repo: <https://github.com/vmware/govmomi/tree/main/govc>
- govmomi Go library: <https://pkg.go.dev/github.com/vmware/govmomi>
- pyvmomi: <https://github.com/vmware/pyvmomi>
