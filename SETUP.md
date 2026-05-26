# Installation & First-Time Configuration

`esxi-skill` is delivered as a single skill folder ([`esxi/`](esxi/)) inside this repository. Installing it means **getting that folder into your AI agent's skills directory**.

---

## Prerequisites

| Platform | Required | Optional |
|---|---|---|
| **macOS** | Python 3.7+, `brew` (for auto-installing govc) | — |
| **Linux** | Python 3.7+, `libsecret-tools` (`apt install libsecret-tools` / `dnf install libsecret`) | — |
| **Windows** | Python 3.7+, PowerShell 5.1+ | govc via `winget install VMware.govc` / `scoop install govc` |

Python is the only hard dependency you must install yourself. `govc` is auto-installed by `esxi.py setup` on macOS and Linux; on Windows it's manual.

---

## Step 1 — clone the repo

Pick a stable location (anywhere on your machine):

```bash
git clone https://github.com/<owner>/esxi-skill.git ~/code/esxi-skill
```

---

## Step 2 — link the skill into your agent

You only install the `esxi/` subdirectory, **not the whole repo**. Two ways:

### Option A — symlink (recommended; auto-updates with `git pull`)

```bash
# Claude Code
ln -s ~/code/esxi-skill/esxi ~/.claude/skills/esxi

# OpenAI Codex CLI
ln -s ~/code/esxi-skill/esxi ~/.codex/skills/esxi

# Both at once
for agent_dir in ~/.claude/skills ~/.codex/skills; do
  mkdir -p "$agent_dir"
  ln -s ~/code/esxi-skill/esxi "$agent_dir/esxi"
done
```

After `cd ~/code/esxi-skill && git pull`, both Claude and Codex see the update immediately.

### Option B — copy (no auto-update; useful for offline machines)

```bash
cp -R ~/code/esxi-skill/esxi ~/.claude/skills/esxi
cp -R ~/code/esxi-skill/esxi ~/.codex/skills/esxi
```

You'll need to repeat `cp -R` after each `git pull`.

### Windows (PowerShell)

```powershell
# Symlink — requires Dev Mode enabled OR run as Administrator
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\esxi" `
                                 -Target "$env:USERPROFILE\code\esxi-skill\esxi"

# Or copy
Copy-Item -Recurse "$env:USERPROFILE\code\esxi-skill\esxi" `
                   "$env:USERPROFILE\.claude\skills\esxi"
```

---

## Step 3 — verify installation

```bash
python3 ~/.claude/skills/esxi/scripts/esxi.py preflight
```

You should see JSON like:

```json
{"ready": false, "can_connect": false, "missing": ["govc", "config"]}
```

`missing: [govc, config]` is the expected "fresh install" state. The skill itself is installed correctly; the next step is to connect it to your ESXi/vCenter.

---

## Step 4 — first ESXi connection

Just **trigger the skill** through your AI agent. Examples that trigger it:

- "List all VMs on my ESXi host"
- "Create a snapshot of `web-01` before I patch it"
- "Which datastores are >80% full?"

The agent will run `preflight`, see what's missing, ask you 4 non-sensitive fields (host / username / cert type / datacenter), then run `esxi.py setup --host ... --user ...` automatically. It will install `govc` for you (Linux/macOS) and print **one** OS-specific command for you to run yourself — the **password command**.

The agent never sees, prompts for, or logs your password. You run that one command in your own terminal. It stores the password in:

| OS | Backend |
|---|---|
| macOS | login Keychain (`security` CLI) |
| Linux | libsecret keyring (`secret-tool`) |
| Windows | DPAPI-encrypted file at `%APPDATA%\esxi-skill\<profile>.cred` |

For the exact command per platform, see [`esxi/references/setup-commands.md`](esxi/references/setup-commands.md). The agent will paste the right one for your OS.

---

## Multiple ESXi hosts (profiles)

Use `--profile`:

```bash
python3 ~/.claude/skills/esxi/scripts/esxi.py --profile prod setup --host vcenter.prod --user administrator@vsphere.local --insecure 0
python3 ~/.claude/skills/esxi/scripts/esxi.py --profile lab  setup --host esxi.lab      --user root                       --insecure 1
```

Then use them:

```bash
python3 ~/.claude/skills/esxi/scripts/esxi.py --profile prod g ls vm
ESXI_PROFILE=lab python3 ~/.claude/skills/esxi/scripts/esxi.py g ls vm
```

---

## CI / containers (no keychain)

If you're running in CI or a container without a keychain available, set `GOVC_PASSWORD` directly:

```bash
export GOVC_PASSWORD='...'
python3 ~/.claude/skills/esxi/scripts/esxi.py g ls vm
```

`esxi.py g` checks `$GOVC_PASSWORD` **before** the keychain lookup. The password lives only in that shell's env; nothing is persisted.

---

## (Optional) Claude Code allowlist

To avoid permission prompts on every invocation, add to `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 ~/.claude/skills/esxi/scripts/esxi.py *)"
    ]
  }
}
```

---

## Uninstall

```bash
# Remove the install (whether symlink or copy)
rm -rf ~/.claude/skills/esxi
rm -rf ~/.codex/skills/esxi

# Remove your config and credentials
rm -rf ~/.config/esxi-skill           # macOS / Linux
# Windows: Remove-Item -Recurse "$env:APPDATA\esxi-skill"

# macOS: remove the Keychain entry
security delete-generic-password -s 'govc-<your-host>' -a 'root'

# Linux: remove the libsecret entry
secret-tool clear service 'govc-<your-host>' account 'root'

# Optionally remove the cloned repo too
rm -rf ~/code/esxi-skill
```

---

## Troubleshooting

See [`esxi/references/troubleshooting.md`](esxi/references/troubleshooting.md) for a full catalog of common errors. Highlights:

- **`x509: certificate signed by unknown authority`** — set `GOVC_INSECURE=1` in the config (we default to `1` for home labs)
- **`Multiple devices are currently online`** — that's `adb` error, unrelated to this skill
- **`govc not found`** after `setup` — open a new shell to pick up the updated `$PATH`
