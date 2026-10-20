import os
import time
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import new_session, session_scope
from ..models import Integration, now
from . import meshy
from .mcp import McpClient, McpError
from .secrets import SecretsError, decrypt, encrypt

KINDS = ("meshy", "unity", "mcp", "webhook")
SINGLETON = ("meshy", "unity")
SECRET_FIELDS = {
    "meshy": ("api_key",),
    "unity": ("key_id", "key_secret"),
    "mcp": ("token",),
    "webhook": ("signing_secret",),
}
EVENTS = {
    "product.done": "Un producto terminó el procesamiento sin fallos de QA",
    "product.qa_failed": "Un producto terminó con fallos de QA",
    "product.failed": "El procesamiento de un producto falló",
    "unity.synced": "Un producto se publicó en Unity",
    "unity.failed": "Falló la publicación de un producto en Unity",
}
DEFAULT_NAMES = {"meshy": "Generador 3D (Meshy)", "unity": "Unity Asset Manager"}


class IntegrationError(ValueError):
    pass


class DeliveryError(Exception):
    pass


def http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(15.0))


def ensure_singletons(db: Session) -> None:
    present = {i.kind for i in db.scalars(select(Integration).where(Integration.kind.in_(SINGLETON)))}
    for kind in SINGLETON:
        if kind not in present:
            config = {"api_base": "", "auto_sync": True} if kind == "unity" else {}
            db.add(Integration(kind=kind, name=DEFAULT_NAMES[kind], config=config))


def secrets_of(i: Integration) -> dict:
    return decrypt(i.secrets_enc)


def _singleton(db: Session, kind: str) -> Integration | None:
    return db.scalar(select(Integration).where(Integration.kind == kind))


def meshy_key(db: Session | None = None) -> str:
    def resolve(session: Session) -> str:
        i = _singleton(session, "meshy")
        if i and i.enabled:
            try:
                key = secrets_of(i).get("api_key", "")
            except SecretsError:
                key = ""
            if key:
                return key
        return get_settings().meshy_api_key

    if db is not None:
        return resolve(db)
    with session_scope() as session:
        return resolve(session)


def unity_credentials(db: Session | None = None) -> dict | None:
    def resolve(session: Session) -> dict | None:
        s = get_settings()
        i = _singleton(session, "unity")
        if i is not None and not i.enabled:
            return None
        cfg = dict(i.config or {}) if i else {}
        try:
            sec = secrets_of(i) if i else {}
        except SecretsError:
            sec = {}
        key_id = sec.get("key_id") or s.unity_key_id
        key_secret = sec.get("key_secret") or s.unity_key_secret
        if not (key_id and key_secret):
            return None
        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "api_base": (cfg.get("api_base") or s.unity_api_base).rstrip("/"),
            "auto_sync": bool(cfg.get("auto_sync", True)),
        }

    if db is not None:
        return resolve(db)
    with session_scope() as session:
        return resolve(session)


def _url(value, what: str) -> str:
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise IntegrationError("%s debe ser una URL http(s) valida." % what)
    return value


def clean_config(kind: str, raw: dict | None) -> dict:
    raw = raw or {}
    if kind == "meshy":
        return {}
    if kind == "unity":
        base = str(raw.get("api_base") or "").strip()
        return {"api_base": _url(base, "La URL de la API") if base else "", "auto_sync": bool(raw.get("auto_sync", True))}
    events = raw.get("events") or []
    if not isinstance(events, list) or any(e not in EVENTS for e in events):
        raise IntegrationError("Eventos desconocidos: %s" % ", ".join(map(str, events)))
    out = {"url": _url(raw.get("url"), "La URL"), "events": [e for e in EVENTS if e in events]}
    if kind == "mcp":
        out["event_tool"] = str(raw.get("event_tool") or "").strip()[:120]
    return out


def clean_secrets(kind: str, values: dict | None) -> dict:
    allowed = SECRET_FIELDS[kind]
    out = {}
    for k, v in (values or {}).items():
        if k not in allowed:
            raise IntegrationError("Campo secreto desconocido: %s" % k)
        v = str(v or "").strip()
        if v:
            out[k] = v[:2000]
    return out


def apply_secrets(i: Integration, new: dict, clear: list[str]) -> None:
    try:
        current = secrets_of(i)
    except SecretsError:
        current = {}
    for k in clear:
        current.pop(k, None)
    current.update(new)
    i.secrets_enc = encrypt(current)


def public(i: Integration) -> dict:
    try:
        sec = secrets_of(i)
    except SecretsError:
        sec = {}
    state = {}
    for field in SECRET_FIELDS[i.kind]:
        value = sec.get(field, "")
        state[field] = {"set": bool(value), "hint": ("…" + value[-4:]) if len(value) > 8 else ("•••" if value else "")}
    return {
        "id": i.id,
        "kind": i.kind,
        "name": i.name,
        "enabled": i.enabled,
        "config": i.config or {},
        "secrets": state,
        "last_status": i.last_status,
        "last_message": i.last_message,
        "last_at": i.last_at,
    }


def mcp_client(i: Integration) -> McpClient:
    return McpClient(i.config["url"], secrets_of(i).get("token", ""), http=http_client())


def _check(i: Integration) -> str:
    if i.kind == "meshy":
        key = meshy_key_of(i)
        if not key:
            raise IntegrationError("Falta la API key.")
        res = meshy.request("GET", "/balance", key)
        return "Conectado. Créditos disponibles: %s" % res.get("balance", "?")
    if i.kind == "unity":
        from . import unity

        client = unity.get_client()
        if client is None:
            raise IntegrationError("Faltan el ID y el secreto de la cuenta de servicio.")
        client.ping()
        return "Conectado al Asset Manager de Unity."
    if i.kind == "mcp":
        client = mcp_client(i)
        info = client.initialize().get("serverInfo", {})
        tools = [t.get("name") for t in client.list_tools()]
        tool = (i.config or {}).get("event_tool")
        if tool and tool not in tools:
            raise IntegrationError("Conectado, pero el servidor no tiene la herramienta '%s'." % tool)
        label = " ".join(x for x in (info.get("name"), info.get("version")) if x) or "servidor MCP"
        return "Conectado a %s. Herramientas: %d." % (label, len(tools))
    from .events import deliver_webhook

    deliver_webhook(i, {"event": "ping", "occurred_at": time.time()})
    return "El destino respondió correctamente."


def meshy_key_of(i: Integration) -> str:
    try:
        return secrets_of(i).get("api_key", "") or get_settings().meshy_api_key
    except SecretsError:
        return ""


def test(integration_id: str) -> tuple[bool, str]:
    with session_scope() as db:
        i = db.get(Integration, integration_id)
        if i is None:
            raise IntegrationError("La integración no existe.")
        try:
            message, ok = _check(i), True
        except (IntegrationError, DeliveryError, McpError, meshy.MeshyError, SecretsError) as e:
            message, ok = str(e), False
        except Exception as e:
            message, ok = "%s: %s" % (type(e).__name__, e), False
        record_result(i, ok, message)
        return ok, message


def record_result(i: Integration, ok: bool, message: str) -> None:
    i.last_status = "OK" if ok else "FAILED"
    i.last_message = message[:500]
    i.last_at = now()


def record_result_by_id(integration_id: str, ok: bool, message: str) -> None:
    with session_scope() as db:
        i = db.get(Integration, integration_id)
        if i is not None:
            record_result(i, ok, message)


def subscribed(db: Session, event: str) -> list[Integration]:
    rows = db.scalars(select(Integration).where(Integration.kind.in_(("mcp", "webhook")), Integration.enabled))
    return [i for i in rows if event in (i.config or {}).get("events", [])]


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
