from __future__ import annotations

import json
import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import catalog as cat_mod
from ..db import get_db
from ..deps import authorize, forbid, get_principal, need_client
from ..identity import Principal
from ..models import Product, Project, new_id, now, product_projects
from ..schemas import AssignIn, ProductOut, ProductsOut, ProjectRef, RetextureIn, UserRef
from .unity import sync_out
from ..services import files as fs
from ..services import jobs
from ..services.catalogs import catalog_for
from ..services.pipeline import ACTIVE, run_pipeline
from ..services.unity_sync import auto_sync

router = APIRouter(prefix="/api/products", tags=["productos"])

MAX_UPLOAD = 300 * 1024 * 1024
PHOTO_EXT = (".jpg", ".jpeg", ".png")
MODEL_EXT = (".glb", ".gltf")


def product_res(pr: Product) -> list[str]:
    return ["project/%s/product/%s" % (x.id, pr.id) for x in pr.projects] or ["project/none/product/%s" % pr.id]


def product_out(pr: Product) -> ProductOut:
    return ProductOut(
        id=pr.id, client_id=pr.client_id, name=pr.name, slug=pr.slug, status=pr.status, stage=pr.stage,
        progress=pr.progress, source=pr.source, brand_id=pr.brand_id, brand_name=pr.brand.name if pr.brand else "",
        parent_id=pr.parent_id, retexture_prompt=pr.retexture_prompt, credits=pr.credits, error=pr.error,
        options=pr.options or {}, metadata=pr.meta or {}, photos=pr.photos or [], raw_files=pr.raw_files or {},
        textures=pr.textures or {}, metrics=pr.metrics, original_filename=pr.original_filename, thumbnail_url=pr.thumbnail_url,
        created_by=UserRef.model_validate(pr.created_by) if pr.created_by else None,
        projects=[ProjectRef.model_validate(x) for x in pr.projects],
        unity=[sync_out(r, pr.name) for r in pr.unity_syncs],
        created_at=pr.created_at, updated_at=pr.updated_at,
    )


def _get(db: Session, p: Principal, pid: str) -> Product:
    pr = db.get(Product, pid)
    if pr is None or (p.client is not None and pr.client_id != p.client.id):
        raise HTTPException(404, "El producto no existe.")
    return pr


def _json(text: str, what: str, kind: type):
    try:
        value = json.loads(text or ("[]" if kind is list else "{}"))
    except ValueError:
        raise HTTPException(400, "%s: JSON invalido." % what)
    if not isinstance(value, kind):
        raise HTTPException(400, "%s: se esperaba %s." % (what, "una lista" if kind is list else "un objeto"))
    return value


def _client_projects(db: Session, p: Principal, ids: list[str]) -> list[Project]:
    out = []
    for pid in dict.fromkeys(ids):
        pr = db.get(Project, pid)
        if pr is None or pr.client_id != p.client.id:
            raise HTTPException(400, "El proyecto '%s' no existe." % pid)
        if pr.archived:
            raise HTTPException(400, "El proyecto '%s' esta archivado." % pr.name)
        out.append(pr)
    return out


def _read_limited(upload: UploadFile, budget: int) -> bytes:
    data = bytearray()
    while chunk := upload.file.read(1024 * 1024):
        data += chunk
        if len(data) > budget:
            raise HTTPException(413, "Los archivos superan el maximo de %d MB." % (MAX_UPLOAD // 1024 // 1024))
    return bytes(data)


def _normalize_options(options: dict, brand_pipeline: dict) -> dict:
    for k, v in (brand_pipeline or {}).items():
        options.setdefault(k, v)
    try:
        return {
            "ai_model": options.get("ai_model", "meshy-7"),
            "ultra_mode": bool(options.get("ultra_mode", True)),
            "should_texture": bool(options.get("should_texture", True)),
            "enable_pbr": bool(options.get("enable_pbr", True)),
            "texture_resolution": options.get("texture_resolution", "2k"),
            "texture_prompt": options.get("texture_prompt", ""),
            "should_remesh": bool(options.get("should_remesh", True)),
            "topology": options.get("topology", "quad"),
            "target_polycount": int(options.get("target_polycount", 15000)),
            "auto_size": bool(options.get("auto_size", True)),
            "remove_lighting": bool(options.get("remove_lighting", True)),
            "image_enhancement": bool(options.get("image_enhancement", True)),
            "target_height_m": float(options.get("target_height_m") or 0),
            "tri_budget": int(options.get("tri_budget", 15000)),
            "lightmap_uv": bool(options.get("lightmap_uv", True)),
        }
    except (TypeError, ValueError):
        raise HTTPException(400, "Alguna opción numérica del pipeline es invalida.")


@router.get("", response_model=ProductsOut)
def list_products(project_id: str | None = None, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    if "products:list" not in p.possible_actions():
        forbid("products:list")
    q = select(Product).where(Product.client_id == p.client.id).order_by(Product.created_at.desc())
    if project_id:
        q = q.join(product_projects, product_projects.c.product_id == Product.id).where(
            product_projects.c.project_id == project_id)
    rows = [pr for pr in db.scalars(q) if p.can("products:list", product_res(pr))]
    return {"products": [product_out(pr) for pr in rows]}


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    name: Annotated[str, Form()] = "",
    brand_id: Annotated[str, Form()] = "",
    metadata: Annotated[str, Form()] = "{}",
    options: Annotated[str, Form()] = "{}",
    project_ids: Annotated[str, Form()] = "[]",
    files: Annotated[list[UploadFile], File()] = [],
    p: Principal = Depends(need_client),
    db: Session = Depends(get_db),
):
    ids = _json(project_ids, "project_ids", list)
    if not ids:
        active = db.scalars(select(Project.id).where(Project.client_id == p.client.id, ~Project.archived)).all()
        if len(active) != 1:
            raise HTTPException(400, "Elegí al menos un proyecto para el producto.")
        ids = list(active)
    projects = _client_projects(db, p, ids)
    for pr in projects:
        authorize(p, "products:create", "project/%s/product/new" % pr.id)

    cat = catalog_for(db, p.client)
    brand_id = brand_id.strip()
    brand = cat_mod.get_brand(cat, brand_id) if brand_id else None
    if brand_id and brand is None:
        raise HTTPException(400, "La marca seleccionada ya no existe.")
    try:
        metadata_vals = cat_mod.build_metadata(cat, brand_id, _json(metadata, "metadata", dict))
    except cat_mod.BrandError as e:
        raise HTTPException(400, str(e))
    opts = _normalize_options(_json(options, "options", dict), (brand or {}).get("pipeline") or {})

    uploads = [f for f in files if f.filename]
    photos = [f for f in uploads if f.filename.lower().endswith(PHOTO_EXT)]
    models = [f for f in uploads if f.filename.lower().endswith(MODEL_EXT)]
    if not photos and not models:
        raise HTTPException(400, "Subí al menos una foto (.jpg/.png) o un modelo .glb.")

    pid = new_id()
    d = fs.product_dir(pid)
    total = 0
    try:
        (d / "input").mkdir(parents=True, exist_ok=True)
        pr = Product(
            id=pid, client_id=p.client.id, name=name.strip() or "Producto sin nombre", status="QUEUED",
            stage="En cola", options=opts, meta=metadata_vals, brand_id=brand_id or None,
            created_by_id=p.user.id, photos=[], raw_files={},
        )
        pr.slug = fs.slugify(pr.name)
        if models:
            pr.source, pr.original_filename = "local", models[0].filename
            data = _read_limited(models[0], MAX_UPLOAD - total)
            total += len(data)
            (d / "raw").mkdir(parents=True, exist_ok=True)
            (d / "raw" / "model.glb").write_bytes(data)
            pr.raw_files = {"glb": "raw/model.glb"}
        else:
            pr.source = "meshy"
            for i, f in enumerate(photos[:4]):
                data = _read_limited(f, MAX_UPLOAD - total)
                total += len(data)
                ext = ("." + f.filename.rsplit(".", 1)[-1].lower()) if "." in f.filename else ".jpg"
                fn = "photo_%d%s" % (i, ext)
                (d / "input" / fn).write_bytes(data)
                pr.photos = [*pr.photos, fn]
        pr.projects = projects
        db.add(pr)
        db.commit()
    except Exception:
        db.rollback()
        fs.remove_product_files(pid)
        raise
    fs.log(pid, "creado '%s' (%s, %d archivo/s)" % (pr.name, pr.source, len(uploads)))
    jobs.submit(run_pipeline, pid)
    return product_out(pr)


@router.get("/{pid}", response_model=ProductOut)
def get_product(pid: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:read", product_res(pr))
    return product_out(pr)


@router.get("/{pid}/log")
def get_log(pid: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:read", product_res(pr))
    return Response(fs.read_log(pid), media_type="text/plain; charset=utf-8")


@router.get("/{pid}/files/{rel:path}")
def get_file(pid: str, rel: str, download: int = 0, p: Principal = Depends(get_principal),
             db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:download" if download else "products:read", product_res(pr))
    f = fs.safe_file(pid, rel)
    if f is None:
        raise HTTPException(404, "Archivo no encontrado.")
    media = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    return FileResponse(f, media_type=media, filename=f.name if download else None)


@router.post("/{pid}/retexture", response_model=ProductOut, status_code=201)
def retexture(pid: str, body: RetextureIn, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    parent = _get(db, p, pid)
    authorize(p, "products:retexture", product_res(parent))
    if not (parent.raw_files or {}).get("glb"):
        raise HTTPException(400, "El producto original todavía no tiene modelo.")
    prompt = body.prompt.strip()
    pr = Product(
        client_id=p.client.id, name="%s · %s" % (parent.name, prompt[:40]),
        slug=fs.slugify(parent.slug + "_" + prompt[:30]), status="QUEUED", stage="En cola", source="retexture",
        options=dict(parent.options or {}), meta=dict(parent.meta or {}), brand_id=parent.brand_id,
        parent_id=parent.id, retexture_prompt=prompt, created_by_id=p.user.id, photos=[], raw_files={},
    )
    pr.projects = list(parent.projects)
    db.add(pr)
    db.commit()
    fs.log(pr.id, "re-texturizado de '%s' con: %s" % (parent.name, prompt))
    jobs.submit(run_pipeline, pr.id)
    return product_out(pr)


@router.post("/{pid}/retry", status_code=202)
def retry(pid: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:retry", product_res(pr))
    if pr.status in ACTIVE:
        raise HTTPException(409, "El producto ya se esta procesando.")
    pr.status, pr.error, pr.stage, pr.updated_at = "QUEUED", None, "En cola", now()
    db.commit()
    jobs.submit(run_pipeline, pr.id)
    return {"ok": True}


@router.put("/{pid}/projects", response_model=ProductOut)
def assign_projects(pid: str, body: AssignIn, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:assign", product_res(pr))
    projects = _client_projects(db, p, body.project_ids)
    for x in projects:
        authorize(p, "products:assign", "project/%s/product/%s" % (x.id, pr.id))
    pr.projects = projects
    pr.updated_at = now()
    db.commit()
    if pr.status == "DONE":
        jobs.submit(auto_sync, pr.id)
        db.expire_all()
    return product_out(pr)


@router.delete("/{pid}", status_code=204)
def delete(pid: str, p: Principal = Depends(need_client), db: Session = Depends(get_db)):
    pr = _get(db, p, pid)
    authorize(p, "products:delete", product_res(pr))
    if pr.status in ACTIVE:
        raise HTTPException(409, "El producto se esta procesando: espera a que termine o falle.")
    db.delete(pr)
    db.commit()
    fs.remove_product_files(pid)
