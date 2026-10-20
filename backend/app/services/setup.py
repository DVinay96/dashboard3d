from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Client, Project, User
from . import integrations
from .platform import public_settings


def steps(db: Session) -> list[dict]:
    p = public_settings(db)
    n_clients = db.scalar(select(func.count()).select_from(Client)) or 0
    linked = db.scalar(select(func.count()).select_from(Project).where(Project.unity_project_id.is_not(None))) or 0
    users = db.scalar(select(func.count()).select_from(User).where(~User.is_super_admin)) or 0
    return [
        {
            "id": "blender",
            "title": "Blender",
            "detail": p["blender_path"] if p["blender_ok"] else "No se encontró Blender. Indica su ruta en Plataforma.",
            "done": p["blender_ok"],
            "link": "/admin/platform",
        },
        {
            "id": "meshy",
            "title": "Generador 3D (Meshy)",
            "detail": "API key cargada." if p["meshy_key_set"] else "Conecta la API key del generador para crear modelos desde fotos.",
            "done": p["meshy_key_set"],
            "link": "/admin/integrations",
        },
        {
            "id": "unity",
            "title": "Unity Asset Manager",
            "detail": "Cuenta de servicio conectada."
            if p["unity_configured"]
            else "Conecta la cuenta de servicio para publicar en Unity.",
            "done": p["unity_configured"],
            "link": "/admin/integrations",
        },
        {
            "id": "client",
            "title": "Primer cliente",
            "detail": "%d cliente(s) creados." % n_clients if n_clients else "Crea un cliente y elegí sus módulos.",
            "done": n_clients > 0,
            "link": "/admin/clients",
        },
        {
            "id": "users",
            "title": "Usuarios de los clientes",
            "detail": "%d usuario(s) de clientes." % users if users else "Crea al menos un usuario y asignale un rol.",
            "done": users > 0,
            "link": "/admin/users",
        },
        {
            "id": "unity_projects",
            "title": "Proyectos vinculados con Unity",
            "detail": "%d proyecto(s) vinculados." % linked
            if linked
            else "Vincula cada proyecto con un proyecto de Unity (Proyectos → Editar, con el cliente elegido).",
            "done": linked > 0,
            "link": "/projects",
        },
        {
            "id": "auth",
            "title": "Autenticación",
            "detail": "Sin inicio de sesión (AUTH_MODE=none): usalo solo en una maquina de confianza."
            if get_settings().auth_mode == "none"
            else "Autenticación configurada.",
            "done": get_settings().auth_mode != "none",
            "link": None,
        },
    ]
