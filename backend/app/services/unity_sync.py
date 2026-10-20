from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Client, Product, UnitySync, now
from . import events, integrations, unity
from .files import log, product_dir

PENDING, SYNCING, SYNCED, FAILED = "PENDING", "SYNCING", "SYNCED", "FAILED"


class SyncError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def prepare(db: Session, product: Product) -> int:
    if product.status != "DONE":
        raise SyncError("Solo se sincronizan productos terminados y sin fallos de QA.", 409)
    targets = sorted((p for p in product.projects if p.unity_project_id), key=lambda p: (p.created_at, p.name))
    if not targets:
        raise SyncError(
            "Ninguno de los proyectos del producto tiene destino en Unity. Pedile al super admin que vincule el proyecto.")
    if any(r.status == SYNCING for r in product.unity_syncs):
        raise SyncError("Ya se esta sincronizando.", 409)

    existing = {r.project_id: r for r in product.unity_syncs}
    pending = 0
    for pr in targets:
        row = existing.get(pr.id)
        if row is None:
            row = UnitySync(product_id=product.id, project_id=pr.id, unity_project_id=pr.unity_project_id, created_at=now())
            product.unity_syncs.append(row)
        elif row.status == SYNCED and row.unity_project_id == pr.unity_project_id:
            continue
        row.unity_project_id = pr.unity_project_id
        row.status, row.error, row.attempts, row.updated_at = PENDING, None, (row.attempts or 0) + 1, now()
        pending += 1
    if not pending:
        raise SyncError("Ya esta sincronizado en todos sus proyectos.", 409)
    return pending


@dataclass
class _Row:
    id: str
    unity_project_id: str
    status: str
    asset_id: str | None
    version: str | None
    dataset_id: str | None
    files_done: list[str]
    submitted: bool
    order: tuple[float, str]


def _update(row_id: str, **patch) -> None:
    with session_scope() as db:
        db.execute(update(UnitySync).where(UnitySync.id == row_id).values(updated_at=now(), **patch))


def auto_sync(pid: str) -> None:
    with session_scope() as db:
        p = db.get(Product, pid)
        if p is None or p.status != "DONE":
            return
        owner = db.get(Client, p.client_id)
        if owner.disabled or "unity" not in (owner.modules or []):
            return
        creds = integrations.unity_credentials(db)
        if creds is None or not creds["auto_sync"]:
            return
        try:
            prepare(db, p)
            db.commit()
        except SyncError:
            return
    sync_product(pid)


def sync_product(pid: str) -> None:
    try:
        if _run(pid):
            events.emit("unity.synced", pid)
    except Exception as e:
        msg = str(e) if isinstance(e, (unity.UnityError, SyncError)) else f"{type(e).__name__}: {e}"
        log(pid, "Unity: ERROR %s" % msg)
        if not isinstance(e, (unity.UnityError, SyncError)):
            log(pid, traceback.format_exc())
        with session_scope() as db:
            db.execute(update(UnitySync).where(UnitySync.product_id == pid, UnitySync.status.in_((PENDING, SYNCING)))
                       .values(status=FAILED, error=msg, updated_at=now()))
        events.emit("unity.failed", pid)


def _files_to_upload(pid: str, metrics: dict | None, slug: str) -> list[Path]:
    out = product_dir(pid) / "out"
    names = list((metrics or {}).get("exported", {}).values()) + [slug + ".metadata.json"]
    files = [out / n for n in dict.fromkeys(names) if (out / n).is_file()]
    if not any(f.suffix in (".glb", ".fbx") for f in files):
        raise unity.UnityError("El producto no tiene modelos exportados para subir.")
    return files


def _run(pid: str) -> bool:
    client = unity.get_client()
    if client is None:
        raise unity.UnityError("Unity no esta configurado en el servidor (faltan UNITY_KEY_ID y UNITY_KEY_SECRET).")

    with session_scope() as db:
        p = db.get(Product, pid)
        if p is None:
            return False
        info = {
            "name": p.name, "slug": p.slug, "metrics": p.metrics, "meta": dict(p.meta or {}),
            "brand": p.brand.name if p.brand else "", "brand_slug": p.brand.slug if p.brand else "",
            "creator": p.created_by.email if p.created_by else "",
        }
        rows = [_Row(r.id, r.unity_project_id, r.status, r.unity_asset_id, r.unity_asset_version,
                     r.unity_dataset_id, list(r.files_done or []), bool(r.submitted),
                     (r.created_at, r.project.name)) for r in p.unity_syncs]
        client_row = db.get(Client, p.client_id)
        info["client"], info["client_slug"] = client_row.name, client_row.slug

    rows.sort(key=lambda r: r.order)
    todo = [r for r in rows if r.status == PENDING]
    if not todo:
        return False
    for r in todo:
        _update(r.id, status=SYNCING, error=None)

    home = next((r for r in rows if r.asset_id), None)
    log(pid, "Unity: sincronizando %d destino(s)" % len(todo))

    if home is None:
        home = todo[0]
        desc = " · ".join(x for x in (
            f"Cliente: {info['client']}", f"Marca: {info['brand']}" if info["brand"] else "",
            f"SKU: {info['meta'].get('sku')}" if info["meta"].get("sku") else "",
            f"Creado por: {info['creator']}" if info["creator"] else "") if x)
        tags = [t for t in ("pipeline3d", info["client_slug"], info["brand_slug"]) if t]
        a = client.create_asset(home.unity_project_id, info["name"], desc, tags)
        home.asset_id, home.version, home.dataset_id = a["asset_id"], a["version"], a["dataset_id"]
        _update(home.id, unity_asset_id=home.asset_id, unity_asset_version=home.version, unity_dataset_id=home.dataset_id)
        log(pid, "Unity: asset %s creado en el proyecto %s" % (home.asset_id, home.unity_project_id))

    if not home.submitted:
        assert home.asset_id and home.version and home.dataset_id
        for f in _files_to_upload(pid, info["metrics"], info["slug"]):
            if f.name in home.files_done:
                continue
            url = client.create_file(home.unity_project_id, home.asset_id, home.version, home.dataset_id, f.name,
                                     f.stat().st_size, main=f.suffix == ".glb", description=f"Pipeline 3D: {f.name}")
            client.upload(url, f)
            client.finalize(home.unity_project_id, home.asset_id, home.version, home.dataset_id, f.name)
            home.files_done.append(f.name)
            _update(home.id, files_done=list(home.files_done))
            log(pid, "Unity: subido %s" % f.name)
        client.autosubmit(home.unity_project_id, home.asset_id, home.version,
                          "Generado por Pipeline 3D" + (f" ({info['creator']})" if info["creator"] else "")
                          + time.strftime(" — %Y-%m-%d"))
        home.submitted = True
        _update(home.id, submitted=True)
        log(pid, "Unity: versión enviada")

    for r in todo:
        if r.id != home.id and r.unity_project_id != home.unity_project_id:
            client.link(home.unity_project_id, home.asset_id, r.unity_project_id)
            log(pid, "Unity: enlazado al proyecto %s" % r.unity_project_id)
        _update(r.id, status=SYNCED, error=None, synced_at=now(), unity_asset_id=home.asset_id,
                unity_asset_version=home.version, unity_dataset_id=home.dataset_id, submitted=True)
    log(pid, "Unity: sincronización completa")
    return True
