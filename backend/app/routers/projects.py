from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import authorize, forbid, need_client
from ..identity import Principal
from ..models import Project, product_projects
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["proyectos"])


def project_res(project_id: str) -> str:
    return "project/%s" % project_id


def _counts(db: Session, ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(product_projects.c.project_id, func.count())
        .where(product_projects.c.project_id.in_(ids))
        .group_by(product_projects.c.project_id)
    ).all()
    return dict(rows)


def _out(pr: Project, n: int) -> ProjectOut:
    return ProjectOut(
        id=pr.id, client_id=pr.client_id, name=pr.name, description=pr.description,
        unity_project_id=pr.unity_project_id, archived=pr.archived, created_at=pr.created_at, product_count=n,
    )


def _get(db: Session, p: Principal, project_id: str) -> Project:
    pr = db.get(Project, project_id)
    if pr is None or pr.client_id != p.client.id:
        raise HTTPException(404, "El proyecto no existe.")
    return pr


def _name_taken(db: Session, p: Principal, name: str, exclude: str = "") -> bool:
    return bool(db.scalar(select(Project.id).where(
        Project.client_id == p.client.id, func.lower(Project.name) == name.lower(), Project.id != exclude)))


@router.get("", response_model=list[ProjectOut])
def list_projects(p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    if "projects:read" not in p.possible_actions():
        forbid("projects:read")
    rows = db.scalars(
        select(Project).where(Project.client_id == p.client.id).order_by(Project.archived, Project.name)
    ).all()
    rows = [r for r in rows if p.can("projects:read", project_res(r.id))]
    counts = _counts(db, [r.id for r in rows])
    return [_out(r, counts.get(r.id, 0)) for r in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create(body: ProjectCreate, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    authorize(p, "projects:create", project_res("new"))
    name = body.name.strip()
    if _name_taken(db, p, name):
        raise HTTPException(409, "Ya existe un proyecto llamado '%s'." % name)
    pr = Project(client_id=p.client.id, name=name, description=body.description.strip())
    db.add(pr)
    db.commit()
    return _out(pr, 0)


@router.patch("/{project_id}", response_model=ProjectOut)
def update(project_id: str, body: ProjectUpdate, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = _get(db, p, project_id)
    authorize(p, "projects:update", project_res(pr.id))
    fields = body.model_fields_set
    if "name" in fields and body.name is not None:
        name = body.name.strip()
        if _name_taken(db, p, name, exclude=pr.id):
            raise HTTPException(409, "Ya existe un proyecto llamado '%s'." % name)
        pr.name = name
    if "description" in fields and body.description is not None:
        pr.description = body.description.strip()
    if "archived" in fields and body.archived is not None:
        pr.archived = body.archived
    if "unity_project_id" in fields:
        if not p.is_super_admin:
            raise HTTPException(403, "Solo el super admin puede vincular el proyecto con Unity.")
        pr.unity_project_id = (body.unity_project_id or "").strip() or None
    db.commit()
    return _out(pr, _counts(db, [pr.id]).get(pr.id, 0))


@router.delete("/{project_id}", status_code=204)
def delete(project_id: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = _get(db, p, project_id)
    authorize(p, "projects:delete", project_res(pr.id))
    n = _counts(db, [pr.id]).get(pr.id, 0)
    if n:
        raise HTTPException(409, "No se puede borrar: tiene %d producto/s. Archivalo en su lugar." % n)
    db.delete(pr)
    db.commit()
