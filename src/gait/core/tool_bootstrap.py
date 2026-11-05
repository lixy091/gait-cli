import os
import platform
import re
import shutil
import subprocess
import sys
import shlex


RECOMMENDED_NODE_MAJOR = 24
NVM_INSTALL_COMMAND = "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash"
OPENSPEC_PACKAGE = "@fission-ai/openspec@latest"
INSTALL_HINTS = {
    "node": f"Install Node.js {RECOMMENDED_NODE_MAJOR}; on macOS/Linux: ensure nvm exists, run `{NVM_INSTALL_COMMAND}`, then `. \"$HOME/.nvm/nvm.sh\" && nvm install 24 && nvm alias default 24`.",
    "npm": "npm is shipped with Node.js; reinstall/update Node.js.",
    "openspec": f"npm install -g {OPENSPEC_PACKAGE}",
}


def current_platform() -> str:
    return sys.platform


def node_major_version() -> int | None:
    executable = shutil.which("node")
    if not executable:
        return None
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    match = re.search(r"v?(\d+)", result.stdout or result.stderr)
    return int(match.group(1)) if match else None


def detect_tools() -> dict[str, bool]:
    return {
        "node": node_major_version() is not None and node_major_version() >= RECOMMENDED_NODE_MAJOR,
        "npm": shutil.which("npm") is not None,
        "openspec": shutil.which("openspec") is not None,
    }


def run_streaming(command: str, *, shell: bool = True) -> None:
    """Run an installer while inheriting stdout/stderr from the current terminal."""
    completed = subprocess.run(command, shell=shell, check=False)
    if completed.returncode:
        raise RuntimeError(f"Installation command failed ({completed.returncode}): {command}")


def run_command(arguments: list[str], *, cwd) -> None:
    """Run an installed CLI, including npm's .cmd shims on Windows."""
    if os.name == "nt":
        command = subprocess.list2cmdline(arguments)
        result = subprocess.run(command, cwd=cwd, shell=True, check=False)
    else:
        result = subprocess.run(arguments, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(arguments)}")


def _installation_commands(missing: list[str], platform_name: str) -> list[str]:
    commands: list[str] = []
    if "node" in missing:
        if shutil.which("nvm") is None:
            commands.append(f"bash -c '{NVM_INSTALL_COMMAND}'")
        commands.append('. "$HOME/.nvm/nvm.sh" && nvm install 24 && nvm alias default 24')
    if "npm" in missing:
        # npm is provided by Node; make the prerequisite explicit rather than invoking a nonexistent installer.
        if "node" not in missing:
            raise RuntimeError("npm is missing although Node.js is available. " + INSTALL_HINTS["npm"])
    if "openspec" in missing:
        commands.append(f"npm install -g {OPENSPEC_PACKAGE}")
    return commands


def _install_missing(missing: list[str], platform_name: str) -> None:
    if platform_name not in {"linux", "darwin"}:
        raise RuntimeError("Automatic installation is supported only on macOS/Linux. " + " ".join(INSTALL_HINTS[name] for name in missing))
    pending = list(missing)
    if "node" in pending:
        for command in _installation_commands(["node"], platform_name):
            run_streaming(command)
        if node_major_version() is None or node_major_version() < RECOMMENDED_NODE_MAJOR:
            raise RuntimeError("Node.js 24 is still unavailable after nvm installation")
        pending.remove("node")
    if "npm" in pending:
        if shutil.which("npm") is None:
            raise RuntimeError(INSTALL_HINTS["npm"])
        pending.remove("npm")
    if "openspec" in pending:
        run_streaming(f"npm install -g {OPENSPEC_PACKAGE}")


def bootstrap_tools(mode: str, *, interactive: bool | None = None, platform_name: str | None = None) -> dict[str, bool]:
    if mode == "skip":
        return {}
    interactive = sys.stdin.isatty() if interactive is None else interactive
    platform_name = platform_name or current_platform()
    status = detect_tools()
    missing = [name for name, found in status.items() if not found]
    if not missing:
        print("node, npm, and openspec are available.")
        return status
    print("Missing or unsupported tools: " + ", ".join(missing))
    for name in missing:
        print(f"{name}: {INSTALL_HINTS[name]}")
    if mode == "check":
        return status
    if not interactive or platform_name not in {"linux", "darwin"}:
        print("Use gait init --tools install in an interactive macOS/Linux terminal, or install manually.")
        raise RuntimeError("Cannot install missing tools in this environment; run gait init --tools install in an interactive macOS/Linux terminal. " + " ".join(INSTALL_HINTS[n] for n in missing))
    if mode == "auto":
        for name in missing:
            if not input(f"Install {name}? [y/N] ").strip().lower().startswith("y"):
                raise RuntimeError(f"Required tool installation declined: {name}")
    _install_missing(missing, platform_name)
    status = detect_tools()
    missing = [name for name, found in status.items() if not found]
    if missing:
        raise RuntimeError("Tools remain unavailable after installation: " + ", ".join(missing))
    return status


def ensure_openspec_available() -> None:
    if not detect_tools()["openspec"]:
        raise RuntimeError(f"OpenSpec is required. {INSTALL_HINTS['openspec']}")
