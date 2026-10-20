from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..identity import Principal
from ..models import Client, Role, User
from ..schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["usuarios"], dependencies=[Depends(need_super)])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, display_name=u.display_name, client_id=u.client_id,
        client_name=u.client.name if u.client else None, is_super_admin=u.is_super_admin,
        disabled=u.disabled, role_ids=[r.id for r in u.roles], role_names=[r.name for r in u.roles],
        created_at=u.created_at,
    )


def _roles(db: Session, role_ids: list[str], client_id: str | None) -> list[Role]:
    out = []
    for rid in dict.fromkeys(role_ids):
        r = db.get(Role, rid)
        if r is None:
            raise HTTPException(400, "El rol '%s' no existe." % rid)
        if r.client_id not in (None, client_id):
            raise HTTPException(400, "El rol '%s' pertenece a otro cliente." % r.name)
        out.append(r)
    return out


def _other_active_supers(db: Session, uid: str) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.is_super_admin, ~User.disabled, User.id != uid)
    ) or 0


def _get(db: Session, uid: str) -> User:
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(404, "El usuario no existe.")
    return u


@router.get("", response_model=list[UserOut])
def list_users(client_id: str | None = None, db: Session = Depends(get_db)):
    q = select(User).order_by(User.email)
    if client_id:
        q = q.where(User.client_id == client_id)
    return [_out(u) for u in db.scalars(q)]


@router.post("", response_model=UserOut, status_code=201)
def create(body: UserCreate, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Email invalido.")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Ya existe un usuario con ese email.")
    client_id = None
    if not body.is_super_admin:
        if not body.client_id or db.get(Client, body.client_id) is None:
            raise HTTPException(400, "Elegí el cliente al que pertenece el usuario.")
        client_id = body.client_id
    u = User(email=email, display_name=body.display_name.strip(), client_id=client_id,
             is_super_admin=body.is_super_admin)
    u.roles = _roles(db, body.role_ids, client_id)
    db.add(u)
    db.commit()
    return _out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update(user_id: str, body: UserUpdate, db: Session = Depends(get_db), p: Principal = Depends(need_super)):
    u = _get(db, user_id)
    if body.disabled and not u.disabled:
        if u.id == p.user.id:
            raise HTTPException(400, "No podés deshabilitar tu propia cuenta.")
        if u.is_super_admin and not _other_active_supers(db, u.id):
            raise HTTPException(400, "Debe quedar al menos un super admin activo.")
    if body.display_name is not None:
        u.display_name = body.display_name.strip()
    if body.role_ids is not None:
        u.roles = _roles(db, body.role_ids, u.client_id)
    if body.disabled is not None:
        u.disabled = body.disabled
    db.commit()
    return _out(u)


@router.delete("/{user_id}", status_code=204)
def delete(user_id: str, db: Session = Depends(get_db), p: Principal = Depends(need_super)):
    u = _get(db, user_id)
    if u.id == p.user.id:
        raise HTTPException(400, "No podés borrar tu propia cuenta.")
    if u.is_super_admin and not _other_active_supers(db, u.id):
        raise HTTPException(400, "Debe quedar al menos un super admin activo.")
    db.delete(u)
    db.commit()
