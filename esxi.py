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


# ─── Private venv (for `keyring` on Windows; no global pip install) ──────

def data_dir() -> Path:
    """Per-OS user-level data directory for esxi-skill private files (venv)."""
    sysname = platform.system()
    if sysname == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sysname == "Darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "esxi-skill"

def _venv_dir() -> Path:
    return data_dir() / "venv"

def _venv_python() -> Path:
    v = _venv_dir()
    if platform.system() == "Windows":
        return v / "Scripts" / "python.exe"
    return v / "bin" / "python"

def _venv_site_packages() -> Optional[Path]:
    v = _venv_dir()
    if not v.exists():
        return None
    # Unix: lib/pythonX.Y/site-packages   Windows: Lib/site-packages
    cands = list(v.glob("lib/python*/site-packages")) + list(v.glob("Lib/site-packages"))
    return cands[0] if cands else None

def _try_import_keyring():
    """Import `keyring` from the current env or from our private venv.
    Returns the module or None. No global install is performed."""
    try:
        import keyring  # type: ignore
        return keyring
    except ImportError:
        pass
    sp = _venv_site_packages()
    if sp is not None and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))
        try:
            import keyring  # type: ignore
            return keyring
        except ImportError:
            pass
    return None

def ensure_keyring_venv() -> Path:
    """Create a private venv in data_dir() and pip-install `keyring` into it.
    Returns the venv path. Does NOT touch any global site-packages."""
    import venv as stdlib_venv  # local import to keep cold-start light
    vd = _venv_dir()
    if _try_import_keyring() is not None:
        return vd  # already usable
    vd.parent.mkdir(parents=True, exist_ok=True)
    if not vd.exists():
        print(f"[setup] creating private venv at {vd}", file=sys.stderr)
        stdlib_venv.create(vd, with_pip=True, clear=False)
    py = _venv_python()
    if not py.exists():
        raise RuntimeError(f"venv python not found at {py}")
    print("[setup] installing keyring into private venv (no global install)…", file=sys.stderr)
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "keyring"]
    )
    return vd


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
        # Prefer `keyring` (Windows Credential Manager via DPAPI). keyring is
        # installed into a private venv under %LOCALAPPDATA%\esxi-skill\venv —
        # no global pip install. See ensure_keyring_venv().
        kr = _try_import_keyring()
        if kr is not None:
            try:
                return kr.get_password(service, account)
            except Exception:
                pass  # fall through to file fallback
        # Fallback: DPAPI-encrypted hex file. PowerShell's `ConvertFrom-SecureString`
        # (no -Key) binds ciphertext to current user + current machine.
        cf = cred_file_path(profile)
        if not cf.exists():
            return None
        ps = (
            f"$s = Get-Content -LiteralPath {json.dumps(str(cf))}; "
            f"$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR("
            f"(ConvertTo-SecureString $s)); "
            f"try {{ [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) }} "
            f"finally {{ [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }}"
        )
        r = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
        if r.returncode != 0:
            return None
        return r.stdout.rstrip("\r\n")
    else:
        raise KeychainError(f"Unsupported platform: {sysname}")

def set_password(service: str, account: str, password: str, profile: str = "default") -> None:
    """Store password in the OS-appropriate keychain backend.
    Used by `set-password` subcommand; NOT recommended for macOS where the
    native `security -U -w` interactive prompt is stronger (no Python
    intermediary). On Linux+libsecret, `secret-tool store` is also stronger.
    The primary value of this helper is uniform UX on Windows and Linux-no-
    libsecret, where native CLI alternatives are awkward."""
    sysname = platform.system()
    if sysname == "Darwin":
        r = _run(["security", "add-generic-password",
                  "-a", account, "-s", service, "-U", "-w", password])
        if r.returncode != 0:
            raise KeychainError(f"security add-generic-password failed: {r.stderr.strip()}")
    elif sysname == "Linux":
        if shutil.which("secret-tool"):
            r = _run(
                ["secret-tool", "store", "--label", f"govc: {account} @ {service}",
                 "service", service, "account", account],
                input_=password,
            )
            if r.returncode != 0:
                raise KeychainError(f"secret-tool store failed: {r.stderr.strip()}")
        else:
            cf = cred_file_path(profile)
            cf.parent.mkdir(parents=True, exist_ok=True)
            try:
                cf.parent.chmod(0o700)
            except OSError:
                pass
            # Write with restrictive umask so creation permissions are tight
            old_umask = os.umask(0o077)
            try:
                cf.write_text(password)
                cf.chmod(0o600)
            finally:
                os.umask(old_umask)
    elif sysname == "Windows":
        # Prefer keyring → Windows Credential Manager. If keyring isn't installed
        # yet, create the private venv and install it now.
        kr = _try_import_keyring()
        if kr is None:
            try:
                ensure_keyring_venv()
                kr = _try_import_keyring()
            except Exception as e:
                print(
                    f"[warn] failed to provision keyring venv: {e}\n"
                    "[warn] falling back to DPAPI-encrypted file.",
                    file=sys.stderr,
                )
        if kr is not None:
            kr.set_password(service, account, password)
            return
        # Fallback: DPAPI-encrypt via PowerShell, write hex to file (stdin feeds
        # the plaintext so it never lands in argv).
        cf = cred_file_path(profile)
        cf.parent.mkdir(parents=True, exist_ok=True)
        ps = (
            "$p = [Console]::In.ReadLine(); "
            "$sec = ConvertTo-SecureString -String $p -AsPlainText -Force; "
            "ConvertFrom-SecureString -SecureString $sec"
        )
        r = _run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            input_=password,
        )
        if r.returncode != 0:
            raise KeychainError(
                f"DPAPI encryption via PowerShell failed: {r.stderr.strip()}"
            )
        cf.write_text(r.stdout.rstrip("\r\n"))
        user = os.environ.get("USERNAME") or os.environ.get("USER")
        if user and shutil.which("icacls"):
            subprocess.run(
                ["icacls", str(cf), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
                capture_output=True,
            )
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
        kr = _try_import_keyring()
        if kr is not None:
            try:
                if kr.get_password(service, account) is not None:
                    return True
            except Exception:
                pass
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
    to store the password. Never executed by this module.

    Policy:
      - Default recommendation on every platform is a single line:
          python3 <esxi.py> set-password
        This uses `getpass` for hidden TTY input, then routes the password
        to the OS-appropriate backend inside esxi.py.
      - For the paranoid: on macOS we also document the direct `security`
        interactive command (password never enters Python); on Linux we also
        document `secret-tool store` (password goes through keyring daemon).
    """
    sysname = platform.system()
    py_cmd = f"python3 {Path(__file__)}"
    if profile != "default":
        py_cmd += f" --profile {profile}"

    primary = (
        "Run ONE command in your own terminal:\n"
        "\n"
        f"  {py_cmd} set-password\n"
        "\n"
        "  (hidden prompt, asks to retype; stores to the OS-appropriate\n"
        "   keychain automatically.)\n"
    )

    if sysname == "Darwin":
        return primary + (
            "\n"
            "Or (most secure — password never enters Python):\n"
            "\n"
            f"  security add-generic-password -a {account!r} -s {service!r} -U -w\n"
            "\n"
            "  (security prompts for the password itself; `man security` confirms\n"
            "   this is the intended use of trailing `-w` without a value.)\n"
        )
    elif sysname == "Linux" and shutil.which("secret-tool"):
        return primary + (
            "\n"
            "Or (libsecret native prompt — keyring daemon handles input):\n"
            "\n"
            f"  secret-tool store --label={f'govc: {account} @ {service}'!r} \\\n"
            f"    service {service!r} account {account!r}\n"
        )
    elif sysname == "Windows":
        vd = _venv_dir()
        cf = cred_file_path(profile)
        kr_ok = _try_import_keyring() is not None
        if kr_ok:
            storage_line = (
                f"ⓘ Storage: Windows Credential Manager via `keyring`\n"
                f"  (private venv at {vd}, NOT a global pip install).\n"
                f"  Manage entries visually in `credwiz` or `cmdkey /list`.\n"
            )
        else:
            storage_line = (
                f"ⓘ Storage: DPAPI-encrypted file at {cf} (NTFS ACL → current user).\n"
                f"  To upgrade to Windows Credential Manager, re-run:\n"
                f"    {py_cmd} setup --host <H> --user <U>\n"
                f"  which provisions a private keyring venv (no global pip install).\n"
            )
        return primary + (
            "\n"
            f"{storage_line}"
            "\n"
            "Alternative (no Python at all — direct DPAPI file via PowerShell):\n"
            "\n"
            f"  New-Item -ItemType Directory -Force -Path (Split-Path -Parent '{cf}') | Out-Null\n"
            "  Read-Host -AsSecureString -Prompt 'ESXi password' |\n"
            "    ConvertFrom-SecureString |\n"
            f"    Set-Content -LiteralPath '{cf}' -NoNewline\n"
            f"  icacls '{cf}' /inheritance:r /grant:r \"$($env:USERNAME):(R,W)\"\n"
        )
    else:
        # Linux-no-libsecret and any other POSIX
        return primary



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

    # 2.5. On Windows: provision a private venv with `keyring` so we can write
    # into Windows Credential Manager (DPAPI-backed). No global pip install.
    if platform.system() == "Windows" and not getattr(args, "no_keyring", False):
        try:
            ensure_keyring_venv()
            print("[setup] keyring available in private venv", file=sys.stderr)
        except Exception as e:
            print(
                f"[warn] could not provision keyring venv: {e}\n"
                "[warn] will fall back to DPAPI-encrypted file if needed.",
                file=sys.stderr,
            )

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


# ─── set-password ─────────────────────────────────────────────────────────

def cmd_set_password(args: argparse.Namespace) -> int:
    """Prompt for password (TTY-hidden via getpass) and store it."""
    import getpass

    profile = args.profile
    cfg = load_config(profile)
    if cfg is None:
        print(
            f"esxi-skill: no config for profile '{profile}'. Run setup first:\n"
            f"  python3 {Path(__file__)} setup --host … --user … …",
            file=sys.stderr,
        )
        return 2

    service = cfg.get("cred_service") or f"govc-{cfg['host']}"
    account = cfg["username"]
    host = cfg["host"]

    try:
        pw = getpass.getpass(f"ESXi password for {account}@{host}: ")
    except (KeyboardInterrupt, EOFError):
        print("\naborted", file=sys.stderr)
        return 1
    if not pw:
        print("empty password — aborted", file=sys.stderr)
        return 1
    try:
        confirm = getpass.getpass("Retype to confirm: ")
    except (KeyboardInterrupt, EOFError):
        print("\naborted", file=sys.stderr)
        return 1
    if confirm != pw:
        print("passwords do not match", file=sys.stderr)
        return 1

    try:
        set_password(service, account, pw, profile)
    except KeychainError as e:
        print(f"esxi-skill: {e}", file=sys.stderr)
        return 3
    finally:
        # Best-effort clear (Python strings are immutable so this doesn't
        # purge memory; we rely on GC. Still, drop references promptly.)
        pw = ""
        confirm = ""

    print(f"✓ password stored (service={service} account={account})")
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
    sp_setup.add_argument("--no-keyring", action="store_true",
                          help="(Windows) skip provisioning the private keyring venv; use DPAPI file fallback")
    sp_setup.set_defaults(func=cmd_setup)

    sp_sp = sub.add_parser("set-password",
                           help="prompt for password (hidden) and store in keychain")
    sp_sp.set_defaults(func=cmd_set_password)

    sp_g = sub.add_parser("g", help="govc wrapper (loads creds, execs govc)")
    sp_g.add_argument("govc_args", nargs=argparse.REMAINDER,
                      help="arguments passed through to govc")
    sp_g.set_defaults(func=cmd_g)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
