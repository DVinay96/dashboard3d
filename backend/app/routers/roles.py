from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..models import Client, Role, User, user_roles
from ..policy import PolicyError, clean_statements
from ..schemas import RoleIn, RoleOut

router = APIRouter(prefix="/api/roles", tags=["roles"], dependencies=[Depends(need_super)])


def _out(db: Session, r: Role) -> RoleOut:
    n = db.scalar(select(func.count()).select_from(user_roles).where(user_roles.c.role_id == r.id)) or 0
    return RoleOut(id=r.id, client_id=r.client_id, name=r.name, description=r.description,
                   statements=r.statements, builtin=r.builtin, user_count=n)


def _get(db: Session, rid: str) -> Role:
    r = db.get(Role, rid)
    if r is None:
        raise HTTPException(404, "El rol no existe.")
    return r


def _check_name(db: Session, name: str, client_id: str | None, exclude: str | None = None) -> None:
    q = select(Role.id).where(func.lower(Role.name) == name.lower(), Role.id != (exclude or ""))
    q = q.where(Role.client_id.is_(None) if client_id is None else Role.client_id == client_id)
    if db.scalar(q):
        raise HTTPException(409, "Ya existe un rol llamado '%s'." % name)


@router.get("", response_model=list[RoleOut])
def list_roles(client_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Role).order_by(Role.builtin.desc(), Role.name)
    if client_id:
        q = q.where(or_(Role.client_id.is_(None), Role.client_id == client_id))
    return [_out(db, r) for r in db.scalars(q)]


@router.post("", response_model=RoleOut, status_code=201)
def create(body: RoleIn, db: Session = Depends(get_db)):
    if body.client_id and db.get(Client, body.client_id) is None:
        raise HTTPException(400, "El cliente no existe.")
    name = body.name.strip()
    _check_name(db, name, body.client_id)
    try:
        statements = clean_statements(body.statements)
    except PolicyError as e:
        raise HTTPException(400, str(e))
    r = Role(client_id=body.client_id, name=name, description=body.description.strip(),
             statements=statements, builtin=False)
    db.add(r)
    db.commit()
    return _out(db, r)


@router.put("/{role_id}", response_model=RoleOut)
def update(role_id: str, body: RoleIn, db: Session = Depends(get_db)):
    r = _get(db, role_id)
    name = body.name.strip()
    _check_name(db, name, r.client_id, exclude=r.id)
    try:
        r.statements = clean_statements(body.statements)
    except PolicyError as e:
        raise HTTPException(400, str(e))
    r.name, r.description = name, body.description.strip()
    db.commit()
    return _out(db, r)


@router.delete("/{role_id}", status_code=204)
def delete(role_id: str, db: Session = Depends(get_db)):
    r = _get(db, role_id)
    if r.builtin:
        raise HTTPException(400, "Los roles incluidos no se pueden borrar.")
    users = db.scalars(select(User.email).join(user_roles).where(user_roles.c.role_id == r.id)).all()
    if users:
        raise HTTPException(409, "No se puede borrar: %d usuario/s lo tienen (%s)." % (len(users), ", ".join(users[:3])))
    db.delete(r)
    db.commit()
