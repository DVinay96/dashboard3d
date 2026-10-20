from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env_file(path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    auth_mode: str
    meshy_api_key: str
    meshy_base: str
    blender_path: str
    job_workers: int
    poll_seconds: float
    poll_timeout: float
    frontend_dist: Path
    unity_key_id: str
    unity_key_secret: str
    unity_api_base: str
    allowed_hosts: list[str]

    @property
    def products_dir(self) -> Path:
        return self.data_dir / "products"


@lru_cache
def get_settings() -> Settings:
    if not os.environ.get("PIPELINE_SKIP_DOTENV"):
        load_env_file()
    data_dir = Path(os.environ.get("PIPELINE_DATA_DIR") or ROOT / "data").resolve()
    return Settings(
        data_dir=data_dir,
        database_url=os.environ.get("DATABASE_URL") or "sqlite:///%s" % (data_dir / "pipeline.db"),
        auth_mode=os.environ.get("AUTH_MODE", "none").strip().lower(),
        meshy_api_key=os.environ.get("MESHY_API_KEY", "").strip(),
        meshy_base=os.environ.get("MESHY_BASE", "https://api.meshy.ai/openapi/v1"),
        blender_path=os.environ.get("BLENDER_PATH", "").strip(),
        job_workers=int(os.environ.get("JOB_WORKERS", "2")),
        poll_seconds=float(os.environ.get("POLL_SECONDS", "5")),
        poll_timeout=float(os.environ.get("POLL_TIMEOUT", str(60 * 25))),
        frontend_dist=Path(os.environ.get("FRONTEND_DIST") or ROOT / "frontend" / "dist"),
        unity_key_id=os.environ.get("UNITY_KEY_ID", "").strip(),
        unity_key_secret=os.environ.get("UNITY_KEY_SECRET", "").strip(),
        unity_api_base=os.environ.get("UNITY_API_BASE", "https://services.api.unity.com/assets/v1").rstrip("/"),
        allowed_hosts=[h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()],
    )
