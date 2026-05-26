# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-05-26

### Changed
- **Restructured as a multi-file open-source project.** Repo root is now the project; the actual skill lives in [`esxi/`](esxi/). Install changes from "clone the repo into your skills dir" to "clone anywhere + symlink the `esxi/` subdir into your skills dir."
- Root `README.md` rewritten as project overview. Skill usage docs stay in `esxi/SKILL.md`.
- Added project-level files: `SETUP.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `VERSION`, `.github/workflows/lint.yml`.

### Migration
If you installed v0.1.x by cloning the repo directly into `~/.claude/skills/esxi/`, you need to re-install — see [SETUP.md](SETUP.md).

## [0.1.0] — 2026-05-22

### Added
- Spec-compliant structure (`scripts/`, `references/`, `evals/`).
- Table of contents on reference files >300 lines.
- `evals/evals.json` scaffold with 5 test prompts.

### Changed
- Moved `esxi.py` → `scripts/esxi.py` per Anthropic skill anatomy convention.
- All documentation paths updated to `<SKILL_DIR>/scripts/esxi.py`.

## [0.0.x] — 2026-04 → 2026-05

Pre-release iterations. Highlights:

- Single-file Python implementation; **zero pip dependencies** (pure stdlib).
- **Read-only credential consumer** design: `esxi.py` never writes passwords. User runs OS-native command, skill reads from OS keychain.
- Per-OS credential backends: macOS Keychain (`security`), Linux libsecret (`secret-tool`), Windows DPAPI-encrypted file.
- `GOVC_PASSWORD` env-var bypass for CI / containers / Linux without libsecret.
- Three subcommands: `preflight` (JSON status check), `setup` (install govc + write config + print password command for user), `g` (govc wrapper, `os.execvpe` replaces Python with govc).
- `os.execvpe` ensures the password lives only in `govc`'s env after exec, not in any persistent shell or Python process.
- Linux deliberately refuses to fall back to a plaintext chmod-600 file when libsecret is absent — install `libsecret-tools` or use `GOVC_PASSWORD` env var.
- Windows DPAPI file uses PowerShell `Read-Host -AsSecureString | ConvertFrom-SecureString | Set-Content`. Plaintext never hits disk.

[Unreleased]: https://github.com/<owner>/esxi-skill/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/<owner>/esxi-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/<owner>/esxi-skill/releases/tag/v0.1.0
