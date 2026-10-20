from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .identity import Principal, resolve_principal


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    return resolve_principal(request, db)


def need_client(p: Principal = Depends(get_principal)) -> Principal:
    if p.client is None:
        raise HTTPException(400, "Elegí un cliente para operar.")
    return p


def need_super(p: Principal = Depends(get_principal)) -> Principal:
    if not p.is_super_admin:
        raise HTTPException(403, "Solo el super admin puede hacer esto.")
    return p


def forbid(action: str) -> None:
    raise HTTPException(403, "No tenés permiso para esta acción (%s)." % action)


def authorize(p: Principal, action: str, resources: str | list[str]) -> None:
    if not p.can(action, resources):
        forbid(action)
