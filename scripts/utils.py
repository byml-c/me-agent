from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

NODE_ID = os.environ.get("ME_AGENT_NODE_ID", "")
SCRIPT_ARGS = json.loads(os.environ.get("ME_AGENT_SCRIPT_ARGS", "{}") or "{}")
NODE_DATABASES = json.loads(os.environ.get("ME_AGENT_NODE_DATABASES", "[]") or "[]")
NODE_FILES = json.loads(os.environ.get("ME_AGENT_NODE_FILES", "[]") or "[]")
TRIGGER = os.environ.get("ME_AGENT_SCRIPT_TRIGGER", "manual_run")
SCRIPTS_DIR = Path(os.environ.get("ME_AGENT_SCRIPTS_DIR", os.getcwd())).resolve()

def _expand_token(value):
    return os.path.expanduser(os.path.expandvars(str(value)))

def _cmdline(app, args):
    normalized_args = shlex.split(args) if isinstance(args, str) else [str(item) for item in (args or [])]
    return [_expand_token(app), *[_expand_token(item) for item in normalized_args]]

def _desktop_args(app, args):
    basename = os.path.basename(str(app))
    is_vscode = basename in {"code", "code-insiders", "codium", "vscodium"}
    is_hyprland_wayland = (
        os.environ.get("XDG_CURRENT_DESKTOP", "").lower() == "hyprland"
        and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )
    has_ozone_arg = any(str(item).startswith("--ozone-platform=") for item in args)
    if is_vscode and is_hyprland_wayland and not has_ozone_arg:
        return ["--ozone-platform=x11", *args]
    return args

def _resolve_cwd(cwd=None):
    raw_cwd = str(cwd) if cwd is not None else str(SCRIPTS_DIR)
    return str(Path(_expand_token(raw_cwd)).resolve())

def _proc_cmdline(pid):
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="replace") for part in raw.split(b"\0") if part]

def _proc_cwd(pid):
    try:
        return str(Path(f"/proc/{pid}/cwd").resolve())
    except OSError:
        return ""

def _find_existing(cmd, cwd):
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        if _proc_cmdline(entry.name) == cmd and _proc_cwd(entry.name) == cwd:
            return {"pid": int(entry.name), "command": cmd, "cwd": cwd}
    return None

def _desktop_env():
    env = dict(os.environ)
    runtime_dir = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    env.setdefault("XDG_RUNTIME_DIR", runtime_dir)
    bus_path = os.path.join(runtime_dir, "bus")
    if "DBUS_SESSION_BUS_ADDRESS" not in env and os.path.exists(bus_path):
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"
    if "WAYLAND_DISPLAY" not in env and "DISPLAY" not in env and os.path.isdir(runtime_dir):
        for name in os.listdir(runtime_dir):
            if name.startswith("wayland-") and os.path.exists(os.path.join(runtime_dir, name)):
                env["WAYLAND_DISPLAY"] = name
                break
    return env

def open_app(app, args=None, once=True, cwd=None):
    cmd = _cmdline(app, _desktop_args(app, shlex.split(args) if isinstance(args, str) else [str(item) for item in (args or [])]))
    binary = shutil.which(cmd[0]) or _expand_token(cmd[0])
    resolved = [binary, *cmd[1:]]
    if not os.path.isabs(resolved[0]) and not shutil.which(resolved[0]):
        return {"ok": False, "created": False, "error": f"executable not found: {resolved[0]}", "command": resolved}
    if os.path.isabs(resolved[0]) and not os.path.exists(resolved[0]):
        return {"ok": False, "created": False, "error": f"executable not found: {resolved[0]}", "command": resolved}
    resolved_cwd = _resolve_cwd(cwd)
    if once:
        existing = _find_existing(resolved, resolved_cwd)
        if existing:
            return {"ok": True, "created": False, **existing}
    process = subprocess.Popen(
        resolved,
        cwd=resolved_cwd,
        env=_desktop_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    return {"ok": True, "created": True, "pid": process.pid, "command": resolved, "cwd": resolved_cwd}

def list_node_files():
    return NODE_FILES

def get_node_file(file_id=None, name=None):
    for item in NODE_FILES:
        if file_id and str(item.get("file_id") or item.get("id") or "") == str(file_id):
            return item
        if name and str(item.get("name") or "") == str(name):
            return item
    return None

def log(value):
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False))
    else:
        print(value)
