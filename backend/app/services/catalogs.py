from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Brand, Client


def brand_dict(b: Brand) -> dict:
    return {
        "id": b.id, "name": b.name, "slug": b.slug, "notes": b.notes,
        "fields": b.fields or [], "pipeline": b.pipeline or {}, "created_at": b.created_at,
    }


def catalog_for(db: Session, client: Client) -> dict:
    brands = db.scalars(select(Brand).where(Brand.client_id == client.id).order_by(Brand.created_at)).all()
    return {"base_fields": client.base_fields or [], "brands": [brand_dict(b) for b in brands]}
