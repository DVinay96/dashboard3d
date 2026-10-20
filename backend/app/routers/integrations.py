from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..models import Integration, now
from ..schemas import EventInfo, IntegrationCreate, IntegrationOut, IntegrationsOut, IntegrationUpdate, TestResult
from ..services import integrations as svc
from ..services.secrets import SecretsError

router = APIRouter(prefix="/api/integrations", tags=["integraciones"], dependencies=[Depends(need_super)])


def _get(db: Session, integration_id: str) -> Integration:
    i = db.get(Integration, integration_id)
    if i is None:
        raise HTTPException(404, "La integración no existe.")
    return i


def _out(i: Integration) -> IntegrationOut:
    return IntegrationOut(**svc.public(i))


def _fail(e: Exception):
    raise HTTPException(400, str(e))


@router.get("", response_model=IntegrationsOut)
def list_integrations(db: Session = Depends(get_db)):
    order = {k: n for n, k in enumerate(svc.KINDS)}
    rows = sorted(db.scalars(select(Integration)), key=lambda i: (order[i.kind], i.created_at))
    return IntegrationsOut(
        items=[_out(i) for i in rows],
        events=[EventInfo(name=k, description=v) for k, v in svc.EVENTS.items()],
    )


@router.post("", response_model=IntegrationOut, status_code=201)
def create(body: IntegrationCreate, db: Session = Depends(get_db)):
    if body.kind not in ("mcp", "webhook"):
        raise HTTPException(400, "Solo se pueden crear conectores MCP o webhooks.")
    try:
        config = svc.clean_config(body.kind, body.config)
        secrets = svc.clean_secrets(body.kind, body.secrets)
    except svc.IntegrationError as e:
        _fail(e)
    i = Integration(kind=body.kind, name=body.name.strip(), enabled=body.enabled, config=config)
    svc.apply_secrets(i, secrets, [])
    db.add(i)
    db.commit()
    return _out(i)


@router.put("/{integration_id}", response_model=IntegrationOut)
def update(integration_id: str, body: IntegrationUpdate, db: Session = Depends(get_db)):
    i = _get(db, integration_id)
    try:
        if body.config is not None:
            i.config = svc.clean_config(i.kind, {**(i.config or {}), **body.config})
        new = svc.clean_secrets(i.kind, body.secrets)
        clear = [c for c in body.clear_secrets if c in svc.SECRET_FIELDS[i.kind]]
    except svc.IntegrationError as e:
        _fail(e)
    if new or clear:
        svc.apply_secrets(i, new, clear)
    if body.name is not None:
        i.name = body.name.strip()
    if body.enabled is not None:
        i.enabled = body.enabled
    i.last_status = i.last_message = i.last_at = None
    i.updated_at = now()
    db.commit()
    return _out(i)


@router.delete("/{integration_id}", status_code=204)
def delete(integration_id: str, db: Session = Depends(get_db)):
    i = _get(db, integration_id)
    if i.kind in svc.SINGLETON:
        raise HTTPException(400, "Esta integración no se puede borrar; desactivala o borra sus credenciales.")
    db.delete(i)
    db.commit()


@router.post("/{integration_id}/test", response_model=TestResult)
def test(integration_id: str, db: Session = Depends(get_db)):
    _get(db, integration_id)
    db.close()
    try:
        ok, message = svc.test(integration_id)
    except (svc.IntegrationError, SecretsError) as e:
        return TestResult(ok=False, message=str(e))
    return TestResult(ok=ok, message=message)
