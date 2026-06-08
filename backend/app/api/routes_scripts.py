from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.schemas import ScriptRunRequest
from backend.app.db.session import get_db
from backend.app.services import graph_store

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.post("/{script_id}/run")
def run_script(script_id: str, payload: ScriptRunRequest):
    with get_db() as db:
        result = {
            "script_id": script_id,
            "node_id": payload.node_id,
            "status": "blocked",
            "stdout": "",
            "stderr": "MVP 默认禁用脚本执行。请在后续版本接入沙盒 runtime 后再启用。",
        }
        graph_store.append_event(db, "ScriptExecuted", "system", result)
        return result
