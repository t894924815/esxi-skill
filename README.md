**English** | [中文](README.zh-CN.md)

# esxi-skill

A [Claude Code](https://claude.ai/code) / [Codex CLI](https://github.com/openai/codex) **agent skill** for managing **VMware ESXi & vSphere** infrastructure via `govc`.

This repository is the **upstream project**. The actual skill content lives under [`esxi/`](esxi/) — that subdirectory is what gets installed into your AI agent's skills directory.

---

## Why this skill exists

`govc` is VMware's official Go CLI for vSphere. It exposes 400+ commands across 40+ categories — powerful, but cumbersome for LLM agents to use blindly. Without context, an LLM will:

- Hallucinate command syntax
- Fall back to less suitable tools (PowerCLI, manual SSH)
- Use stale `PascalCase` jq paths against `govc 0.30+` (which switched to `camelCase`)
- Treat snapshots as backups, or run destructive ops without confirmation
- Leak credentials into chat logs and shell history

`esxi-skill` packages the operational knowledge an LLM needs to drive `govc` safely and idiomatically: triggering rules, safety guards, per-OS credential handling, recipes for common tasks, and troubleshooting references.

## What it does

- **VM lifecycle**: create, clone (incl. linked + cloud-init), power, destroy, migrate
- **Snapshots**: create / revert / consolidate, with anti-bloat warnings
- **Datastore**: browse, upload/download, capacity reports
- **Host**: maintenance mode, esxcli passthrough, service control
- **Network**: vSwitch / DVS / port groups
- **OVA/OVF**: import / export
- **Bulk ops**: health check, mass migrate, CSV-driven create

## Design highlights

- **Read-only credential consumer** — the skill never writes passwords. The user runs an OS-native command (Keychain `security`, libsecret `secret-tool`, Windows DPAPI PowerShell) and the skill reads from that store.
- **Cross-platform**: macOS (primary, tested), Linux (libsecret), Windows (DPAPI file).
- **Zero pip dependencies** — pure Python 3.7+ stdlib.
- **Single Python entry point** at [`esxi/scripts/esxi.py`](esxi/scripts/esxi.py). Three subcommands: `preflight`, `setup`, `g`.
- **`os.execvpe` for the wrapper** — Python is replaced by `govc`; password only lives in `govc`'s env after exec.

## Quick install

```bash
git clone https://github.com/<owner>/esxi-skill.git
# Then symlink the skill subdir into your agent's skills directory:
ln -s "$(pwd)/esxi-skill/esxi" ~/.claude/skills/esxi          # Claude Code
ln -s "$(pwd)/esxi-skill/esxi" ~/.codex/skills/esxi           # Codex CLI
```

Full install guide and per-OS prerequisites: **[SETUP.md](SETUP.md)**.

## Repository layout

```
esxi-skill/                       ← this repo (the "project")
├── README.md                     # ← you are here (project overview)
├── SETUP.md                      # install + first-time configuration
├── CHANGELOG.md                  # version history
├── CONTRIBUTING.md               # how to file issues / send PRs
├── VERSION
├── LICENSE                       # MIT
├── .github/workflows/            # CI: lint markdown + python syntax check
└── esxi/                         ← THE SKILL (this is what gets installed)
    ├── SKILL.md                  # primary skill instructions (loaded by Claude)
    ├── scripts/
    │   └── esxi.py               # the wrapper: preflight / setup / g
    ├── references/               # progressive-disclosure docs
    │   ├── govc-reference.md
    │   ├── common-operations.md
    │   ├── setup-commands.md
    │   └── troubleshooting.md
    └── evals/
        └── evals.json            # test prompts (scaffold; needs live ESXi)
```

## Status

- **macOS**: tested end-to-end against a live ESXi 8.0.1 host
- **Linux**: code paths complete, **untested on a real Linux host**
- **Windows**: DPAPI file backend designed and code-reviewed, **untested on a real Windows host**

See **[CHANGELOG.md](CHANGELOG.md)** for what changed when.

## Contributing

PRs welcome — bug reports, new recipes, Linux/Windows validation, additional `references/` content. See **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## License

MIT — see [LICENSE](LICENSE).
