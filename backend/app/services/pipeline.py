from __future__ import annotations

import json
import shutil
import subprocess
import time
import traceback
from pathlib import Path

from .. import catalog as catalog_mod
from ..config import get_settings
from ..db import session_scope
from ..models import Client, Product, now
from . import events, integrations, meshy
from .catalogs import catalog_for
from .unity_sync import auto_sync
from .files import append_log, log, product_dir
from .platform import get_setting, resolve_blender

ACTIVE = ("QUEUED", "GENERATING", "DOWNLOADING", "CONDITIONING")
QA_SCRIPT = Path(__file__).resolve().parents[1] / "qa_blender.py"


def update_product(pid: str, **patch) -> None:
    with session_scope() as db:
        p = db.get(Product, pid)
        if p is None:
            return
        for k, v in patch.items():
            setattr(p, k, v)
        p.updated_at = now()


def snapshot(pid: str) -> dict | None:
    with session_scope() as db:
        p = db.get(Product, pid)
        if p is None:
            return None
        return {
            "id": p.id, "client_id": p.client_id, "name": p.name, "slug": p.slug, "source": p.source,
            "options": dict(p.options or {}), "photos": list(p.photos or []),
            "raw_files": dict(p.raw_files or {}), "task_id": p.task_id, "parent_id": p.parent_id,
            "retexture_prompt": p.retexture_prompt, "brand_id": p.brand_id or "", "meta": dict(p.meta or {}),
        }


def run_pipeline(pid: str) -> None:
    try:
        _run(pid)
    except meshy.MeshyError as e:
        log(pid, "ERROR del generador 3D: %s" % e)
        update_product(pid, status="FAILED", error=str(e))
        events.emit("product.failed", pid)
    except Exception as e:
        log(pid, "ERROR: %s\n%s" % (e, traceback.format_exc()))
        update_product(pid, status="FAILED", error=str(e))
        events.emit("product.failed", pid)


def _generate(pid: str, snap: dict, d: Path) -> Path:
    settings = get_settings()
    raw_dir = d / "raw"
    api_key = integrations.meshy_key()
    if not api_key:
        raise meshy.MeshyError(
            "Falta la API key del generador 3D. Conectala en Integraciones.")

    if snap["source"] == "retexture":
        parent = snapshot(snap["parent_id"]) if snap["parent_id"] else None
        if parent is None:
            raise meshy.MeshyError("El producto original ya no existe.")
        glb = parent["raw_files"].get("glb")
        use_task = parent["task_id"] if parent["source"] in ("meshy", "retexture") else None
        endpoint, payload = meshy.build_retexture_payload(
            snap["options"], snap["retexture_prompt"] or "", use_task, product_dir(parent["id"]) / glb if glb else None)
        log(pid, "POST %s (prompt: %s, base: %s)" % (
            endpoint, payload["text_style_prompt"],
            "task " + payload["input_task_id"] if "input_task_id" in payload else "GLB subido"))
    else:
        images = [str(d / "input" / f) for f in snap["photos"]]
        endpoint, payload = meshy.build_payload(snap["options"], images)
        log(pid, "POST %s (%d foto/s, %s)" % (endpoint, len(images), payload["ai_model"]))
    update_product(pid, status="GENERATING", progress=0, stage="Enviando al generador 3D")

    res = meshy.request("POST", endpoint, api_key, payload)
    task_id = res.get("result")
    if not task_id:
        raise meshy.MeshyError("El generador 3D no devolvió task id: %s" % res)
    log(pid, "task_id=%s" % task_id)
    update_product(pid, task_id=task_id, endpoint=endpoint, stage="Generando geometría")

    started = time.time()
    task: dict = {}
    while True:
        if time.time() - started > settings.poll_timeout:
            raise meshy.MeshyError("Timeout de %d min esperando la generación." % (settings.poll_timeout // 60))
        time.sleep(settings.poll_seconds)
        task = meshy.request("GET", "%s/%s" % (endpoint, task_id), api_key)
        st = task.get("status")
        pr = int(task.get("progress") or 0)
        update_product(pid, progress=pr, stage="Generando: %s %d%%" % (st, pr))
        if st == "SUCCEEDED":
            break
        if st in ("FAILED", "CANCELED"):
            err = (task.get("task_error") or {}).get("message") or st
            raise meshy.MeshyError("La tarea terminó en %s: %s" % (st, err))

    credits = task.get("consumed_credits")
    log(pid, "generación COMPLETA (créditos: %s)" % credits)
    update_product(pid, status="DOWNLOADING", stage="Descargando assets", credits=credits)

    urls = task.get("model_urls") or {}
    got: dict[str, str] = {}
    for fmt in ("glb", "fbx"):
        if urls.get(fmt):
            dest = raw_dir / ("model." + fmt)
            log(pid, "descargando %s" % fmt)
            meshy.download(urls[fmt], dest)
            got[fmt] = str(dest.relative_to(d))
    if not got.get("glb"):
        raise meshy.MeshyError("El generador 3D no devolvió GLB.")

    tex: dict[str, str] = {}
    for i, t in enumerate(task.get("texture_urls") or []):
        for key, url in (t or {}).items():
            if not url or not isinstance(url, str) or not url.startswith("http"):
                continue
            ext = Path(url.split("?")[0]).suffix or ".png"
            dest = raw_dir / "textures" / ("%d_%s%s" % (i, key, ext))
            try:
                meshy.download(url, dest)
                tex["%d_%s" % (i, key)] = str(dest.relative_to(d))
            except Exception as e:
                log(pid, "no se pudo bajar textura %s: %s" % (key, e))
    if task.get("thumbnail_url"):
        try:
            meshy.download(task["thumbnail_url"], raw_dir / "thumbnail.png")
        except Exception:
            pass

    update_product(pid, raw_files=got, textures=tex, thumbnail_url=task.get("thumbnail_url"))
    return d / got["glb"]


def _run(pid: str) -> None:
    snap = snapshot(pid)
    if snap is None:
        return
    d = product_dir(pid)

    existing = snap["raw_files"].get("glb")
    already = bool(existing) and (d / existing).exists()
    uses_meshy = snap["source"] in ("meshy", "retexture")
    if uses_meshy and already:
        log(pid, "el modelo ya esta descargado: se reutiliza, sin llamar a la API")
    src_model = _generate(pid, snap, d) if (uses_meshy and not already) else d / existing

    with session_scope() as db:
        blender = resolve_blender(db)
        unity_dir = str(get_setting(db, "unity_export_dir"))
    if not blender or not Path(blender).exists():
        raise RuntimeError(
            "No se encontró Blender. Carga la ruta en Plataforma "
            "(ej: /Applications/Blender.app/Contents/MacOS/Blender).")

    update_product(pid, status="CONDITIONING", stage="Blender: acondicionando + QA", progress=0)
    log(pid, "Blender: %s" % blender)
    o = snap["options"]
    args = json.dumps({
        "src": str(src_model),
        "out_dir": str(d / "out"),
        "qa_dir": str(d / "qa"),
        "slug": snap["slug"],
        "target_height_m": o.get("target_height_m") or 0,
        "tri_budget": int(o.get("tri_budget") or 15000),
        "lightmap_uv": bool(o.get("lightmap_uv", True)),
        "export_fbx": True,
    })
    cmd = [blender, "-b", "--factory-startup", "-noaudio", "--python", str(QA_SCRIPT), "--", args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 20)
    append_log(pid, "\n----- blender -----\n" + (proc.stdout or "")[-4000:] + (proc.stderr or "")[-2000:] + "\n")

    metrics_path = d / "qa" / "metrics.json"
    if proc.returncode != 0 or not metrics_path.exists():
        raise RuntimeError("Blender falló (code %s). Ver el log del producto." % proc.returncode)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    checks = metrics.get("checks", [])
    failed = [c for c in checks if c["level"] == "fail"]
    status = "QA_FAILED" if failed else "DONE"
    update_product(pid, status=status, progress=100,
                   stage="%d/%d checks OK" % (len(checks) - len(failed), len(checks)), metrics=metrics)
    log(pid, "%s -- %d checks, %d fallos" % (status, len(checks), len(failed)))

    try:
        with session_scope() as db:
            client = db.get(Client, snap["client_id"])
            cat = catalog_for(db, client)
        sidecar = catalog_mod.describe(cat, snap["brand_id"], snap["meta"])
        sidecar.update({
            "producto": snap["name"], "slug": snap["slug"],
            "generado": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modelos": metrics.get("exported") or {},
        })
        (d / "out" / (snap["slug"] + ".metadata.json")).write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(pid, "no se pudo escribir el sidecar de metadatos: %s" % e)

    if status == "DONE" and unity_dir and Path(unity_dir).is_dir():
        for f in (d / "out").iterdir():
            try:
                shutil.copy2(f, Path(unity_dir) / f.name)
            except Exception as e:
                log(pid, "copia a Unity falló: %s" % e)
        log(pid, "copiado a %s" % unity_dir)

    events.emit("product.done" if status == "DONE" else "product.qa_failed", pid)
    if status == "DONE":
        try:
            auto_sync(pid)
        except Exception as e:
            log(pid, "Unity: no se pudo iniciar la sincronización automatica: %s" % e)
