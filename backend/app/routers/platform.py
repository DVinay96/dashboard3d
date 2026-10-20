from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import need_super
from ..schemas import PlatformSettings, PlatformSettingsIn, SetupOut, SetupStep
from ..services import platform as svc
from ..services import setup as setup_svc

router = APIRouter(prefix="/api/platform", tags=["plataforma"], dependencies=[Depends(need_super)])


@router.get("/settings", response_model=PlatformSettings)
def get_settings_(db: Session = Depends(get_db)):
    return svc.public_settings(db)


@router.put("/settings", response_model=PlatformSettings)
def put_settings(body: PlatformSettingsIn, db: Session = Depends(get_db)):
    for key in svc.EDITABLE:
        value = getattr(body, key)
        if value is not None:
            svc.set_setting(db, key, value.strip())
    db.commit()
    return svc.public_settings(db)


@router.get("/setup", response_model=SetupOut)
def setup(db: Session = Depends(get_db)):
    steps = setup_svc.steps(db)
    return SetupOut(steps=[SetupStep(**s) for s in steps], ready=all(s["done"] for s in steps if s["id"] != "auth"))
