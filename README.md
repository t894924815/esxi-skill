**English** | [中文](README.zh-CN.md)

# esxi-skill

A [Claude Code](https://claude.ai/code) skill for managing **VMware ESXi / vSphere** via the `govc` CLI.

Designed for LLM-driven automation: structured JSON output, fast startup, Unix-native. Covers VM lifecycle, snapshots, datastores, hosts, networks, OVA import/export, and bulk ops.

## Why a dedicated skill

`govc` is powerful but has 400+ commands across 40+ categories. Without context, an LLM either hallucinates syntax or defaults to less suitable tools (PowerCLI, manual SSH). This skill packages:

- **Triggering guidance** — Claude knows when to invoke it (VM ops, ESXi questions, vCenter automation)
- **Safety rules** — destructive ops require explicit confirmation; snapshots ≠ backups
- **Recipes** — common playbooks (health check, clone + cloud-init, bulk create, maintenance mode)
- **Troubleshooting** — common errors with fixes
- **Full command reference** — every `govc` category with flags and examples

## Install

Clone this repository into your Claude Code skills directory (use the clone URL from this repo's GitHub page).

- **Per-project**: clone into `<your-project>/.claude/skills/esxi`
- **Global (user-level)**: clone into `~/.claude/skills/esxi`

## Setup

1. **Install govc**
   ```bash
   # macOS
   brew install govc

   # Linux
   curl -L -o - "https://github.com/vmware/govmomi/releases/latest/download/govc_$(uname -s)_$(uname -m).tar.gz" \
     | sudo tar -C /usr/local/bin -xvzf - govc

   govc version
   ```

2. **Store credentials** (macOS Keychain recommended)
   ```bash
   security add-generic-password -a root -s govc-esxi.lab -w 'your-password' -U
   ```

3. **Set env vars** (add to `~/.zshrc`)
   ```bash
   export GOVC_URL='esxi.lab'                  # or vCenter FQDN
   export GOVC_USERNAME='root'                  # or administrator@vsphere.local
   export GOVC_INSECURE=1                       # if using self-signed cert
   export GOVC_DATACENTER='ha-datacenter'       # ESXi default
   export GOVC_PASSWORD=$(security find-generic-password -a "$GOVC_USERNAME" -s "govc-$GOVC_URL" -w 2>/dev/null)
   ```

4. **(Optional) allowlist govc in Claude Code settings**
   ```json
   // .claude/settings.json
   {
     "permissions": {
       "allow": ["Bash(govc *)"]
     }
   }
   ```

5. **Verify**
   ```bash
   govc about
   govc ls
   ```

## Triggering

Ask Claude Code things like:

- "List all VMs on my ESXi host"
- "Create a snapshot of web-01 before I update it"
- "Which datastores are over 80% full?"
- "Migrate all VMs off esxi1.lab so I can put it in maintenance mode"
- "Clone ubuntu-template to a new VM named app-prod with 4 CPU and 8GB RAM"

Claude will use govc directly via the Bash tool, following the skill's safety rules (read-first, confirm destructive ops, prefer JSON output for parsing).

## Contents

```
esxi-skill/
├── SKILL.md                          # Main skill — loaded on trigger
├── README.md                         # This file (English)
├── README.zh-CN.md                   # Chinese translation
├── LICENSE
└── references/
    ├── govc-reference.md             # Full command catalog by category
    ├── common-operations.md          # 12 recipes: health check, clone+cloud-init, migrate, etc.
    └── troubleshooting.md            # Common errors with fixes
```

## Safety model

This skill treats ESXi as **production-critical infrastructure**. Destructive operations (`vm.destroy`, `snapshot.remove`, `datastore.rm`, `host.maintenance.enter` on last host) always require explicit user confirmation. Claude will:

1. Show `vm.info` before any mutation.
2. Print the exact command it intends to run before running it.
3. Never `vm.destroy` without first confirming the target.
4. Warn about long-lived snapshots (disk bloat, performance impact).

See `SKILL.md` § *Safety Rules* for details.

## When this skill is **not** the right tool

- **vSAN deep management** — use PowerCLI or vSAN REST
- **NSX-T / HCX** — dedicated CLIs
- **Complex idempotent state management** — use Terraform `vsphere` provider
- **Read-only monitoring dashboard** — use Grafana + VMware exporter

For those cases, use govc for the 90% of ops it handles, and fall back to the specialized tool for the 10%.

## License

MIT. See [LICENSE](LICENSE).

## Contributing

PRs welcome. If you've got a recurring ESXi recipe that's not in `references/common-operations.md`, open an issue or PR.
