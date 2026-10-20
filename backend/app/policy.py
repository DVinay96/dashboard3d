from __future__ import annotations

import re
from fnmatch import fnmatchcase

from .modules import ALL_ACTIONS


class PolicyError(ValueError):
    pass


def _verdict(statements: list[dict], action: str, resource: str) -> str | None:
    allowed = False
    for st in statements:
        if not any(fnmatchcase(action, a) for a in st["actions"]):
            continue
        if not any(fnmatchcase(resource, r) for r in st["resources"]):
            continue
        if st["effect"] == "deny":
            return "deny"
        allowed = True
    return "allow" if allowed else None


def is_allowed(statements: list[dict], action: str, resource: str) -> bool:
    return _verdict(statements, action, resource) == "allow"


def is_allowed_any(statements: list[dict], action: str, resources: list[str]) -> bool:
    verdicts = [_verdict(statements, action, r) for r in resources]
    return "deny" not in verdicts and "allow" in verdicts


def action_in_statements(statements: list[dict], action: str) -> bool:
    granted = any(
        st["effect"] == "allow" and any(fnmatchcase(action, a) for a in st["actions"]) for st in statements
    )
    blanket_deny = any(
        st["effect"] == "deny"
        and "*" in st["resources"]
        and any(fnmatchcase(action, a) for a in st["actions"])
        for st in statements
    )
    return granted and not blanket_deny


def _clean_patterns(raw, what: str, i: int) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise PolicyError("Statement %d: faltan %s" % (i, what))
    out: list[str] = []
    for item in raw:
        item = str(item).strip()
        if not item:
            continue
        if len(item) > 200 or not re.match(r"^[\w:/*?.\-]+$", item):
            raise PolicyError("Statement %d: patrón invalido '%s'" % (i, item))
        if item not in out:
            out.append(item)
    if not out:
        raise PolicyError("Statement %d: faltan %s" % (i, what))
    return out


def clean_statements(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise PolicyError("Un rol necesita al menos un statement")
    out = []
    for i, st in enumerate(raw, 1):
        if not isinstance(st, dict):
            raise PolicyError("Statement %d invalido" % i)
        effect = st.get("effect")
        if effect not in ("allow", "deny"):
            raise PolicyError("Statement %d: effect debe ser allow o deny" % i)
        actions = _clean_patterns(st.get("actions"), "acciones", i)
        resources = _clean_patterns(st.get("resources") or ["*"], "recursos", i)
        for a in actions:
            if not any(fnmatchcase(known, a) for known in ALL_ACTIONS):
                raise PolicyError("Statement %d: la acción '%s' no existe" % (i, a))
        out.append({"effect": effect, "actions": actions, "resources": resources})
    return out


BUILTIN_ROLES = [
    {
        "id": "viewer",
        "name": "Solo lectura",
        "description": "Mira productos, proyectos y marcas, sin modificar nada.",
        "actions": ["products:list", "products:read", "projects:read", "brands:read", "unity:read"],
    },
    {
        "id": "operator",
        "name": "Operador",
        "description": "Sube productos, los reprocesa, descarga y sincroniza con Unity.",
        "actions": [
            "products:list", "products:read", "products:download", "products:assign",
            "products:create", "products:retexture", "products:retry",
            "projects:read", "brands:read", "unity:read", "unity:sync",
        ],
    },
    {
        "id": "manager",
        "name": "Gestor",
        "description": "Opera productos, los borra y administra proyectos y marcas.",
        "actions": ["products:*", "projects:*", "brands:*", "unity:*"],
    },
    {
        "id": "admin",
        "name": "Administrador del cliente",
        "description": "Todo lo que los módulos del cliente permiten.",
        "actions": ["*"],
    },
]
