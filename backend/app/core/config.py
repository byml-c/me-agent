from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]


def load_env_file(path: Path = ROOT_DIR / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    file_storage_path: Path
    openai_api_key: str | None
    openai_base_url: str
    openai_base_model: str


def get_settings() -> Settings:
    load_env_file()
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    return Settings(
        database_path=Path(os.getenv("ME_AGENT_DB", str(data_dir / "me_agent.sqlite3"))),
        file_storage_path=Path(os.getenv("ME_AGENT_FILE_STORAGE", str(data_dir / "uploads"))),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_base_model=os.getenv("OPENAI_BASE_MODEL", "gpt-4.1-mini"),
    )
