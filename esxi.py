#!/usr/bin/env python3
"""esxi-skill — cross-platform govc wrapper.

Subcommands:
  preflight   — JSON status check (exit 0 if ready, 1 otherwise).
  setup       — auto-install govc, write config, print per-OS password cmd.
  g           — govc wrapper: load config + keychain password, exec govc.

Config lives in  ~/.config/esxi-skill/<profile>.json  (or the first location
in $XDG_CONFIG_HOME/esxi-skill). Password lives in the OS-native keychain.

Design:
  - Pure stdlib. No pip dependencies.
  - Python 3.7+.
  - `g` uses os.execvpe: Python is replaced by govc, so password lives only
    in govc's env (unavoidable — govc reads GOVC_PASSWORD).
  - Windows credential retrieval is NOT implemented here. Recommend WSL.
"""

from __future__ import annotations
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional


# ─── Config ──────────────────────────────────────────────────────────────

def config_dir() -> Path:
    """Per-OS config directory.
      macOS / Linux: $XDG_CONFIG_HOME or ~/.config → esxi-skill/
      Windows:       %APPDATA% → esxi-skill/        (e.g. C:\\Users\\u\\AppData\\Roaming\\esxi-skill)
    """
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "esxi-skill"

def config_path(profile: str) -> Path:
    return config_dir() / f"{profile}.json"

def cred_file_path(profile: str) -> Path:
    return config_dir() / f"{profile}.cred"

def load_config(profile: str) -> Optional[dict]:
    p = config_path(profile)
    if not p.exists():
        return None
    return json.loads(p.read_text())

def save_config(profile: str, cfg: dict) -> Path:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    p = config_path(profile)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return p


# ─── Keychain access (per-OS) ─────────────────────────────────────────────

class KeychainError(Exception):
    pass

def _run(cmd: list[str], input_: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=input_, capture_output=True, text=True)

def get_password(service: str, account: str, profile: str = "default") -> Optional[str]:
    sysname = platform.system()
    if sysname == "Darwin":
        r = _run(["security", "find-generic-password", "-a", account, "-s", service, "-w"])
        if r.returncode == 0:
            # security prints password + newline
            return r.stdout.rstrip("\n")
        return None
    elif sysname == "Linux":
        # Prefer libsecret
        if shutil.which("secret-tool"):
            r = _run(["secret-tool", "lookup", "service", service, "account", account])
            if r.returncode == 0 and r.stdout:
                return r.stdout  # secret-tool does not add trailing newline
        # Fallback to file
        cf = cred_file_path(profile)
        if cf.exists():
            return cf.read_text()
        return None
    elif sysname == "Windows":
        # Windows: chmod-equivalent file under %APPDATA%\esxi-skill (via config_dir).
        # For stronger security, users can install the `keyring` pip package and
        # extend this module to prefer Windows Credential Manager.
        cf = cred_file_path(profile)
        if cf.exists():
            return cf.read_text()
        return None
    else:
        raise KeychainError(f"Unsupported platform: {sysname}")

def keychain_has_entry(service: str, account: str, profile: str = "default") -> bool:
    sysname = platform.system()
    if sysname == "Darwin":
        r = _run(["security", "find-generic-password", "-a", account, "-s", service])
        return r.returncode == 0
    elif sysname == "Linux":
        if shutil.which("secret-tool"):
            r = _run(["secret-tool", "lookup", "service", service, "account", account])
            if r.returncode == 0 and r.stdout:
                return True
        return cred_file_path(profile).exists()
    elif sysname == "Windows":
        return cred_file_path(profile).exists()
    else:
        return False


# ─── govc install ─────────────────────────────────────────────────────────

def govc_path() -> Optional[str]:
    return shutil.which("govc")

def govc_version() -> Optional[str]:
    p = govc_path()
    if not p:
        return None
    r = _run([p, "version"])
    if r.returncode == 0:
        return r.stdout.splitlines()[0].strip()
    return None

def install_govc() -> None:
    """Install govc. Raises on failure."""
    sysname = platform.system()
    if sysname == "Darwin":
        if not shutil.which("brew"):
            raise RuntimeError(
                "Homebrew is required to auto-install govc on macOS. "
                "Install brew from https://brew.sh, then retry setup."
            )
        r = subprocess.run(["brew", "install", "govc"])
        if r.returncode != 0:
            raise RuntimeError("brew install govc failed")
    elif sysname == "Linux":
        machine = platform.machine()
        arch = {"x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
        if not arch:
            raise RuntimeError(f"Unsupported Linux arch: {machine}")
        url = f"https://github.com/vmware/govmomi/releases/latest/download/govc_Linux_{arch}.tar.gz"
        with tempfile.TemporaryDirectory() as td:
            tgz = Path(td) / "govc.tar.gz"
            print(f"[setup] downloading {url}", file=sys.stderr)
            with urllib.request.urlopen(url) as resp, open(tgz, "wb") as out:
                shutil.copyfileobj(resp, out)
            with tarfile.open(tgz) as tf:
                tf.extract("govc", path=td)
            src = Path(td) / "govc"
            # Try /usr/local/bin first, fallback to ~/.local/bin
            for dest_dir in [Path("/usr/local/bin"), Path.home() / ".local/bin"]:
                if not dest_dir.exists():
                    try:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                    except OSError:
                        continue
                if os.access(dest_dir, os.W_OK):
                    dest = dest_dir / "govc"
                    shutil.copy2(src, dest)
                    dest.chmod(0o755)
                    print(f"[setup] installed to {dest}", file=sys.stderr)
                    return
            # Need sudo
            if shutil.which("sudo"):
                r = subprocess.run(["sudo", "install", "-m", "755", str(src), "/usr/local/bin/govc"])
                if r.returncode == 0:
                    print("[setup] installed to /usr/local/bin/govc (via sudo)", file=sys.stderr)
                    return
            raise RuntimeError(
                "Cannot write to /usr/local/bin or ~/.local/bin. "
                "Install govc manually from " + url
            )
    elif sysname == "Windows":
        # Windows: prefer winget/scoop/choco — no silent install to avoid UAC surprises
        raise RuntimeError(
            "govc auto-install on Windows is not implemented.\n"
            "  Install one of:\n"
            "    winget install VMware.govc\n"
            "    scoop install govc\n"
            "    choco install govc\n"
            "  Or download from https://github.com/vmware/govmomi/releases/latest\n"
            "  Then re-run setup."
        )
    else:
        raise RuntimeError(
            f"Automatic govc install on {sysname} is not supported. "
            f"Download manually: https://github.com/vmware/govmomi/releases/latest"
        )


# ─── Password command hint (per-OS) ───────────────────────────────────────

def password_command_hint(service: str, account: str, profile: str) -> str:
    """Return the platform-appropriate command for the USER to run themselves
    to store the password. Never executed by this module."""
    sysname = platform.system()
    if sysname == "Darwin":
        return (
            "Run ONE of these in your own terminal:\n"
            "\n"
            "  # Option A (recommended) — security CLI's native prompt.\n"
            "  # `-w` as the last option with no value triggers an interactive\n"
            "  # prompt (hidden, asks to retype). Documented in `man security`.\n"
            f"  security add-generic-password -a {account!r} -s {service!r} -U -w\n"
            "\n"
            "  # Option B — Keychain Access.app GUI.\n"
            "  #   open -a \"Keychain Access\"\n"
            "  #   File ▸ New Password Item…\n"
            f"  #     Keychain Item Name: {service}\n"
            f"  #     Account Name:       {account}\n"
            "  #     Password:           (type into the native secure field)\n"
        )
    elif sysname == "Linux":
        has_libsecret = shutil.which("secret-tool") is not None
        if has_libsecret:
            return (
                "Run in your own terminal (libsecret detected):\n"
                "\n"
                f"  secret-tool store --label={f'govc: {account} @ {service}'!r} \\\n"
                f"    service {service!r} account {account!r}\n"
                "\n"
                "secret-tool will prompt via the keyring daemon. Password never\n"
                "touches the shell.\n"
            )
        cf = cred_file_path(profile)
        return (
            "Run in your own terminal (libsecret not found — using file fallback):\n"
            "\n"
            "  umask 077\n"
            f"  mkdir -p {str(cf.parent)!r}\n"
            f"  read -rs -p 'ESXi password: ' PW && echo\n"
            f"  printf '%s' \"$PW\" > {str(cf)!r}\n"
            f"  chmod 600 {str(cf)!r}\n"
            "  unset PW\n"
            "\n"
            "For stronger security, install libsecret-tools and re-run setup:\n"
            "  apt install libsecret-tools    # Debian/Ubuntu\n"
            "  dnf install libsecret          # Fedora/RHEL\n"
        )
    elif sysname == "Windows":
        cf = cred_file_path(profile)
        return (
            "Run in PowerShell in your own terminal (file-based credential):\n"
            "\n"
            f"  $dir = Split-Path -Parent '{cf}'\n"
            "  New-Item -ItemType Directory -Force -Path $dir | Out-Null\n"
            "  $sec = Read-Host -AsSecureString -Prompt 'ESXi password'\n"
            "  $pw = [System.Net.NetworkCredential]::new('', $sec).Password\n"
            f"  [IO.File]::WriteAllText('{cf}', $pw)\n"
            "  # Tighten ACL to current user only:\n"
            f"  icacls '{cf}' /inheritance:r /grant:r \"$($env:USERNAME):(R,W)\"\n"
            "\n"
            "⚠️  File-based storage. For Windows Credential Manager integration,\n"
            "    install `keyring` (pip install keyring) and extend esxi.py.\n"
            "    Stronger alternative: run esxi-skill inside WSL.\n"
        )
    else:
        return f"Unsupported platform: {sysname}. See SKILL.md."


# ─── preflight ────────────────────────────────────────────────────────────

def cmd_preflight(args: argparse.Namespace) -> int:
    profile = args.profile
    missing: list[str] = []
    details: dict = {}

    # 1. govc installed?
    v = govc_version()
    if v:
        details["govc"] = v
    else:
        missing.append("govc")

    # 2. config exists?
    cfg = load_config(profile)
    if cfg is not None:
        details["profile"] = profile
        details["host"] = cfg.get("host")
        details["user"] = cfg.get("username")
    else:
        missing.append("config")

    # 3. keychain entry?
    if cfg is not None:
        service = cfg.get("cred_service") or f"govc-{cfg.get('host','')}"
        account = cfg.get("username", "")
        if keychain_has_entry(service, account, profile):
            sysname = platform.system()
            if sysname == "Darwin":
                details["keychain"] = "macos"
            elif sysname == "Linux":
                details["keychain"] = "libsecret" if shutil.which("secret-tool") else "file"
            else:
                details["keychain"] = "file"
        else:
            missing.append("keychain")

    # 4. can_connect?
    can_connect = False
    if not missing:
        try:
            service = cfg["cred_service"]
            pw = get_password(service, cfg["username"], profile)
            if pw:
                env = build_govc_env(cfg, pw)
                r = subprocess.run(
                    [govc_path(), "about"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                can_connect = r.returncode == 0
        except Exception:
            can_connect = False
    details["can_connect"] = can_connect

    ready = (not missing) and can_connect
    out = {"ready": ready, **details}
    if missing:
        out["missing"] = missing
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ready else 1


# ─── setup ────────────────────────────────────────────────────────────────

def cmd_setup(args: argparse.Namespace) -> int:
    profile = args.profile
    host = args.host
    user = args.user
    insecure = args.insecure
    datacenter = args.datacenter

    print(f"[setup] profile={profile}  host={host}  user={user}  insecure={insecure}  dc={datacenter}", file=sys.stderr)

    # 1. Install govc if missing
    if not govc_path():
        print("[setup] govc not found, installing…", file=sys.stderr)
        install_govc()
    else:
        print(f"[setup] govc already installed: {govc_version()}", file=sys.stderr)

    # 2. Write config
    service = f"govc-{host}"
    cfg = {
        "profile": profile,
        "host": host,
        "username": user,
        "insecure": bool(insecure),
        "datacenter": datacenter,
        "cred_service": service,
    }
    p = save_config(profile, cfg)
    print(f"[setup] config written: {p}", file=sys.stderr)

    # 3. Print password command for USER to run themselves
    print("")
    print("━" * 60)
    print(f"🔐 Password step — run this yourself (profile={profile}):")
    print("━" * 60)
    print(password_command_hint(service, user, profile))
    print("━" * 60)
    print("After you've stored the password, run:")
    print(f"  python3 {Path(__file__)} preflight")
    print("to verify, then ask your AI assistant to run the original request.")
    return 0


# ─── g wrapper ────────────────────────────────────────────────────────────

def build_govc_env(cfg: dict, password: str) -> dict:
    """Minimal env for govc. Starts fresh (no inherited GOVC_*), passes only
    what govc needs plus basic PATH/HOME/USER."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "USER": os.environ.get("USER", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "GOVC_URL": cfg["host"],
        "GOVC_USERNAME": cfg["username"],
        "GOVC_INSECURE": "1" if cfg.get("insecure") else "0",
        "GOVC_DATACENTER": cfg.get("datacenter", "ha-datacenter"),
        "GOVC_PASSWORD": password,
    }
    return env

def cmd_g(args: argparse.Namespace) -> int:
    profile = args.profile
    cfg = load_config(profile)
    if cfg is None:
        print(
            f"esxi-skill: profile '{profile}' not configured "
            f"({config_path(profile)} missing)",
            file=sys.stderr,
        )
        print(
            f"  Run setup: python3 {Path(__file__)} setup --host HOST --user USER …",
            file=sys.stderr,
        )
        return 2

    if not govc_path():
        print("esxi-skill: govc not in PATH", file=sys.stderr)
        print(f"  Run setup to install.", file=sys.stderr)
        return 4

    service = cfg.get("cred_service") or f"govc-{cfg['host']}"
    pw = get_password(service, cfg["username"], profile)
    if not pw:
        print(
            f"esxi-skill: password not in keychain (service={service} account={cfg['username']})",
            file=sys.stderr,
        )
        print(f"  Re-run setup and complete the password step.", file=sys.stderr)
        return 3

    env = build_govc_env(cfg, pw)
    # Replace current process with govc. Password lives only in govc's env.
    try:
        os.execvpe(govc_path(), [govc_path()] + args.govc_args, env)
    except OSError as e:
        print(f"esxi-skill: execvpe failed: {e}", file=sys.stderr)
        return 5


# ─── main ─────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="esxi", description=__doc__.splitlines()[0])
    parser.add_argument("--profile", default=os.environ.get("ESXI_PROFILE", "default"),
                        help="config profile (default: 'default', or $ESXI_PROFILE)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_pre = sub.add_parser("preflight", help="JSON status check")
    sp_pre.set_defaults(func=cmd_preflight)

    sp_setup = sub.add_parser("setup", help="install govc + write config + print password cmd")
    sp_setup.add_argument("--host", required=True)
    sp_setup.add_argument("--user", default="root")
    sp_setup.add_argument("--insecure", type=int, default=1, help="1 = skip TLS verify")
    sp_setup.add_argument("--datacenter", default="ha-datacenter")
    sp_setup.set_defaults(func=cmd_setup)

    sp_g = sub.add_parser("g", help="govc wrapper (loads creds, execs govc)")
    sp_g.add_argument("govc_args", nargs=argparse.REMAINDER,
                      help="arguments passed through to govc")
    sp_g.set_defaults(func=cmd_g)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
