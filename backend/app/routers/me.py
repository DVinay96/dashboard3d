from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_principal
from ..identity import LOCAL_ADMIN_EMAIL, Principal
from ..models import Client, User
from ..modules import module_list
from ..schemas import ClientBrief, DevIdentities, DevIdentity, MeOut, ModuleOut, UserRef

router = APIRouter(prefix="/api", tags=["sesión"])


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal)):
    return MeOut(
        user=UserRef.model_validate(p.user),
        is_super_admin=p.is_super_admin,
        client=ClientBrief.model_validate(p.client) if p.client else None,
        modules=p.modules(),
        can=p.possible_actions(),
        auth_mode=get_settings().auth_mode,
    )


@router.get("/modules", response_model=list[ModuleOut])
def modules(_: Principal = Depends(get_principal)):
    return module_list()


@router.get("/dev/identities", response_model=DevIdentities)
def dev_identities(db: Session = Depends(get_db)):
    if get_settings().auth_mode != "none":
        raise HTTPException(404, "No disponible.")
    clients = db.scalars(select(Client).order_by(Client.name)).all()
    names = {c.id: c.name for c in clients}
    users = db.scalars(select(User).order_by(User.email)).all()
    return DevIdentities(
        clients=[ClientBrief.model_validate(c) for c in clients],
        users=[
            DevIdentity(
                id=u.id, email=u.email, display_name=u.display_name, client_id=u.client_id,
                client_name=names.get(u.client_id), is_super_admin=u.is_super_admin,
            )
            for u in users
            if u.email != LOCAL_ADMIN_EMAIL
        ],
    )
