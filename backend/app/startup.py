from __future__ import annotations

import logging

from . import db as database
from . import migrate
from .config import Settings
from .services import bootstrap, integrations, jobs
from .services.legacy_import import import_legacy

logger = logging.getLogger("pipeline")


def startup(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.products_dir.mkdir(parents=True, exist_ok=True)
    database.configure(settings.database_url)
    migrate.upgrade(settings.database_url)
    with database.session_scope() as db:
        bootstrap.seed_roles(db)
        bootstrap.ensure_local_admin(db)
        integrations.ensure_singletons(db)
        import_legacy(db)
        n = bootstrap.fail_interrupted(db)
        if n:
            logger.warning("%d producto(s) quedaron a medias en la corrida anterior y se marcaron FAILED", n)
    jobs.configure(settings.job_workers)
    if settings.auth_mode == "none":
        logger.warning("AUTH_MODE=none: sin autenticación. Cualquiera que llegue al servidor es super admin.")
