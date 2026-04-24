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

This skill auto-configures itself the first time you invoke it — no manual prep needed.

When you ask Claude something like *"list all VMs on my ESXi host"*, it will:

1. Run `scripts/preflight.sh` to detect what's missing.
2. If anything is missing, Claude will tell you to run this in **your own terminal**:
   ```bash
   bash ~/.claude/skills/esxi/scripts/setup-interactive.sh
   ```
3. The interactive script prompts you for host / username / cert type / password. **Password is read silently (no echo, never in chat, never in shell history).**
4. The script then:
   - Installs `govc` (Homebrew on macOS, release tarball on Linux)
   - Writes config to `~/.config/esxi-skill/default.env`
   - Stores password in macOS Keychain (never in plain text on disk)
   - Verifies the connection with `govc about`
5. Tell Claude "done", Claude re-runs preflight, and executes your original request using the `scripts/g` wrapper.

### 🔐 Security design

**Credentials never pass through the LLM or chat log.** The interactive script runs entirely in your terminal; Claude just points you at it and waits for you to confirm. Same trust boundary as `sudo` or `ssh`.

### Non-interactive alternative

For automation (CI, Ansible, etc.) where you already have the password in an env var or vault:

```bash
echo "$PASSWORD" | ~/.claude/skills/esxi/scripts/setup.sh 'esxi.lab' 'root' 1 'ha-datacenter'
```

Four positional args: `<host> <user> <insecure:1|0> <datacenter>`. Password is piped via stdin (so it doesn't appear in shell history or process listings).

### Multi-profile

For multiple ESXi hosts, use `ESXI_PROFILE`:

```bash
echo 'pw' | ESXI_PROFILE=prod ~/.claude/skills/esxi/scripts/setup.sh 'vcenter.prod' 'admin@vsphere.local' 0
echo 'pw' | ESXI_PROFILE=lab  ~/.claude/skills/esxi/scripts/setup.sh 'esxi.lab'      'root'                 1

# Later
ESXI_PROFILE=prod ~/.claude/skills/esxi/scripts/g ls vm
ESXI_PROFILE=lab  ~/.claude/skills/esxi/scripts/g ls vm
```

### (Optional) Allowlist in Claude Code settings

```json
// .claude/settings.json
{
  "permissions": {
    "allow": [
      "Bash(~/.claude/skills/esxi/scripts/g *)",
      "Bash(~/.claude/skills/esxi/scripts/preflight.sh*)"
    ]
  }
}
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
├── scripts/
│   ├── preflight.sh                  # Check state; JSON output
│   ├── setup-interactive.sh          # User-run setup: prompts silently in terminal
│   ├── setup.sh                      # Non-interactive setup (for automation)
│   └── g                             # govc wrapper (auto-loads Keychain password)
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
