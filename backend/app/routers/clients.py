from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..identity import Principal
from ..models import Client, Product, Project, User
from ..modules import clean_modules
from ..schemas import ClientCreate, ClientOut, ClientUpdate
from ..services.clients import create_client

router = APIRouter(prefix="/api/clients", tags=["clientes"], dependencies=[Depends(need_super)])

ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _theme(raw: dict) -> dict:
    out: dict = {}
    if raw.get("accent"):
        if not ACCENT_RE.match(str(raw["accent"])):
            raise HTTPException(400, "El color de acento debe ser #RRGGBB.")
        out["accent"] = str(raw["accent"])
    if raw.get("logo_url"):
        url = str(raw["logo_url"])
        if len(url) > 500 or not url.startswith(("https://", "http://", "/")):
            raise HTTPException(400, "El logo debe ser una URL http(s).")
        out["logo_url"] = url
    return out


def _counts(db: Session) -> dict[str, dict[str, int]]:
    def by_client(model):
        return dict(db.execute(select(model.client_id, func.count()).group_by(model.client_id)).all())

    users, projects, products = by_client(User), by_client(Project), by_client(Product)
    return {"users": users, "projects": projects, "products": products}


def _out(c: Client, counts: dict) -> ClientOut:
    return ClientOut(
        **{k: getattr(c, k) for k in ("id", "name", "slug", "modules", "theme", "disabled", "created_at")},
        user_count=counts["users"].get(c.id, 0),
        project_count=counts["projects"].get(c.id, 0),
        product_count=counts["products"].get(c.id, 0),
    )


def _get(db: Session, client_id: str) -> Client:
    c = db.get(Client, client_id)
    if c is None:
        raise HTTPException(404, "El cliente no existe.")
    return c


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    counts = _counts(db)
    return [_out(c, counts) for c in db.scalars(select(Client).order_by(Client.name))]


@router.post("", response_model=ClientOut, status_code=201)
def create(body: ClientCreate, db: Session = Depends(get_db)):
    try:
        modules = None if body.modules is None else clean_modules(body.modules)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if db.scalar(select(Client.id).where(func.lower(Client.name) == body.name.strip().lower())):
        raise HTTPException(409, "Ya existe un cliente con ese nombre.")
    c = create_client(db, body.name, modules, _theme(body.theme or {}))
    db.commit()
    return _out(c, _counts(db))


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    return _out(_get(db, client_id), _counts(db))


@router.patch("/{client_id}", response_model=ClientOut)
def update(client_id: str, body: ClientUpdate, db: Session = Depends(get_db)):
    c = _get(db, client_id)
    if body.name is not None:
        dup = db.scalar(select(Client.id).where(func.lower(Client.name) == body.name.strip().lower(), Client.id != c.id))
        if dup:
            raise HTTPException(409, "Ya existe un cliente con ese nombre.")
        c.name = body.name.strip()
    if body.modules is not None:
        try:
            c.modules = clean_modules(body.modules)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if body.theme is not None:
        c.theme = _theme(body.theme)
    if body.disabled is not None:
        c.disabled = body.disabled
    db.commit()
    return _out(c, _counts(db))


@router.delete("/{client_id}", status_code=204)
def delete(client_id: str, db: Session = Depends(get_db)):
    c = _get(db, client_id)
    n = db.scalar(select(func.count()).select_from(Product).where(Product.client_id == c.id))
    if n:
        raise HTTPException(409, "No se puede borrar: tiene %d producto/s. Deshabilitalo en su lugar." % n)
    db.delete(c)
    db.commit()
