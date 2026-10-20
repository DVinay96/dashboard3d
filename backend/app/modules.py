from __future__ import annotations

MODULES: dict[str, dict] = {
    "catalog": {
        "label": "Catalogo y proyectos",
        "description": "Ver los productos, descargarlos y organizarlos en proyectos.",
        "actions": {
            "products:list": "Ver la lista de productos",
            "products:read": "Abrir un producto: renders, métricas y log",
            "products:download": "Descargar los modelos GLB/FBX",
            "products:assign": "Asignar productos a proyectos",
            "products:delete": "Borrar productos",
            "projects:read": "Ver los proyectos",
            "projects:create": "Crear proyectos",
            "projects:update": "Editar proyectos",
            "projects:delete": "Borrar proyectos",
        },
    },
    "generation": {
        "label": "Generación 3D",
        "description": "Crear modelos desde fotos y procesarlos (gasta créditos del generador).",
        "actions": {
            "products:create": "Crear productos desde fotos o un GLB",
            "products:retexture": "Cambiar el material de un producto",
            "products:retry": "Reprocesar un producto",
        },
    },
    "brands": {
        "label": "Marcas y metadatos",
        "description": "Definir marcas y el esquema de metadatos de sus productos.",
        "actions": {
            "brands:read": "Ver marcas y su esquema de metadatos",
            "brands:create": "Crear marcas",
            "brands:update": "Editar marcas",
            "brands:delete": "Borrar marcas",
            "brands:update_base": "Editar los campos base de todas las marcas",
        },
    },
    "unity": {
        "label": "Sincronización con Unity",
        "description": "Publicar los productos en el Asset Manager de Unity.",
        "actions": {
            "unity:read": "Ver el estado de sincronización",
            "unity:sync": "Sincronizar productos con Unity",
        },
    },
}

DEFAULT_MODULES = ["catalog", "generation", "brands"]

ALL_ACTIONS: dict[str, str] = {a: d for m in MODULES.values() for a, d in m["actions"].items()}
ACTION_MODULE: dict[str, str] = {a: mid for mid, m in MODULES.items() for a in m["actions"]}


def module_list() -> list[dict]:
    return [
        {
            "id": mid,
            "label": m["label"],
            "description": m["description"],
            "actions": [{"name": a, "description": d} for a, d in m["actions"].items()],
        }
        for mid, m in MODULES.items()
    ]


def clean_modules(raw) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("modules debe ser una lista")
    unknown = [m for m in raw if m not in MODULES]
    if unknown:
        raise ValueError("Módulo desconocido: %s" % ", ".join(map(str, unknown)))
    return [m for m in MODULES if m in raw]
