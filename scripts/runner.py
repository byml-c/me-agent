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