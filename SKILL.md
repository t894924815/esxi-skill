---
name: esxi
description: "VMware ESXi / vSphere management via govc CLI. Use when: managing ESXi hosts or vCenter, VM lifecycle operations (create/clone/power/delete), snapshot management, datastore operations, network/port group config, host inventory queries, ISO/OVA import, VMDK operations, or any vSphere automation task. TRIGGER when: user mentions ESXi, vSphere, vCenter, govc, VMware VM, .vmx, .vmdk, snapshot, datastore, or wants to automate VMware infrastructure. Prefer govc over PowerCLI for LLM-driven automation (structured JSON output, fast startup, Unix-native)."
---

# VMware ESXi / vSphere Management

Manage VMware ESXi hosts and vCenter via `govc` — VMware's official Go CLI built on `govmomi`. Optimized for LLM-driven automation: structured JSON output, zero-dependency binary, Unix-native.

---

## 🚀 Before Running Any ESXi Command (CRITICAL)

Every invocation of this skill MUST start with a **preflight check**. Do not attempt to run `govc` directly — use the wrapper `./scripts/g` which handles credentials transparently.

### Step 1 — Preflight

```bash
~/.claude/skills/esxi/scripts/preflight.sh
```

Output is a JSON object:
- `{"ready": true, ...}` → proceed to the actual user request using `./scripts/g`
- `{"ready": false, "missing": [...]}` → follow **First-Time Setup** below

### Step 2 — First-Time Setup (when preflight returns ready=false)

The `missing` field lists what's absent. Possible values: `govc`, `config`, `keychain`.

**🔐 CRITICAL SECURITY RULES:**

- DO NOT ask the user for their password in chat.
- DO NOT auto-trigger GUI dialogs, `read -rsp` prompts, or anything that spawns interactive input from a subprocess Claude started.
- Claude's role here is purely **advisory**: print copy-pasteable commands for the user to review and run themselves in their own terminal. The user chooses the input method for the password (Keychain Access.app, OS password manager, or a CLI prompt they themselves type). Claude never sees or handles the password.

**What Claude should do**:

1. **Ask the user for the non-sensitive fields only** (each field in its own line in the chat, waiting for reply):
   - ESXi / vCenter host (e.g. `esxi.lab`)
   - Username (e.g. `root`)
   - Self-signed cert? y/n (→ `GOVC_INSECURE=1` or `0`)
   - Datacenter (default `ha-datacenter`)

2. **Output a single copy-pasteable command block** with those values filled in. The block has three parts; ask the user to run them (or tell them to pick one of the two password options). Do not run any of this via the Bash tool — the user runs it in their own terminal.

   ```bash
   # ─── 1. Install govc (macOS) ──────────────────────────────────────────
   command -v govc >/dev/null || brew install govc

   # ─── 2. Write non-sensitive config ────────────────────────────────────
   mkdir -p ~/.config/esxi-skill && chmod 700 ~/.config/esxi-skill
   cat > ~/.config/esxi-skill/default.env <<'EOF'
   export GOVC_URL='<HOST>'
   export GOVC_USERNAME='<USER>'
   export GOVC_INSECURE=<1|0>
   export GOVC_DATACENTER='<DC>'
   export ESXI_CRED_SERVICE='govc-<HOST>'
   EOF
   chmod 600 ~/.config/esxi-skill/default.env

   # ─── 3. Store password in login Keychain — pick ONE of the two ────────

   # Option A (recommended): Keychain Access.app GUI
   #   open -a "Keychain Access"
   #   File ▸ New Password Item…
   #     Keychain Item Name: govc-<HOST>
   #     Account Name:       <USER>
   #     Password:           (type here in native secure field)

   # Option B: CLI with silent prompt (password never in history/args)
   IFS= read -rs -p "ESXi password: " PW && echo && \
     security add-generic-password -a '<USER>' -s 'govc-<HOST>' -w "$PW" -U && \
     unset PW && echo "✓ saved to Keychain"
   ```

3. **Explain the two options briefly**:
   - **Option A** (Keychain Access.app) — fully native, password never enters any shell. Most secure.
   - **Option B** — password briefly in shell memory during `read`/`security` execution. Acceptable for most threat models; not in shell history, not in process args (because `-w "$PW"` resolves the variable before exec).

4. **Wait for the user to confirm** ("done"/"好了"/etc.).

5. **Re-run preflight** (`~/.claude/skills/esxi/scripts/preflight.sh`). If `ready: true`, proceed to the original request. If still failing, show the JSON and help debug.

**For Linux / Windows**: output the equivalent block using `secret-tool` / `cmdkey` — see [references/setup-commands.md](references/setup-commands.md) for OS-specific templates.

**Why this matters**:
- Credentials never pass through the LLM or chat log.
- No hidden side effects from Claude — the user sees every action before it runs.
- Password entry uses either OS-native secure storage GUI (most secure) or a CLI path the user typed themselves.
- The `g` wrapper reads the password from the Keychain on each call; it's the same regardless of which option the user picked.

### Step 3 — Run the Actual Request

Use the wrapper, not raw `govc`:

```bash
~/.claude/skills/esxi/scripts/g ls vm
~/.claude/skills/esxi/scripts/g vm.info -json 'web-01'
~/.claude/skills/esxi/scripts/g about
```

The wrapper reads config + pulls password from Keychain each time, exports env vars, then execs `govc`.

### Multi-profile (optional)

For multiple ESXi hosts, set `ESXI_PROFILE` before each call:

```bash
ESXI_PROFILE=prod ~/.claude/skills/esxi/scripts/g ls vm       # uses ~/.config/esxi-skill/prod.env
ESXI_PROFILE=lab  ~/.claude/skills/esxi/scripts/g ls vm       # uses ~/.config/esxi-skill/lab.env
```

To create a new profile, run setup with `ESXI_PROFILE=<name>` prefixed.

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

**Don't install or configure manually — the `scripts/setup.sh` helper does it all.** See the [First-Time Setup](#step-2--first-time-setup-when-preflight-returns-readyfalse) section at the top of this file.

- `scripts/setup.sh` — installs govc (brew / GitHub release tarball), writes config, stores password in Keychain, tests connection.
- `scripts/g` — govc wrapper: loads profile env + Keychain password, then execs govc.
- `scripts/preflight.sh` — status check; run this first, every invocation.

The underlying env-var model is standard govc:
`GOVC_URL`, `GOVC_USERNAME`, `GOVC_PASSWORD`, `GOVC_INSECURE`, `GOVC_DATACENTER` — but you shouldn't need to set them yourself when using the wrapper.

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

> **Note**: the examples below show `govc` as shorthand. When actually running, use the wrapper: **`~/.claude/skills/esxi/scripts/g`** (or `./scripts/g` from the skill dir). It auto-loads credentials from Keychain.

### Inventory

```bash
# List everything under datacenter
govc ls

# Find all VMs
govc find -type m

# VM details as JSON
govc vm.info -json '<vm-name>'

# All VMs' power state + IP
govc ls -json vm | jq -r '.elements[].Object | "\(.Name)\t\(.Runtime.PowerState)\t\(.Summary.Guest.IpAddress // "-")"'
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

All `govc` commands accept `-json`. Pipe to `jq` for filtering:

```bash
govc vm.info -json '*' | jq '.virtualMachines[] | {name: .name, cpu: .config.hardware.numCPU, mem: .config.hardware.memoryMB}'
```

For table output, use `-dump` (Go struct pretty-print) or default human format.

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
