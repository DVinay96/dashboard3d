from __future__ import annotations

import os
import shutil

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Setting
from . import integrations

EDITABLE = ("blender_path", "unity_export_dir")


def find_blender() -> str:
    for cand in (
        shutil.which("blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/opt/homebrew/bin/blender",
        "/usr/local/bin/blender",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    ):
        if cand and os.path.exists(cand):
            return cand
    return ""


def get_setting(db: Session, key: str, default=""):
    row = db.get(Setting, key)
    return default if row is None or row.value is None else row.value


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def resolve_blender(db: Session) -> str:
    return str(get_setting(db, "blender_path") or get_settings().blender_path or find_blender())


def public_settings(db: Session) -> dict:
    s = get_settings()
    blender = resolve_blender(db)
    key = integrations.meshy_key(db)
    return {
        "blender_path": blender,
        "blender_ok": bool(blender and os.path.exists(blender)),
        "unity_export_dir": str(get_setting(db, "unity_export_dir")),
        "meshy_key_set": bool(key),
        "meshy_key_masked": ("..." + key[-4:]) if key else "",
        "unity_configured": integrations.unity_credentials(db) is not None,
        "unity_api_base": (integrations.unity_credentials(db) or {}).get("api_base", s.unity_api_base),
    }
