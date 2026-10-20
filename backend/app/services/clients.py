from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import DEFAULT_BASE_FIELDS, slug_key
from ..models import Client, Project
from ..modules import DEFAULT_MODULES

DEFAULT_PROJECT = "General"


def unique_slug(db: Session, name: str) -> str:
    base = slug_key(name).replace("_", "-") or "cliente"
    slug, n = base, 2
    while db.scalar(select(Client.id).where(Client.slug == slug)):
        slug = "%s-%d" % (base, n)
        n += 1
    return slug


def create_client(db: Session, name: str, modules: list[str] | None = None, theme: dict | None = None) -> Client:
    client = Client(
        name=name.strip(),
        slug=unique_slug(db, name),
        modules=list(DEFAULT_MODULES if modules is None else modules),
        base_fields=[dict(f) for f in DEFAULT_BASE_FIELDS],
        theme=theme or {},
    )
    db.add(client)
    db.flush()
    db.add(Project(client_id=client.id, name=DEFAULT_PROJECT, description="Proyecto inicial"))
    db.flush()
    return client
