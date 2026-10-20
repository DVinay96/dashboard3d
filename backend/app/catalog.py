from __future__ import annotations

import re
import time
import unicodedata
import uuid

FIELD_TYPES = ("text", "number", "select", "bool", "date")

DEFAULT_BASE_FIELDS = [
    {"key": "sku", "label": "SKU", "type": "text", "required": True,
     "options": [], "default": "", "help": "Código único del producto"},
    {"key": "nombre_comercial", "label": "Nombre comercial", "type": "text",
     "required": False, "options": [], "default": "", "help": ""},
    {"key": "precio", "label": "Precio", "type": "number", "required": False,
     "options": [], "default": "", "help": "En la moneda de la marca"},
]


class BrandError(ValueError):
    pass


def slug_key(text):
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(c for c in norm if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "_", ascii_only).strip("_").lower()[:40]


def clean_field(raw, used_keys):
    label = (raw.get("label") or "").strip()
    if not label:
        raise BrandError("Cada campo necesita un nombre visible.")
    key = slug_key(raw.get("key") or label)
    if not key:
        raise BrandError("El campo '%s' no produce una clave valida." % label)
    if key in used_keys:
        raise BrandError("La clave '%s' esta repetida." % key)
    used_keys.add(key)

    ftype = raw.get("type") or "text"
    if ftype not in FIELD_TYPES:
        raise BrandError("Tipo de campo desconocido: %s" % ftype)

    options = []
    if ftype == "select":
        src = raw.get("options")
        if isinstance(src, str):
            src = src.split(",")
        options = [str(o).strip() for o in (src or []) if str(o).strip()]
        if not options:
            raise BrandError("El campo '%s' es una lista y no tiene opciones." % label)

    default = raw.get("default", "")
    if ftype == "bool":
        default = bool(default)
    elif default is None:
        default = ""
    else:
        default = str(default)
    if ftype == "select" and default and default not in options:
        raise BrandError("El valor por defecto de '%s' no esta entre sus opciones." % label)

    return {
        "key": key,
        "label": label,
        "type": ftype,
        "required": bool(raw.get("required")),
        "options": options,
        "default": default,
        "help": (raw.get("help") or "").strip(),
    }


def clean_fields(raw_list, reserved=()):
    used = set(reserved)
    return [clean_field(f, used) for f in (raw_list or [])]


def clean_brand(raw, cat, brand_id=None):
    name = (raw.get("name") or "").strip()
    if not name:
        raise BrandError("La marca necesita un nombre.")
    for b in cat["brands"]:
        if b["id"] != brand_id and b["name"].strip().lower() == name.lower():
            raise BrandError("Ya existe una marca llamada '%s'." % name)

    reserved = {f["key"] for f in cat.get("base_fields", [])}
    fields = clean_fields(raw.get("fields"), reserved)

    pipeline = {}
    src = raw.get("pipeline") or {}
    for k, cast in (("target_height_m", float), ("tri_budget", int), ("target_polycount", int)):
        if src.get(k) not in (None, ""):
            try:
                pipeline[k] = cast(src[k])
            except (TypeError, ValueError):
                raise BrandError("Valor invalido para %s." % k)
    for k in ("topology", "texture_resolution", "ai_model"):
        if src.get(k):
            pipeline[k] = str(src[k])
    if src.get("texture_prompt"):
        pipeline["texture_prompt"] = str(src["texture_prompt"])[:800]

    return {
        "id": brand_id or uuid.uuid4().hex[:10],
        "name": name,
        "slug": slug_key(name),
        "notes": (raw.get("notes") or "").strip(),
        "fields": fields,
        "pipeline": pipeline,
        "created_at": raw.get("created_at") or time.time(),
    }


def get_brand(cat, brand_id):
    for b in cat["brands"]:
        if b["id"] == brand_id:
            return b
    return None


def fields_for(cat, brand_id):
    out = [dict(f, scope="base") for f in cat.get("base_fields", [])]
    brand = get_brand(cat, brand_id)
    if brand:
        out += [dict(f, scope="brand") for f in brand.get("fields", [])]
    return out


def coerce_value(field, value):
    t = field["type"]
    if t == "bool":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "si", "on", "yes")
        return bool(value)
    if t == "number":
        if value in (None, ""):
            return ""
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise BrandError("'%s' espera un número." % field["label"])
        return int(n) if n == int(n) else n
    return "" if value is None else str(value).strip()


def build_metadata(cat, brand_id, raw_values):
    values = {}
    missing = []
    for f in fields_for(cat, brand_id):
        given = (raw_values or {}).get(f["key"], None)
        if given in (None, ""):
            given = f.get("default", "")
        val = coerce_value(f, given)
        if f["type"] == "select" and val and f["options"] and val not in f["options"]:
            raise BrandError("'%s' no acepta el valor '%s'." % (f["label"], val))
        if f.get("required") and val in ("", False):
            missing.append(f["label"])
        values[f["key"]] = val
    if missing:
        raise BrandError("Faltan campos obligatorios: %s" % ", ".join(missing))
    return values


def describe(cat, brand_id, metadata):
    brand = get_brand(cat, brand_id)
    fields = [
        {
            "key": f["key"],
            "label": f["label"],
            "type": f["type"],
            "scope": f.get("scope", "base"),
            "value": (metadata or {}).get(f["key"], ""),
        }
        for f in fields_for(cat, brand_id)
    ]
    return {"brand": brand["name"] if brand else "", "brand_id": brand_id or "", "fields": fields}
