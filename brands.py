#!/usr/bin/env python3
"""
Catalogo de marcas y esquema de metadatos de producto.

Modelo (data/brands.json):

  base_fields   campos comunes a TODAS las marcas (SKU, nombre, precio...)
  brands[]      cada marca con:
                  fields[]    campos propios, se suman a los base
                  pipeline    overrides del pipeline (altura, budget, prompt...)

Un campo es: {key, label, type, required, options, default, help}
type: text | number | select | bool | date
"""

import json
import os
import re
import unicodedata
import threading
import time
import uuid

FIELD_TYPES = ("text", "number", "select", "bool", "date")

_lock = threading.RLock()


# ---------------------------------------------------------------- semillas


def default_catalog():
    """Catalogo inicial: los campos base que aplican a cualquier mueble."""
    return {
        "base_fields": [
            {"key": "sku", "label": "SKU", "type": "text", "required": True,
             "options": [], "default": "", "help": "Codigo unico del producto"},
            {"key": "nombre_comercial", "label": "Nombre comercial", "type": "text",
             "required": False, "options": [], "default": "", "help": ""},
            {"key": "precio", "label": "Precio", "type": "number", "required": False,
             "options": [], "default": "", "help": "En la moneda de la marca"},
        ],
        "brands": [],
        "updated_at": time.time(),
    }


# ------------------------------------------------------------ persistencia


def catalog_path(data_dir):
    return os.path.join(data_dir, "brands.json")


def load_catalog(data_dir):
    path = catalog_path(data_dir)
    if not os.path.exists(path):
        return save_catalog(data_dir, default_catalog())
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cat = json.load(fh)
    except Exception:
        return default_catalog()
    cat.setdefault("base_fields", [])
    cat.setdefault("brands", [])
    return cat


def save_catalog(data_dir, cat):
    with _lock:
        os.makedirs(data_dir, exist_ok=True)
        cat["updated_at"] = time.time()
        path = catalog_path(data_dir)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cat, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    return cat


# -------------------------------------------------------------- validacion


class BrandError(Exception):
    pass


def slug_key(text):
    """'Colección' -> 'coleccion': los acentos se transliteran, no se pierden."""
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(c for c in norm if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_only).strip("_").lower()
    return s[:40]


def clean_field(raw, used_keys):
    """Normaliza un campo y verifica que la clave sea unica y utilizable."""
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

    # las claves base estan reservadas: un campo propio no puede pisarlas
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


# ------------------------------------------------------------------ acceso


def get_brand(cat, brand_id):
    for b in cat["brands"]:
        if b["id"] == brand_id:
            return b
    return None


def fields_for(cat, brand_id):
    """Campos base + campos propios de la marca, en ese orden."""
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
            raise BrandError("'%s' espera un numero." % field["label"])
        return int(n) if n == int(n) else n
    return "" if value is None else str(value).strip()


def build_metadata(cat, brand_id, raw_values):
    """Aplica defaults, convierte tipos y verifica los campos obligatorios."""
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
    """Metadatos legibles para el sidecar JSON y para la interfaz."""
    brand = get_brand(cat, brand_id)
    fields = []
    for f in fields_for(cat, brand_id):
        fields.append({
            "key": f["key"],
            "label": f["label"],
            "type": f["type"],
            "scope": f.get("scope", "base"),
            "value": (metadata or {}).get(f["key"], ""),
        })
    return {
        "brand": brand["name"] if brand else "",
        "brand_id": brand_id or "",
        "fields": fields,
    }
