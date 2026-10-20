import hashlib
import hmac
import json
import logging
import time

from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Client, Integration, Product
from . import integrations, jobs
from .integrations import DeliveryError
from .mcp import McpError
from .secrets import SecretsError

logger = logging.getLogger("pipeline.events")

ATTEMPTS = 3
RETRY_SLEEP = 1.0


def product_payload(db: Session, product: Product) -> dict:
    client = db.get(Client, product.client_id)
    return {
        "client": {"id": client.id, "name": client.name, "slug": client.slug},
        "product": {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "status": product.status,
            "source": product.source,
            "brand": product.brand.name if product.brand else None,
            "metadata": dict(product.meta or {}),
            "error": product.error,
            "projects": [{"id": p.id, "name": p.name, "unity_project_id": p.unity_project_id} for p in product.projects],
            "created_by": product.created_by.email if product.created_by else None,
        },
        "unity": [
            {
                "project": r.project.name,
                "unity_project_id": r.unity_project_id,
                "status": r.status,
                "asset_id": r.unity_asset_id,
                "error": r.error,
            }
            for r in product.unity_syncs
        ],
    }


def emit(event: str, product_id: str) -> None:
    try:
        with session_scope() as db:
            product = db.get(Product, product_id)
            if product is None:
                return
            targets = [i.id for i in integrations.subscribed(db, event)]
            if not targets:
                return
            body = {"event": event, "occurred_at": time.time(), **product_payload(db, product)}
    except Exception:
        logger.exception("No se pudo armar el evento %s", event)
        return
    for target in targets:
        jobs.submit(deliver, target, body)


def sign(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def deliver_webhook(i: Integration, body: dict) -> None:
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "X-Pipeline-Event": str(body.get("event"))}
    secret = integrations.secrets_of(i).get("signing_secret", "")
    if secret:
        headers["X-Pipeline-Signature"] = sign(secret, raw)
    client = integrations.http_client()
    last = "sin respuesta"
    for attempt in range(ATTEMPTS):
        try:
            r = client.post(i.config["url"], content=raw, headers=headers)
            if r.status_code < 300:
                return
            last = "HTTP %d" % r.status_code
            if r.status_code < 500 and r.status_code != 429:
                break
        except Exception as e:
            last = str(e)
        if attempt < ATTEMPTS - 1:
            time.sleep(RETRY_SLEEP * (2**attempt))
    raise DeliveryError(last)


def deliver_mcp(i: Integration, body: dict) -> None:
    tool = (i.config or {}).get("event_tool")
    if not tool:
        return
    client = integrations.mcp_client(i)
    last: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            client.call_tool(tool, {"event": body["event"], "payload": body})
            return
        except McpError as e:
            last = e
        if attempt < ATTEMPTS - 1:
            time.sleep(RETRY_SLEEP * (2**attempt))
    raise last if last else DeliveryError("sin respuesta")


def deliver(integration_id: str, body: dict) -> None:
    with session_scope() as db:
        i = db.get(Integration, integration_id)
        if i is None or not i.enabled:
            return
        db.expunge(i)
    try:
        if i.kind == "webhook":
            deliver_webhook(i, body)
        else:
            deliver_mcp(i, body)
        integrations.record_result_by_id(integration_id, True, "Último evento entregado: %s" % body.get("event"))
    except (DeliveryError, McpError, SecretsError) as e:
        logger.warning("Falló la entrega de %s a %s: %s", body.get("event"), i.name, e)
        integrations.record_result_by_id(integration_id, False, "No se pudo entregar %s: %s" % (body.get("event"), e))
