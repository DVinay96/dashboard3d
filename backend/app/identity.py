from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Client, User
from .modules import ACTION_MODULE, ALL_ACTIONS
from .policy import action_in_statements, is_allowed_any

LOCAL_ADMIN_EMAIL = "admin@local"
ACT_AS = "x-act-as"
CLIENT_ID = "x-client-id"


class Principal:

    def __init__(self, user: User, client: Client | None):
        self.user = user
        self.client = client

    @property
    def is_super_admin(self) -> bool:
        return self.user.is_super_admin

    def statements(self) -> list[dict]:
        return [st for role in self.user.roles for st in role.statements]

    def _module_on(self, action: str) -> bool:
        return bool(self.client) and ACTION_MODULE.get(action) in (self.client.modules or [])

    def can(self, action: str, resources: str | list[str]) -> bool:
        if self.is_super_admin:
            return True
        if action not in ALL_ACTIONS or not self._module_on(action):
            return False
        if isinstance(resources, str):
            resources = [resources]
        return is_allowed_any(self.statements(), action, resources)

    def possible_actions(self) -> list[str]:
        if self.is_super_admin:
            return sorted(ALL_ACTIONS)
        sts = self.statements()
        return sorted(a for a in ALL_ACTIONS if self._module_on(a) and action_in_statements(sts, a))

    def modules(self) -> list[str]:
        from .modules import MODULES

        if self.client:
            return list(self.client.modules or [])
        return list(MODULES)


def _hint(request: Request, name: str) -> str:
    return (request.headers.get(name) or request.cookies.get(name) or "").strip()


def resolve_principal(request: Request, db: Session) -> Principal:
    if get_settings().auth_mode != "none":
        raise HTTPException(501, "AUTH_MODE no soportado todavía: solo 'none'.")

    act_as = _hint(request, ACT_AS)
    if act_as:
        user = db.get(User, act_as) or db.scalar(select(User).where(User.email == act_as.lower()))
        if not user:
            raise HTTPException(401, "El usuario indicado en X-Act-As no existe.")
    else:
        user = db.scalar(select(User).where(User.email == LOCAL_ADMIN_EMAIL))
        if not user:
            raise HTTPException(503, "Falta el super admin local (el servidor no terminó de arrancar).")
    if user.disabled:
        raise HTTPException(403, "Tu usuario esta deshabilitado.")

    client = None
    if user.is_super_admin:
        cid = _hint(request, CLIENT_ID)
        if cid:
            client = db.get(Client, cid)
            if not client:
                raise HTTPException(404, "El cliente indicado no existe.")
    else:
        client = user.client
        if not client:
            raise HTTPException(403, "Tu usuario no pertenece a ningún cliente.")
        if client.disabled:
            raise HTTPException(403, "Tu cliente esta deshabilitado.")
    return Principal(user, client)
