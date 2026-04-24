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

## Requirements

- **Python 3.7+** (pre-installed on macOS and most Linux; `winget install Python.Python.3` on Windows)
- Anything else (`govc` binary, keychain setup) is handled automatically by the skill.

## Setup

Entirely driven by a single Python module `esxi.py`. When you ask Claude *"list all VMs on my ESXi host"* and nothing is configured yet:

| Step | Who | Command |
|---|---|---|
| 1. Preflight | Claude auto | `python3 esxi.py preflight` |
| 2. Ask for 4 non-sensitive fields | Claude → you in chat | host / user / cert / datacenter |
| 3. Install `govc` + write config | Claude auto | `python3 esxi.py setup --host … --user … …` |
| 4. Store password | **You run** in your terminal | command printed by step 3 (per-OS) |
| 5. Re-verify + list VMs | Claude auto | `python3 esxi.py preflight && python3 esxi.py g ls vm` |

Step 4 is the only manual part. The command Claude prints depends on your OS:

- **macOS**: `security add-generic-password -a <user> -s govc-<host> -U -w` (interactive hidden prompt)
- **Linux** (with libsecret): `secret-tool store …`
- **Linux** (no libsecret): `read -rs` → `chmod 600` file
- **Windows**: PowerShell `Read-Host -AsSecureString` → `icacls` ACL file

### 🔐 Security design

- Claude auto-handles non-sensitive work (saving you typing), but hands off the password step so credentials never flow through the LLM, chat log, or any process Claude started.
- `esxi.py g` uses `os.execvpe` to replace the Python process with `govc`; the password only lives in govc's env after exec, not in any shell or persistent Python process.

For full OS-specific command reference, see [references/setup-commands.md](references/setup-commands.md).

### Multi-profile

For multiple ESXi hosts, use `--profile` or `ESXI_PROFILE`:

```bash
# Create two profiles
python3 ~/.claude/skills/esxi/esxi.py --profile prod setup --host vcenter.prod --user administrator@vsphere.local --insecure 0
python3 ~/.claude/skills/esxi/esxi.py --profile lab  setup --host esxi.lab      --user root                       --insecure 1

# Use them (each setup prints a password command; run it once per profile)
python3 ~/.claude/skills/esxi/esxi.py --profile prod g ls vm
ESXI_PROFILE=lab python3 ~/.claude/skills/esxi/esxi.py g ls vm
```

### (Optional) Allowlist in Claude Code settings

```json
// .claude/settings.json
{
  "permissions": {
    "allow": [
      "Bash(python3 ~/.claude/skills/esxi/esxi.py *)"
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
├── esxi.py                           # Single Python entry point (all subcommands)
└── references/
    ├── govc-reference.md             # Full command catalog by category
    ├── common-operations.md          # 12 recipes: health check, clone+cloud-init, migrate, etc.
    ├── setup-commands.md             # Per-OS password-storage command reference
    └── troubleshooting.md            # Common errors with fixes
```

### Usage cheatsheet

```bash
python3 ~/.claude/skills/esxi/esxi.py preflight                       # JSON status
python3 ~/.claude/skills/esxi/esxi.py setup --host X --user root ...  # install + config + print pw cmd
python3 ~/.claude/skills/esxi/esxi.py g ls vm                         # run any govc command
python3 ~/.claude/skills/esxi/esxi.py --profile lab g vm.info ...     # non-default profile
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
