---
name: esxi
description: "VMware ESXi / vSphere management via govc CLI. Use when: managing ESXi hosts or vCenter, VM lifecycle operations (create/clone/power/delete), snapshot management, datastore operations, network/port group config, host inventory queries, ISO/OVA import, VMDK operations, or any vSphere automation task. TRIGGER when: user mentions ESXi, vSphere, vCenter, govc, VMware VM, .vmx, .vmdk, snapshot, datastore, or wants to automate VMware infrastructure. Prefer govc over PowerCLI for LLM-driven automation (structured JSON output, fast startup, Unix-native)."
---

# VMware ESXi / vSphere Management

Manage VMware ESXi hosts and vCenter via `govc` — VMware's official Go CLI built on `govmomi`. Optimized for LLM-driven automation: structured JSON output, zero-dependency binary, Unix-native.

## Why govc over PowerCLI

| | govc | PowerCLI |
|---|---|---|
| Startup | ~50ms | 3–8s (PowerShell + module load) |
| Output | JSON via `-json` flag | .NET objects, text by default |
| Install | Single binary | pwsh + VMware.PowerCLI module |
| LLM-friendly | ✅ structured, scriptable | ❌ verbose, hard to parse |

**Always prefer govc unless a specific feature is only in PowerCLI** (a small list: some vSAN / HCX / NSX-T operations).

## Installation

```bash
# macOS
brew install govc

# Linux
curl -L -o - "https://github.com/vmware/govmomi/releases/latest/download/govc_$(uname -s)_$(uname -m).tar.gz" | tar -C /usr/local/bin -xvzf - govc

# Verify
govc version
```

## Authentication

govc reads credentials from environment variables. **Never hardcode passwords**; store them in Keychain or a `.envrc` gitignored from the repo.

### Required env vars

```bash
export GOVC_URL='esxi-host.example.com'              # or vCenter FQDN
export GOVC_USERNAME='root'                          # or administrator@vsphere.local
export GOVC_PASSWORD='...'                           # see Keychain pattern below
export GOVC_INSECURE=1                               # self-signed cert; drop if using CA-signed
export GOVC_DATACENTER='ha-datacenter'               # ESXi default; vCenter uses real names
```

### Keychain pattern (macOS, recommended)

Store password once:
```bash
security add-generic-password -a "$GOVC_USERNAME" -s "govc-$GOVC_URL" -w 'password-here' -U
```

Use in session:
```bash
export GOVC_PASSWORD=$(security find-generic-password -a "$GOVC_USERNAME" -s "govc-$GOVC_URL" -w)
```

Put the `export` lines (without the plaintext password) in `~/.zshrc` so every shell has access.

### Per-command override

For one-off use without setting env:
```bash
govc -u "user:pass@host" -k vm.info <vm-name>
```
`-k` = insecure (self-signed cert), `:` separates user/pass in URL form.

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
