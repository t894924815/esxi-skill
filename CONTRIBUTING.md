# Contributing to esxi-skill

Thanks for your interest in improving this skill!

## What kinds of contributions are most useful

- **Bug reports** — especially anything where Claude / Codex used the skill wrong or got a confusing error.
- **New `references/common-operations.md` recipes** — recurring vSphere ops you've automated.
- **Linux / Windows validation** — these platforms have code paths but no real-host testing yet. Running through `SETUP.md` end-to-end on either platform and reporting what broke is high-value.
- **`evals/evals.json` improvements** — additional test prompts, especially ones that catch known regressions (e.g., camelCase vs PascalCase jq, safety-rule violations).
- **Documentation clarity** — if something in `esxi/SKILL.md` was ambiguous and led the agent astray, propose better wording.

## What's intentionally out of scope (for now)

- **MCP server packaging** — this skill is a plain skill, not an MCP server. Adding MCP support would be a sibling project, not a change here.
- **Gemini / Trae / Kimi adapters** — if you want this skill on those agents, file an issue to discuss.
- **Bundled GUI / TUI** — `esxi.py` is CLI-only by design.
- **Removing the read-only credential consumer rule** — `esxi.py` doesn't write passwords, and PRs that add a `set-password` subcommand will be declined. The user runs OS-native commands; we just read.

## Development setup

```bash
git clone https://github.com/<owner>/esxi-skill.git
cd esxi-skill

# Symlink into your agent's skills dir for live testing
ln -s "$(pwd)/esxi" ~/.claude/skills/esxi

# Edit; the symlink means Claude sees changes immediately
$EDITOR esxi/SKILL.md
```

## Before opening a PR

1. **Syntax-check the Python**:
   ```bash
   python3 -c "import ast; ast.parse(open('esxi/scripts/esxi.py').read())"
   ```
2. **Run preflight** to confirm the skill still loads:
   ```bash
   python3 esxi/scripts/esxi.py preflight
   ```
3. **If you touched `SKILL.md` or `references/*`**, do a sanity skim — Claude reads these literally. Check that the structure still makes sense.
4. **Update `CHANGELOG.md`** under `## [Unreleased]` with a one-line entry.

## Code style

- Pure stdlib Python — **no pip dependencies**. If you find yourself wanting one, please open an issue first to discuss.
- `bash` (not POSIX `sh`) is fine for shell snippets.
- Markdown: ATX-style headers (`#`, `##`), fenced code blocks with language tags.

## Filing issues

Useful issue contents:
- What you asked the agent
- What command it ran
- Full output (esp. JSON from `preflight`)
- OS, Python version, govc version (`python3 esxi/scripts/esxi.py preflight` includes these)

## Security issues

For credential-handling vulnerabilities or anything that could leak secrets, please do **not** file a public issue. Email the maintainer (see the GitHub profile) or use GitHub's private vulnerability reporting.

## License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE).
