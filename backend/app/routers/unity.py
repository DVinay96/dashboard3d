from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import authorize, forbid, need_client
from ..identity import Principal
from ..models import Product, UnitySync
from ..schemas import UnityStatusOut, UnitySyncOut
from ..services import jobs
from ..services import unity as unity_svc
from ..services.unity_sync import SyncError, prepare, sync_product

router = APIRouter(prefix="/api", tags=["unity"])


def sync_out(r: UnitySync, product_name: str) -> UnitySyncOut:
    return UnitySyncOut(
        id=r.id, product_id=r.product_id, product_name=product_name, project_id=r.project_id, project_name=r.project.name,
        unity_project_id=r.unity_project_id, status=r.status, error=r.error, attempts=r.attempts or 0,
        unity_asset_id=r.unity_asset_id, created_at=r.created_at, updated_at=r.updated_at, synced_at=r.synced_at,
    )


def _resources(pr: Product) -> list[str]:
    return ["project/%s/product/%s" % (x.id, pr.id) for x in pr.projects] or ["project/none/product/%s" % pr.id]


@router.get("/unity/status", response_model=UnityStatusOut)
def status(p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    if "unity:read" not in p.possible_actions():
        forbid("unity:read")
    rows = db.scalars(
        select(UnitySync).join(Product, Product.id == UnitySync.product_id)
        .where(Product.client_id == p.client.id).order_by(UnitySync.updated_at.desc())
    ).all()
    products = {r.product_id: db.get(Product, r.product_id) for r in rows}
    visible = [r for r in rows if p.can("unity:read", _resources(products[r.product_id]))]
    return UnityStatusOut(configured=unity_svc.is_configured(),
                          items=[sync_out(r, products[r.product_id].name) for r in visible])


@router.post("/products/{pid}/unity/sync", response_model=list[UnitySyncOut], status_code=202)
def sync(pid: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = db.get(Product, pid)
    if pr is None or pr.client_id != p.client.id:
        raise HTTPException(404, "El producto no existe.")
    authorize(p, "unity:sync", _resources(pr))
    if not unity_svc.is_configured():
        raise HTTPException(409, "Unity no esta configurado en el servidor (faltan UNITY_KEY_ID y UNITY_KEY_SECRET).")
    try:
        prepare(db, pr)
        db.commit()
    except SyncError as e:
        raise HTTPException(e.status, str(e))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya se esta sincronizando.")
    jobs.submit(sync_product, pr.id)
    db.expire_all()
    return [sync_out(r, pr.name) for r in pr.unity_syncs]
