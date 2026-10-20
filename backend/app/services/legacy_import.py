from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import DEFAULT_BASE_FIELDS
from ..config import get_settings
from ..models import Brand, Client, Product, Project
from ..modules import MODULES
from .clients import create_client
from .platform import get_setting, set_setting

logger = logging.getLogger("pipeline.legacy")

PRODUCT_FIELDS = (
    "name", "slug", "status", "stage", "progress", "source", "retexture_prompt", "task_id", "endpoint",
    "credits", "error", "options", "photos", "raw_files", "textures", "thumbnail_url", "metrics",
    "original_filename", "created_at", "updated_at",
)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def legacy_present() -> bool:
    s = get_settings()
    return (s.data_dir / "brands.json").exists() or any(s.products_dir.glob("*/meta.json"))


def import_legacy(db: Session) -> dict | None:
    if get_setting(db, "legacy_imported", False) or db.scalar(select(Client.id)) or not legacy_present():
        return None
    s = get_settings()

    client = create_client(db, "Cliente por defecto", modules=list(MODULES))
    project = db.scalar(select(Project).where(Project.client_id == client.id))

    cat = _read_json(s.data_dir / "brands.json") or {}
    client.base_fields = cat.get("base_fields") or [dict(f) for f in DEFAULT_BASE_FIELDS]
    brand_ids = set()
    for b in cat.get("brands") or []:
        db.add(Brand(id=b["id"], client_id=client.id, name=b.get("name", ""), slug=b.get("slug", ""),
                     notes=b.get("notes", ""), fields=b.get("fields") or [], pipeline=b.get("pipeline") or {},
                     created_at=b.get("created_at") or 0))
        brand_ids.add(b["id"])
    db.flush()

    cfg = _read_json(s.data_dir / "config.json") or {}
    for key in ("blender_path", "unity_export_dir"):
        if cfg.get(key):
            set_setting(db, key, cfg[key])

    metas = []
    for meta_file in s.products_dir.glob("*/meta.json"):
        m = _read_json(meta_file)
        if isinstance(m, dict) and m.get("id"):
            metas.append(m)
    metas.sort(key=lambda m: m.get("created_at", 0))

    ids = set()
    for m in metas:
        kwargs = {k: m[k] for k in PRODUCT_FIELDS if m.get(k) is not None}
        p = Product(id=m["id"], client_id=client.id, meta=m.get("metadata") or {},
                    brand_id=m.get("brand_id") if m.get("brand_id") in brand_ids else None, **kwargs)
        p.projects = [project]
        db.add(p)
        ids.add(m["id"])
    db.flush()
    for m in metas:
        if m.get("parent_id") in ids:
            db.get(Product, m["id"]).parent_id = m["parent_id"]

    set_setting(db, "legacy_imported", True)
    summary = {"client": client.id, "brands": len(brand_ids), "products": len(metas)}
    logger.warning("Importados datos de la versión anterior: %s", summary)
    return summary
