from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from textwrap import dedent
from typing import Any

from backend.app.core.config import ROOT_DIR


MAX_OUTPUT_CHARS = 12000
DEFAULT_TIMEOUT_SECONDS = 10
SCRIPTS_DIR = ROOT_DIR / "scripts"
SCRIPT_LOG_DIR = ROOT_DIR / "log"
SCRIPT_HELPERS_DOC = dedent(
    """
    可用函数:
    - open_app(app, args=None, once=True, cwd=None): 非阻塞启动应用；支持字符串或数组参数，自动展开 `$HOME` 和 `~`；Hyprland/Wayland 下启动 VSCode 会自动使用 X11 Ozone；once=True 时只有启动命令和 cwd 完全相同才不重复启动。
    - list_node_files(): 返回当前节点可见文件列表。
    - get_node_file(file_id=None, name=None): 按 file_id 或 name 读取当前节点文件。
    - log(value): 打印 JSON 或字符串。

    可用变量:
    - NODE_ID: 当前节点 id
    - SCRIPT_ARGS: 本次执行参数 dict
    - NODE_DATABASES: 当前节点挂载的知识条目
    - NODE_FILES: 当前节点文件附件
    - TRIGGER: 当前触发源，可能为 enter / schedule / manual_run
    """
).strip()


def run_python_script(
    node: dict[str, Any],
    script: dict[str, Any],
    args: dict[str, Any] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    trigger: str = "manual_run",
) -> dict[str, Any]:
    code = str(script.get("code") or "")
    if not code.strip():
        return {
            "script_id": script.get("id"),
            "node_id": node.get("id"),
            "status": "blocked",
            "returncode": None,
            "stdout": "",
            "stderr": "脚本内容为空。",
            "trigger": trigger,
        }
    attachments = node_attachments(node)
    SCRIPTS_DIR.mkdir(exist_ok=True)
    SCRIPT_LOG_DIR.mkdir(exist_ok=True)
    ensure_script_runtime_files()
    run_id = uuid.uuid4().hex[:12]
    script_filename = f"{safe_filename(node.get('id') or 'node')}-{safe_filename(script.get('id') or 'script')}.py"
    script_path = SCRIPTS_DIR / script_filename
    runner_path = SCRIPTS_DIR / "runner.py"
    log_path = SCRIPT_LOG_DIR / f"node-script-{run_id}.json"
    script_path.write_text(f"from utils import *\n\n{code}\n", encoding="utf-8")
    env = {
        **os.environ,
        "ME_AGENT_NODE_SCRIPT_PATH": str(script_path),
        "ME_AGENT_NODE_SCRIPT_LOG_PATH": str(log_path),
        "ME_AGENT_NODE_SCRIPT_TIMEOUT": str(max(1, min(timeout_seconds, 60))),
        "ME_AGENT_NODE_SCRIPT_CODE": code,
        "ME_AGENT_SCRIPTS_DIR": str(SCRIPTS_DIR),
        "ME_AGENT_NODE_SCRIPT_RESULT": json.dumps(
            {
                "script_id": script.get("id"),
                "script_name": script.get("name"),
                "node_id": node.get("id"),
                "trigger": trigger,
                "status": "running",
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "log_path": str(log_path),
                "script_path": str(script_path),
                "run_id": run_id,
            },
            ensure_ascii=False,
        ),
        "ME_AGENT_NODE_ID": str(node.get("id") or ""),
        "ME_AGENT_SCRIPT_ARGS": json.dumps(args or {}, ensure_ascii=False),
        "ME_AGENT_NODE_DATABASES": json.dumps(attachments.get("databases", []), ensure_ascii=False),
        "ME_AGENT_NODE_FILES": json.dumps(attachments.get("files", []), ensure_ascii=False),
        "ME_AGENT_SCRIPT_TRIGGER": trigger,
    }
    process = subprocess.Popen(
        [sys.executable, str(runner_path)],
        cwd=SCRIPTS_DIR,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    return {
        "script_id": script.get("id"),
        "node_id": node.get("id"),
        "status": "started",
        "returncode": None,
        "stdout": "",
        "stderr": f"脚本已在后台启动，日志写入 {log_path}",
        "trigger": trigger,
        "pid": process.pid,
        "log_path": str(log_path),
        "script_path": str(script_path),
    }


def run_triggered_scripts(
    node: dict[str, Any],
    trigger: str,
    args: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for script in node_attachments(node).get("scripts", []):
        if should_trigger_script(script, trigger):
            results.append(run_python_script(node, script, args=args, trigger=trigger))
    return results


def should_trigger_script(script: dict[str, Any], trigger: str) -> bool:
    if trigger in {"enter", "manual_enter", "ai_switch"}:
        return bool(script.get("trigger_on_enter"))
    if trigger == "schedule":
        rules = script.get("schedule_rules")
        return isinstance(rules, list) and len(rules) > 0
    return False


def node_attachments(node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    memory = node.get("memory") if isinstance(node.get("memory"), dict) else {}
    attachments = memory.get("attachments") if isinstance(memory.get("attachments"), dict) else {}
    return {
        "databases": list_items(attachments.get("databases")),
        "scripts": list_items(attachments.get("scripts")),
        "files": list_items(attachments.get("files")),
    }


def find_script(node: dict[str, Any], script_id: str) -> dict[str, Any] | None:
    for script in node_attachments(node).get("scripts", []):
        if str(script.get("id") or "") == script_id:
            return script
    return None


def list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def ensure_script_runtime_files() -> None:
    (SCRIPTS_DIR / "utils.py").write_text(utils_code(), encoding="utf-8")
    (SCRIPTS_DIR / "runner.py").write_text(runner_code(), encoding="utf-8")


def utils_code() -> str:
    return dedent(
        r'''
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
        '''
    ).strip() + "\n"


def runner_code() -> str:
    return dedent(
        r'''
        from __future__ import annotations

        import json
        import os
        import subprocess
        import sys
        import time
        import traceback
        from pathlib import Path

        script_path = Path(os.environ["ME_AGENT_NODE_SCRIPT_PATH"])
        log_path = Path(os.environ["ME_AGENT_NODE_SCRIPT_LOG_PATH"])
        timeout_seconds = int(os.environ.get("ME_AGENT_NODE_SCRIPT_TIMEOUT", "10"))
        result = json.loads(os.environ.get("ME_AGENT_NODE_SCRIPT_RESULT", "{}") or "{}")

        def write_result(payload):
            log_path.parent.mkdir(parents=True, exist_ok=True)
            payload["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            result.update(
                {
                    "status": "completed" if completed.returncode == 0 else "failed",
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "code": os.environ.get("ME_AGENT_NODE_SCRIPT_CODE", ""),
                }
            )
        except subprocess.TimeoutExpired as exc:
            result.update(
                {
                    "status": "timeout",
                    "returncode": None,
                    "stdout": exc.stdout or "",
                    "stderr": (exc.stderr or "") + f"\n脚本执行超过 {timeout_seconds} 秒。",
                    "code": os.environ.get("ME_AGENT_NODE_SCRIPT_CODE", ""),
                }
            )
        except Exception:
            result.update(
                {
                    "status": "failed",
                    "returncode": None,
                    "stdout": "",
                    "stderr": traceback.format_exc(),
                    "code": os.environ.get("ME_AGENT_NODE_SCRIPT_CODE", ""),
                }
            )
        write_result(result)
        '''
    ).strip()


def safe_filename(value: Any) -> str:
    normalized = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value))
    return normalized.strip("-_")[:48] or "script"


def truncate(value: str) -> str:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value
    return value[:MAX_OUTPUT_CHARS] + "\n...输出已截断"
