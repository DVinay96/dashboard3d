from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..identity import Principal
from ..models import User
from ..modules import MODULES
from ..schemas import AccessRow

router = APIRouter(prefix="/api/access", tags=["accesos"], dependencies=[Depends(need_super)])


@router.get("", response_model=list[AccessRow])
def access(db: Session = Depends(get_db)):
    rows = []
    for u in db.scalars(select(User).order_by(User.email)):
        principal = Principal(u, u.client)
        blocked = u.disabled or bool(u.client and u.client.disabled)
        actions = [] if blocked else principal.possible_actions()
        rows.append(AccessRow(
            user_id=u.id, email=u.email, display_name=u.display_name, client_id=u.client_id,
            client_name=u.client.name if u.client else None, is_super_admin=u.is_super_admin,
            disabled=u.disabled, roles=[r.name for r in u.roles], client_modules=principal.modules(),
            effective_modules=[m for m, spec in MODULES.items() if any(a in actions for a in spec["actions"])],
            action_count=len(actions),
        ))
    return rows
