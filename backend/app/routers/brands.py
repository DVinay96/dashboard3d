from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import catalog as cat_mod
from ..db import get_db
from ..deps import authorize, forbid, need_client
from ..identity import Principal
from ..models import Brand, Product
from ..schemas import BaseFieldsIn, BrandFieldsOut, BrandIn, BrandOut, CatalogOut
from ..services.catalogs import brand_dict, catalog_for

router = APIRouter(prefix="/api/brands", tags=["marcas"])


def brand_res(brand_id: str) -> str:
    return "brand/%s" % (brand_id or "none")


def _get(db: Session, p: Principal, brand_id: str) -> Brand:
    b = db.get(Brand, brand_id)
    if b is None or b.client_id != p.client.id:
        raise HTTPException(404, "La marca no existe.")
    return b


@router.get("", response_model=CatalogOut)
def get_catalog(p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    if "brands:read" not in p.possible_actions():
        forbid("brands:read")
    cat = catalog_for(db, p.client)
    cat["brands"] = [b for b in cat["brands"] if p.can("brands:read", brand_res(b["id"]))]
    return cat


@router.put("/base-fields", response_model=CatalogOut)
def put_base_fields(body: BaseFieldsIn, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    authorize(p, "brands:update_base", "schema/base")
    try:
        p.client.base_fields = cat_mod.clean_fields(body.fields)
    except cat_mod.BrandError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return catalog_for(db, p.client)


@router.get("/{brand_id}/fields", response_model=BrandFieldsOut)
def brand_fields(brand_id: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    bid = "" if brand_id == "none" else brand_id
    authorize(p, "brands:read", brand_res(bid))
    cat = catalog_for(db, p.client)
    brand = cat_mod.get_brand(cat, bid)
    if bid and brand is None:
        raise HTTPException(404, "La marca no existe.")
    return {"fields": cat_mod.fields_for(cat, bid), "pipeline": (brand or {}).get("pipeline", {})}


@router.post("", response_model=BrandOut, status_code=201)
def create(body: BrandIn, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    authorize(p, "brands:create", brand_res("new"))
    cat = catalog_for(db, p.client)
    try:
        data = cat_mod.clean_brand(body.model_dump(), cat)
    except cat_mod.BrandError as e:
        raise HTTPException(400, str(e))
    b = Brand(client_id=p.client.id, **{k: data[k] for k in ("id", "name", "slug", "notes", "fields", "pipeline", "created_at")})
    db.add(b)
    db.commit()
    return brand_dict(b)


@router.put("/{brand_id}", response_model=BrandOut)
def update(brand_id: str, body: BrandIn, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    b = _get(db, p, brand_id)
    authorize(p, "brands:update", brand_res(b.id))
    cat = catalog_for(db, p.client)
    try:
        data = cat_mod.clean_brand(dict(body.model_dump(), created_at=b.created_at), cat, b.id)
    except cat_mod.BrandError as e:
        raise HTTPException(400, str(e))
    b.name, b.slug, b.notes, b.fields, b.pipeline = (data[k] for k in ("name", "slug", "notes", "fields", "pipeline"))
    db.commit()
    return brand_dict(b)


@router.delete("/{brand_id}", status_code=204)
def delete(brand_id: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    b = _get(db, p, brand_id)
    authorize(p, "brands:delete", brand_res(b.id))
    names = db.scalars(select(Product.name).where(Product.brand_id == b.id).limit(3)).all()
    if names:
        n = db.scalar(select(func.count()).select_from(Product).where(Product.brand_id == b.id))
        raise HTTPException(409, "No se puede borrar: %d producto/s la usan (%s)." % (n, ", ".join(names)))
    db.delete(b)
    db.commit()
