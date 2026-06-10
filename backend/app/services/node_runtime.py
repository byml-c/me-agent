from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any


MAX_OUTPUT_CHARS = 12000
DEFAULT_TIMEOUT_SECONDS = 10
SCRIPT_HELPERS_DOC = dedent(
    """
    可用函数:
    - open_app(app, args=None, once=True): 非阻塞启动应用；支持字符串或数组参数，自动展开 `$HOME` 和 `~`；once=True 时若当前进程已存在则不重复启动。
    - list_node_files(): 返回当前节点可见文件列表。
    - get_node_file(file_id=None, name=None): 按 file_id 或 name 读取当前节点文件。
    - log(value): 打印 JSON 或字符串。

    可用变量:
    - NODE_ID: 当前节点 id
    - SCRIPT_ARGS: 本次执行参数 dict
    - NODE_DATABASES: 当前节点挂载的知识条目
    - NODE_FILES: 当前节点文件附件
    - TRIGGER: 当前触发源，可能为 manual_enter / ai_switch / manual_run
    """
).strip()

SCRIPT_PRELUDE = dedent(
    """
    import json
    import os
    import shutil
    import shlex
    import subprocess

    NODE_ID = os.environ.get("ME_AGENT_NODE_ID", "")
    SCRIPT_ARGS = json.loads(os.environ.get("ME_AGENT_SCRIPT_ARGS", "{}") or "{}")
    NODE_DATABASES = json.loads(os.environ.get("ME_AGENT_NODE_DATABASES", "[]") or "[]")
    NODE_FILES = json.loads(os.environ.get("ME_AGENT_NODE_FILES", "[]") or "[]")
    TRIGGER = os.environ.get("ME_AGENT_SCRIPT_TRIGGER", "manual_run")

    def _expand_token(value):
        return os.path.expanduser(os.path.expandvars(str(value)))

    def _cmdline(app, args):
        normalized_args = shlex.split(args) if isinstance(args, str) else [str(item) for item in (args or [])]
        return [_expand_token(app), *[_expand_token(item) for item in normalized_args]]

    def _find_existing(cmd):
        try:
            result = subprocess.run(["pgrep", "-af", os.path.basename(str(cmd[0]))], capture_output=True, text=True, check=False)
        except Exception:
            return None
        expected_args = [str(item) for item in cmd[1:]]
        for line in (result.stdout or "").splitlines():
            if all(arg in line for arg in expected_args):
                return line
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

    def open_app(app, args=None, once=True):
        cmd = _cmdline(app, args)
        binary = shutil.which(cmd[0]) or _expand_token(cmd[0])
        resolved = [binary, *cmd[1:]]
        if not os.path.isabs(resolved[0]) and not shutil.which(resolved[0]):
            return {"ok": False, "created": False, "error": f"executable not found: {resolved[0]}", "command": resolved}
        if os.path.isabs(resolved[0]) and not os.path.exists(resolved[0]):
            return {"ok": False, "created": False, "error": f"executable not found: {resolved[0]}", "command": resolved}
        if once and _find_existing(resolved):
            return {"ok": True, "created": False, "command": resolved}
        process = subprocess.Popen(
            resolved,
            cwd=os.path.expanduser("~"),
            env=_desktop_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return {"ok": True, "created": True, "pid": process.pid, "command": resolved}

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
    with tempfile.TemporaryDirectory(prefix="me-agent-node-script-") as temp_dir:
        script_path = Path(temp_dir) / "script.py"
        script_path.write_text(f"{SCRIPT_PRELUDE}\n\n{code}\n", encoding="utf-8")
        env = {
            **os.environ,
            "ME_AGENT_NODE_ID": str(node.get("id") or ""),
            "ME_AGENT_SCRIPT_ARGS": json.dumps(args or {}, ensure_ascii=False),
            "ME_AGENT_NODE_DATABASES": json.dumps(attachments.get("databases", []), ensure_ascii=False),
            "ME_AGENT_NODE_FILES": json.dumps(attachments.get("files", []), ensure_ascii=False),
            "ME_AGENT_SCRIPT_TRIGGER": trigger,
        }
        try:
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=max(1, min(timeout_seconds, 60)),
                check=False,
            )
            return {
                "script_id": script.get("id"),
                "node_id": node.get("id"),
                "status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "stdout": truncate(completed.stdout),
                "stderr": truncate(completed.stderr),
                "trigger": trigger,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "script_id": script.get("id"),
                "node_id": node.get("id"),
                "status": "timeout",
                "returncode": None,
                "stdout": truncate(exc.stdout or ""),
                "stderr": truncate((exc.stderr or "") + f"\\n脚本执行超过 {timeout_seconds} 秒。"),
                "trigger": trigger,
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
    if trigger == "manual_enter":
        return bool(script.get("trigger_on_enter"))
    if trigger == "ai_switch":
        return bool(script.get("trigger_on_ai_switch"))
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


def truncate(value: str) -> str:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value
    return value[:MAX_OUTPUT_CHARS] + "\n...输出已截断"
