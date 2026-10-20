from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..identity import LOCAL_ADMIN_EMAIL
from ..models import Product, Role, UnitySync, User, now
from ..policy import BUILTIN_ROLES
from .pipeline import ACTIVE


def seed_roles(db: Session) -> None:
    for spec in BUILTIN_ROLES:
        if db.get(Role, spec["id"]) is None:
            db.add(Role(
                id=spec["id"], client_id=None, name=spec["name"], description=spec["description"],
                statements=[{"effect": "allow", "actions": spec["actions"], "resources": ["*"]}],
                builtin=True,
            ))


def ensure_local_admin(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == LOCAL_ADMIN_EMAIL))
    if user is None:
        user = User(email=LOCAL_ADMIN_EMAIL, display_name="Super admin local", is_super_admin=True)
        db.add(user)
        db.flush()
    return user


def fail_interrupted(db: Session) -> int:
    res = db.execute(
        update(Product)
        .where(Product.status.in_(ACTIVE))
        .values(status="FAILED", error="Interrumpido al reiniciar el servidor.", updated_at=now())
    )
    db.execute(
        update(UnitySync)
        .where(UnitySync.status.in_(("PENDING", "SYNCING")))
        .values(status="FAILED", error="Interrumpido al reiniciar el servidor.", updated_at=now())
    )
    return res.rowcount or 0
