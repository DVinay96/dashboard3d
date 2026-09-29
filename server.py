#!/usr/bin/env python3
"""
Pipeline 3D - de fotos de producto a modelo listo para Unity.

Servidor HTTP sin dependencias externas (solo stdlib). Escucha SOLO en 127.0.0.1.

Etapas del pipeline por producto:
  1. UPLOAD       fotos guardadas en disco
  2. GENERATING   generador 3D (image-to-3d o multi-image-to-3d) + polling
  3. DOWNLOADING  descarga de GLB/FBX/texturas
  4. CONDITIONING Blender headless: escala real, pivote, UV lightmap, budget
  5. QA           metricas + renders + semaforo
  6. DONE / FAILED

Tambien acepta modelos GLB/FBX locales para correr solo 4-5-6 (sin gastar creditos).
"""

import base64
import json
import mimetypes
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import brands as brands_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PRODUCTS = os.path.join(DATA, "products")
STATIC = os.path.join(ROOT, "static")
CONFIG_PATH = os.path.join(DATA, "config.json")

MESHY_BASE = os.environ.get("MESHY_BASE", "https://api.meshy.ai/openapi/v1")
POLL_SECONDS = 5
POLL_TIMEOUT = 60 * 25

_lock = threading.RLock()
_log_lock = threading.RLock()

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

# La API key NO vive aca: se lee solo de la variable de entorno MESHY_API_KEY,
# cargada desde .env. Asi no queda en un archivo que la UI pueda escribir ni se
# filtra si alguien comparte la carpeta data/.
DEFAULT_CONFIG = {
    "blender_path": "",
    "unity_export_dir": "",
}

API_KEY_ENV_VARS = ("MESHY_API_KEY",)


def load_env_file():
    """Lee .env si existe (KEY=VALUE por linea)."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception:
            pass
    cfg["api_key"] = ""
    cfg["api_key_var"] = ""
    for var in API_KEY_ENV_VARS:
        if os.environ.get(var):
            cfg["api_key"] = os.environ[var].strip()
            cfg["api_key_var"] = var
            break
    if os.environ.get("BLENDER_PATH"):
        cfg["blender_path"] = os.environ["BLENDER_PATH"]
    if not cfg["blender_path"]:
        cfg["blender_path"] = find_blender()
    return cfg


def save_config(patch):
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception:
            pass
    cfg.update({k: v for k, v in patch.items() if k in DEFAULT_CONFIG})
    os.makedirs(DATA, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass
    return cfg


def find_blender():
    for cand in (
        shutil.which("blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/opt/homebrew/bin/blender",
        "/usr/local/bin/blender",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    ):
        if cand and os.path.exists(cand):
            return cand
    return ""


# ----------------------------------------------------------------------------
# Persistencia por producto (un meta.json por carpeta, sin base de datos)
# ----------------------------------------------------------------------------


def product_dir(pid):
    return os.path.join(PRODUCTS, pid)


def meta_path(pid):
    return os.path.join(product_dir(pid), "meta.json")


def read_meta(pid):
    try:
        with open(meta_path(pid), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def write_meta(meta):
    with _lock:
        d = product_dir(meta["id"])
        os.makedirs(d, exist_ok=True)
        tmp = meta_path(meta["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
        os.replace(tmp, meta_path(meta["id"]))


def update_meta(pid, **patch):
    with _lock:
        meta = read_meta(pid)
        if meta is None:
            return None
        meta.update(patch)
        meta["updated_at"] = time.time()
        write_meta(meta)
        return meta


def list_products():
    if not os.path.isdir(PRODUCTS):
        return []
    out = []
    for pid in os.listdir(PRODUCTS):
        m = read_meta(pid)
        if m:
            out.append(m)
    out.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return out


def log(pid, msg):
    line = time.strftime("%H:%M:%S") + "  " + str(msg)
    with _log_lock:
        os.makedirs(product_dir(pid), exist_ok=True)
        with open(os.path.join(product_dir(pid), "log.txt"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    print("[" + pid[:8] + "] " + str(msg), flush=True)


def slugify(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "producto")).strip("_").lower()
    return s[:60] or "producto"


# ----------------------------------------------------------------------------
# Cliente del generador 3D
# ----------------------------------------------------------------------------


class MeshyError(Exception):
    pass


def meshy_request(method, path, api_key, payload=None, timeout=90):
    url = MESHY_BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + api_key)
    if data:
        req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:600]
        except Exception:
            pass
        hints = {
            401: "API key invalida o ausente.",
            402: "Creditos insuficientes en la cuenta del generador 3D.",
            429: "Rate limit del generador 3D alcanzado, reintenta en unos minutos.",
        }
        raise MeshyError(
            "HTTP %s %s -- %s %s" % (e.code, e.reason, hints.get(e.code, ""), detail)
        )
    except urllib.error.URLError as e:
        raise MeshyError("Error de red hacia Meshy: %s" % e.reason)


def data_uri(path):
    mime, _ = mimetypes.guess_type(path)
    if mime not in ("image/jpeg", "image/png"):
        mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    with open(path, "rb") as fh:
        return "data:%s;base64,%s" % (mime, base64.b64encode(fh.read()).decode("ascii"))


def build_payload(meta, images):
    """Construye el body segun si es 1 foto (image-to-3d) o varias (multi-image-to-3d)."""
    o = meta["options"]
    multi = len(images) > 1
    payload = {
        "ai_model": o["ai_model"],
        "should_texture": bool(o["should_texture"]),
        "enable_pbr": bool(o["enable_pbr"]),
        "texture_resolution": o["texture_resolution"],
        "should_remesh": bool(o["should_remesh"]),
        "topology": o["topology"],
        "target_polycount": int(o["target_polycount"]),
        "target_formats": ["glb", "fbx"],
    }
    if o.get("ultra_mode") and o["ai_model"] in ("meshy-7", "latest"):
        payload["ultra_mode"] = True
    if o.get("texture_prompt"):
        payload["texture_prompt"] = o["texture_prompt"][:800]

    if multi:
        payload["image_urls"] = [data_uri(p) for p in images[:4]]
        endpoint = "/multi-image-to-3d"
    else:
        payload["image_url"] = data_uri(images[0])
        # Estos dos parametros SOLO existen en image-to-3d:
        # resuelven escala real y pivote en el origen sin post-proceso.
        if o.get("auto_size", True):
            payload["auto_size"] = True
            payload["origin_at"] = "bottom"
        payload["remove_lighting"] = bool(o.get("remove_lighting", True))
        payload["image_enhancement"] = bool(o.get("image_enhancement", True))
        endpoint = "/image-to-3d"
    return endpoint, payload


def build_retexture_payload(meta):
    """Re-pinta la geometria de un producto padre a partir de un texto.

    En /image-to-3d la textura se proyecta desde la foto y el texture_prompt
    solo matiza: una silla blanca en la foto sale blanca aunque pidas negro.
    Retexture usa el texto como instruccion principal y no toca la geometria.
    """
    o = meta["options"]
    parent = read_meta(meta["parent_id"]) or {}
    payload = {
        "text_style_prompt": meta["retexture_prompt"][:800],
        "ai_model": o.get("ai_model", "meshy-7"),
        "enable_pbr": bool(o.get("enable_pbr", True)),
        "texture_resolution": o.get("texture_resolution", "2k"),
        "remove_lighting": True,
        "target_formats": ["glb", "fbx"],
    }
    # preferir el task id del padre (sin subir nada); si no esta, el GLB crudo
    if parent.get("task_id") and parent.get("source") in ("meshy", "retexture"):
        payload["input_task_id"] = parent["task_id"]
    else:
        glb = (parent.get("raw_files") or {}).get("glb")
        if not glb:
            raise MeshyError("El producto original no tiene modelo para re-texturizar.")
        with open(os.path.join(product_dir(parent["id"]), glb), "rb") as fh:
            payload["model_url"] = "data:model/gltf-binary;base64," + base64.b64encode(fh.read()).decode("ascii")
    return "/retexture", payload


def download(url, dest, timeout=300):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "pipeline3d/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest


# ----------------------------------------------------------------------------
# Worker
# ----------------------------------------------------------------------------


def run_pipeline(pid):
    try:
        _run_pipeline(pid)
    except MeshyError as e:
        log(pid, "ERROR del generador 3D: %s" % e)
        update_meta(pid, status="FAILED", error=str(e))
    except Exception as e:
        log(pid, "ERROR: %s\n%s" % (e, traceback.format_exc()))
        update_meta(pid, status="FAILED", error=str(e))


def _run_pipeline(pid):
    meta = read_meta(pid)
    if meta is None:
        return
    cfg = get_config()
    d = product_dir(pid)
    raw_dir = os.path.join(d, "raw")

    # ---- Etapa 2-3: generacion en el generador 3D ----
    # Se saltea si el modelo ya esta en disco: reprocesar NUNCA vuelve a gastar
    # creditos. Se decide por el archivo, no por un flag en meta.json.
    existing = (meta.get("raw_files") or {}).get("glb")
    already_downloaded = bool(existing) and os.path.exists(os.path.join(d, existing))
    uses_meshy = meta.get("source") in ("meshy", "retexture")
    if uses_meshy and already_downloaded:
        log(pid, "el modelo ya esta descargado: se reutiliza, sin llamar a la API")
    if uses_meshy and not already_downloaded:
        api_key = cfg.get("api_key") or ""
        if not api_key:
            raise MeshyError(
                "Falta la API key del generador 3D. Agregala al archivo .env "
                "como MESHY_API_KEY=... y reinicia el servidor.")

        if meta["source"] == "retexture":
            endpoint, payload = build_retexture_payload(meta)
            log(pid, "POST %s (prompt: %s, base: %s)" % (
                endpoint, payload["text_style_prompt"],
                "task " + payload["input_task_id"] if "input_task_id" in payload else "GLB subido"))
        else:
            images = [os.path.join(d, "input", f) for f in meta["photos"]]
            endpoint, payload = build_payload(meta, images)
            log(pid, "POST %s (%d foto/s, %s)" % (endpoint, len(images), payload["ai_model"]))
        update_meta(pid, status="GENERATING", progress=0, stage="Enviando al generador 3D")

        res = meshy_request("POST", endpoint, api_key, payload)
        task_id = res.get("result")
        if not task_id:
            raise MeshyError("El generador 3D no devolvio task id: %s" % res)
        log(pid, "task_id=%s" % task_id)
        update_meta(pid, task_id=task_id, endpoint=endpoint, stage="Generando geometria")

        # ---- polling ----
        started = time.time()
        task = {}
        while True:
            if time.time() - started > POLL_TIMEOUT:
                raise MeshyError("Timeout de %d min esperando la generacion." % (POLL_TIMEOUT // 60))
            time.sleep(POLL_SECONDS)
            task = meshy_request("GET", "%s/%s" % (endpoint, task_id), api_key)
            st = task.get("status")
            pr = int(task.get("progress") or 0)
            update_meta(pid, progress=pr, stage="Generando: %s %d%%" % (st, pr))
            if st == "SUCCEEDED":
                break
            if st in ("FAILED", "CANCELED"):
                err = (task.get("task_error") or {}).get("message") or st
                raise MeshyError("La tarea termino en %s: %s" % (st, err))

        credits = task.get("consumed_credits")
        log(pid, "generacion COMPLETA (creditos: %s)" % credits)
        update_meta(pid, status="DOWNLOADING", stage="Descargando assets", credits=credits)

        # ---- descarga ----
        urls = task.get("model_urls") or {}
        got = {}
        for fmt in ("glb", "fbx"):
            if urls.get(fmt):
                dest = os.path.join(raw_dir, "model." + fmt)
                log(pid, "descargando %s" % fmt)
                download(urls[fmt], dest)
                got[fmt] = os.path.relpath(dest, d)
        if not got.get("glb"):
            raise MeshyError("El generador 3D no devolvio GLB.")

        tex = {}
        for i, t in enumerate(task.get("texture_urls") or []):
            for key, url in (t or {}).items():
                if not url or not isinstance(url, str) or not url.startswith("http"):
                    continue
                ext = os.path.splitext(url.split("?")[0])[1] or ".png"
                dest = os.path.join(raw_dir, "textures", "%d_%s%s" % (i, key, ext))
                try:
                    download(dest=dest, url=url)
                    tex["%d_%s" % (i, key)] = os.path.relpath(dest, d)
                except Exception as e:
                    log(pid, "no se pudo bajar textura %s: %s" % (key, e))
        if task.get("thumbnail_url"):
            try:
                download(task["thumbnail_url"], os.path.join(raw_dir, "thumbnail.png"))
            except Exception:
                pass

        update_meta(pid, raw_files=got, textures=tex, thumbnail_url=task.get("thumbnail_url"))
        src_model = os.path.join(d, got["glb"])
    else:
        src_model = os.path.join(d, existing)

    # ---- Etapa 4-5: acondicionado + QA en Blender ----
    blender = cfg.get("blender_path")
    if not blender or not os.path.exists(blender):
        raise Exception(
            "No se encontro Blender. Cargá la ruta en Ajustes "
            "(ej: /Applications/Blender.app/Contents/MacOS/Blender)."
        )

    update_meta(pid, status="CONDITIONING", stage="Blender: acondicionando + QA", progress=0)
    log(pid, "Blender: %s" % blender)

    meta = read_meta(pid)
    args = json.dumps(
        {
            "src": src_model,
            "out_dir": os.path.join(d, "out"),
            "qa_dir": os.path.join(d, "qa"),
            "slug": meta["slug"],
            "target_height_m": meta["options"].get("target_height_m") or 0,
            "tri_budget": int(meta["options"].get("tri_budget") or 15000),
            "lightmap_uv": bool(meta["options"].get("lightmap_uv", True)),
            "export_fbx": True,
        }
    )

    cmd = [
        blender, "-b", "--factory-startup", "-noaudio",
        "--python", os.path.join(ROOT, "qa_blender.py"),
        "--", args,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 20)
    tail = (proc.stdout or "")[-4000:] + (proc.stderr or "")[-2000:]
    with _log_lock:
        with open(os.path.join(d, "log.txt"), "a", encoding="utf-8") as fh:
            fh.write("\n----- blender -----\n" + tail + "\n")

    metrics_path = os.path.join(d, "qa", "metrics.json")
    if proc.returncode != 0 or not os.path.exists(metrics_path):
        raise Exception("Blender fallo (code %s). Ver el log del producto." % proc.returncode)

    with open(metrics_path, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)

    checks = metrics.get("checks", [])
    failed = [c for c in checks if c["level"] == "fail"]
    status = "QA_FAILED" if failed else "DONE"
    update_meta(
        pid,
        status=status,
        progress=100,
        stage="%d/%d checks OK" % (len(checks) - len(failed), len(checks)),
        metrics=metrics,
    )
    log(pid, "%s -- %d checks, %d fallos" % (status, len(checks), len(failed)))

    # ---- sidecar de metadatos junto al modelo ----
    #      Va antes de la copia a Unity para que viaje con el GLB/FBX.
    try:
        cat = brands_mod.load_catalog(DATA)
        sidecar = brands_mod.describe(cat, meta.get("brand_id", ""), meta.get("metadata"))
        sidecar.update({
            "producto": meta["name"],
            "slug": meta["slug"],
            "generado": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modelos": (metrics.get("exported") or {}),
        })
        with open(os.path.join(d, "out", meta["slug"] + ".metadata.json"), "w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, indent=2, ensure_ascii=False)
    except Exception as e:
        log(pid, "no se pudo escribir el sidecar de metadatos: %s" % e)

    # ---- copia opcional a Unity ----
    unity_dir = cfg.get("unity_export_dir")
    if status == "DONE" and unity_dir and os.path.isdir(unity_dir):
        for f in os.listdir(os.path.join(d, "out")):
            try:
                shutil.copy2(os.path.join(d, "out", f), os.path.join(unity_dir, f))
            except Exception as e:
                log(pid, "copia a Unity fallo: %s" % e)
        log(pid, "copiado a %s" % unity_dir)


def start_job(pid):
    threading.Thread(target=run_pipeline, args=(pid,), daemon=True).start()


# ----------------------------------------------------------------------------
# Multipart minimo
# ----------------------------------------------------------------------------


def parse_multipart(body, boundary):
    parts = []
    sep = b"--" + boundary
    chunks = body.split(sep)
    for raw in chunks[1:]:
        if raw[:2] == b"--":
            break
        if raw[:2] == b"\r\n":
            raw = raw[2:]
        if raw[-2:] == b"\r\n":
            raw = raw[:-2]
        head, _, data = raw.partition(b"\r\n\r\n")
        headers = {}
        for line in head.decode("utf-8", "replace").split("\r\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        cd = headers.get("content-disposition", "")
        mname = re.search(r'name="([^"]*)"', cd)
        mfile = re.search(r'filename="([^"]*)"', cd)
        parts.append(
            {
                "name": mname.group(1) if mname else "",
                "filename": mfile.group(1) if mfile else None,
                "content_type": headers.get("content-type", ""),
                "data": data,
            }
        )
    return parts


# ----------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "Pipeline3D/1.0"

    def log_message(self, fmt, *a):  # silencia el log por request
        pass

    # -- helpers --
    def _send(self, code, body=b"", ctype="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json")

    def _err(self, msg, code=400):
        self._json({"error": str(msg)}, code)

    def _file(self, path, ctype=None):
        if not os.path.exists(path) or not os.path.isfile(path):
            return self._err("no encontrado", 404)
        ctype = ctype or (mimetypes.guess_type(path)[0] or "application/octet-stream")
        with open(path, "rb") as fh:
            self._send(200, fh.read(), ctype)

    # -- rutas --
    def do_GET(self):
        p = self.path.split("?")[0]
        try:
            if p == "/" or p == "/index.html":
                return self._file(os.path.join(STATIC, "index.html"), "text/html; charset=utf-8")

            if p == "/api/config":
                cfg = get_config()
                return self._json(
                    {
                        "has_api_key": bool(cfg.get("api_key")),
                        "api_key_var": cfg.get("api_key_var", ""),
                        "api_key_masked": ("..." + cfg["api_key"][-4:]) if cfg.get("api_key") else "",
                        "env_file": os.path.exists(os.path.join(ROOT, ".env")),
                        "blender_path": cfg.get("blender_path", ""),
                        "blender_ok": bool(cfg.get("blender_path") and os.path.exists(cfg["blender_path"])),
                        "unity_export_dir": cfg.get("unity_export_dir", ""),
                    }
                )

            if p == "/api/brands":
                cat = brands_mod.load_catalog(DATA)
                return self._json(cat)

            m = re.match(r"^/api/brands/([\w-]+)/fields$", p)
            if m:
                cat = brands_mod.load_catalog(DATA)
                bid = m.group(1)
                bid = "" if bid == "none" else bid
                brand = brands_mod.get_brand(cat, bid)
                return self._json({
                    "fields": brands_mod.fields_for(cat, bid),
                    "pipeline": (brand or {}).get("pipeline", {}),
                })

            if p == "/api/products":
                return self._json({"products": list_products()})

            m = re.match(r"^/api/products/([\w-]+)$", p)
            if m:
                meta = read_meta(m.group(1))
                return self._json(meta) if meta else self._err("no existe", 404)

            m = re.match(r"^/api/products/([\w-]+)/log$", p)
            if m:
                lp = os.path.join(product_dir(m.group(1)), "log.txt")
                txt = ""
                if os.path.exists(lp):
                    with open(lp, "r", encoding="utf-8", errors="replace") as fh:
                        txt = fh.read()[-20000:]
                return self._send(200, txt, "text/plain; charset=utf-8")

            # /api/products/<id>/file/<subpath>  (fotos, renders, modelos)
            m = re.match(r"^/api/products/([\w-]+)/file/(.+)$", p)
            if m:
                pid, rel = m.group(1), urllib.request.unquote(m.group(2))
                base = os.path.realpath(product_dir(pid))
                full = os.path.realpath(os.path.join(base, rel))
                if not full.startswith(base + os.sep):
                    return self._err("ruta invalida", 403)
                dl = "download=1" in self.path
                extra = None
                if dl:
                    extra = {"Content-Disposition": 'attachment; filename="%s"' % os.path.basename(full)}
                if not os.path.isfile(full):
                    return self._err("no encontrado", 404)
                ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                with open(full, "rb") as fh:
                    return self._send(200, fh.read(), ctype, extra)

            return self._err("ruta desconocida", 404)
        except Exception as e:
            traceback.print_exc()
            return self._err(e, 500)

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 300 * 1024 * 1024:
                return self._err("payload demasiado grande", 413)
            body = self.rfile.read(length) if length else b""
            ctype = self.headers.get("Content-Type", "")

            if p == "/api/config":
                patch = json.loads(body or b"{}")
                cfg = save_config(patch)
                return self._json({"ok": True, "blender_ok": os.path.exists(cfg.get("blender_path", ""))})

            if p == "/api/products":
                if "multipart/form-data" not in ctype:
                    return self._err("se esperaba multipart/form-data")
                mb = re.search(r"boundary=([^;]+)", ctype)
                if not mb:
                    return self._err("falta boundary")
                boundary = mb.group(1).strip().strip('"').encode()
                parts = parse_multipart(body, boundary)
                return self._create_product(parts)

            if p == "/api/brands/base":
                cat = brands_mod.load_catalog(DATA)
                payload = json.loads(body or b"{}")
                try:
                    cat["base_fields"] = brands_mod.clean_fields(payload.get("fields"))
                except brands_mod.BrandError as e:
                    return self._err(e)
                brands_mod.save_catalog(DATA, cat)
                return self._json(cat)

            if p == "/api/brands":
                cat = brands_mod.load_catalog(DATA)
                payload = json.loads(body or b"{}")
                bid = payload.get("id") or None
                if bid and not brands_mod.get_brand(cat, bid):
                    return self._err("La marca no existe", 404)
                try:
                    brand = brands_mod.clean_brand(payload, cat, bid)
                except brands_mod.BrandError as e:
                    return self._err(e)
                if bid:
                    cat["brands"] = [brand if b["id"] == bid else b for b in cat["brands"]]
                else:
                    cat["brands"].append(brand)
                brands_mod.save_catalog(DATA, cat)
                return self._json(brand, 200 if bid else 201)

            m = re.match(r"^/api/products/([\w-]+)/retexture$", p)
            if m:
                return self._create_retexture(m.group(1), json.loads(body or b"{}"))

            m = re.match(r"^/api/products/([\w-]+)/retry$", p)
            if m:
                pid = m.group(1)
                meta = read_meta(pid)
                if not meta:
                    return self._err("no existe", 404)
                # si ya hay modelo descargado, _run_pipeline solo re-corre Blender
                update_meta(pid, status="QUEUED", error=None, stage="En cola")
                start_job(pid)
                return self._json({"ok": True})

            return self._err("ruta desconocida", 404)
        except Exception as e:
            traceback.print_exc()
            return self._err(e, 500)

    def do_DELETE(self):
        m = re.match(r"^/api/brands/([\w-]+)$", self.path.split("?")[0])
        if m:
            cat = brands_mod.load_catalog(DATA)
            bid = m.group(1)
            if not brands_mod.get_brand(cat, bid):
                return self._err("La marca no existe", 404)
            usados = [p["name"] for p in list_products() if p.get("brand_id") == bid]
            if usados:
                return self._err(
                    "No se puede borrar: %d producto/s la usan (%s)"
                    % (len(usados), ", ".join(usados[:3])))
            cat["brands"] = [b for b in cat["brands"] if b["id"] != bid]
            brands_mod.save_catalog(DATA, cat)
            return self._json({"ok": True})

        m = re.match(r"^/api/products/([\w-]+)$", self.path.split("?")[0])
        if not m:
            return self._err("ruta desconocida", 404)
        pid = m.group(1)
        d = os.path.realpath(product_dir(pid))
        if os.path.isdir(d) and d.startswith(os.path.realpath(PRODUCTS) + os.sep):
            shutil.rmtree(d, ignore_errors=True)
        return self._json({"ok": True})

    # -- creacion --
    def _create_retexture(self, parent_id, body):
        parent = read_meta(parent_id)
        if not parent:
            return self._err("no existe", 404)
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return self._err("Escribi el material que queres, ej: cuero negro granulado")
        if not (parent.get("raw_files") or {}).get("glb"):
            return self._err("El producto original todavia no tiene modelo")

        pid = uuid.uuid4().hex[:12]
        name = "%s \u00b7 %s" % (parent["name"], prompt[:40])
        meta = {
            "id": pid,
            "name": name,
            "slug": slugify(parent["slug"] + "_" + prompt[:30]),
            "created_at": time.time(),
            "updated_at": time.time(),
            "status": "QUEUED",
            "stage": "En cola",
            "progress": 0,
            "options": dict(parent["options"]),
            "brand_id": parent.get("brand_id", ""),
            "brand_name": parent.get("brand_name", ""),
            "metadata": dict(parent.get("metadata") or {}),
            "photos": [],
            "raw_files": {},
            "error": None,
            "source": "retexture",
            "parent_id": parent_id,
            "retexture_prompt": prompt,
        }
        write_meta(meta)
        log(pid, "re-texturizado de '%s' con: %s" % (parent["name"], prompt))
        start_job(pid)
        return self._json(meta, 201)

    def _create_product(self, parts):
        fields = {}
        files = []
        for part in parts:
            if part["filename"]:
                files.append(part)
            else:
                fields[part["name"]] = part["data"].decode("utf-8", "replace")

        name = (fields.get("name") or "").strip() or "Producto sin nombre"
        try:
            options = json.loads(fields.get("options") or "{}")
        except Exception:
            options = {}

        # marca + metadatos: los defaults guardados en la marca rellenan lo vacio
        cat = brands_mod.load_catalog(DATA)
        brand_id = (fields.get("brand_id") or "").strip()
        if brand_id and not brands_mod.get_brand(cat, brand_id):
            return self._err("La marca seleccionada ya no existe")
        try:
            raw_meta = json.loads(fields.get("metadata") or "{}")
        except Exception:
            raw_meta = {}
        try:
            metadata = brands_mod.build_metadata(cat, brand_id, raw_meta)
        except brands_mod.BrandError as e:
            return self._err(e)

        # lo que define la marca manda sobre los defaults del formulario,
        # salvo que el usuario haya escrito algo distinto
        brand = brands_mod.get_brand(cat, brand_id)
        if brand:
            for k, v in (brand.get("pipeline") or {}).items():
                options.setdefault(k, v)

        opts = {
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

        photos = [f for f in files if (f["filename"] or "").lower().endswith((".jpg", ".jpeg", ".png"))]
        models = [f for f in files if (f["filename"] or "").lower().endswith((".glb", ".gltf"))]

        if not photos and not models:
            return self._err("Subí al menos una foto (.jpg/.png) o un modelo .glb")

        pid = uuid.uuid4().hex[:12]
        d = product_dir(pid)
        os.makedirs(os.path.join(d, "input"), exist_ok=True)

        meta = {
            "id": pid,
            "name": name,
            "slug": slugify(name),
            "created_at": time.time(),
            "updated_at": time.time(),
            "status": "QUEUED",
            "stage": "En cola",
            "progress": 0,
            "options": opts,
            "photos": [],
            "raw_files": {},
            "error": None,
            "brand_id": brand_id,
            "brand_name": brand["name"] if brand else "",
            "metadata": metadata,
        }

        if models:
            # modo modelo local: se saltea la generacion, solo acondicionado + QA (gratis)
            meta["source"] = "local"
            os.makedirs(os.path.join(d, "raw"), exist_ok=True)
            dest = os.path.join(d, "raw", "model.glb")
            with open(dest, "wb") as fh:
                fh.write(models[0]["data"])
            meta["raw_files"] = {"glb": os.path.join("raw", "model.glb")}
            meta["original_filename"] = models[0]["filename"]
        else:
            meta["source"] = "meshy"
            for i, f in enumerate(photos[:4]):
                ext = os.path.splitext(f["filename"])[1].lower() or ".jpg"
                fn = "photo_%d%s" % (i, ext)
                with open(os.path.join(d, "input", fn), "wb") as fh:
                    fh.write(f["data"])
                meta["photos"].append(fn)

        write_meta(meta)
        log(pid, "creado '%s' (%s, %d archivo/s)" % (name, meta["source"], len(files)))
        start_job(pid)
        return self._json(meta, 201)


def main():
    load_env_file()
    os.makedirs(PRODUCTS, exist_ok=True)
    port = int(os.environ.get("PORT", "8765"))
    cfg = get_config()

    # re-encola lo que quedo a medias de una corrida anterior
    for m in list_products():
        if m.get("status") in ("QUEUED", "GENERATING", "DOWNLOADING", "CONDITIONING"):
            update_meta(m["id"], status="FAILED", error="Interrumpido al reiniciar el servidor.")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("=" * 62)
    print("  Pipeline 3D")
    print("  http://127.0.0.1:%d" % port)
    print("  Blender : %s" % (cfg.get("blender_path") or "NO ENCONTRADO - cargalo en Ajustes"))
    print("  API key : %s" % (("configurada via " + cfg["api_key_var"]) if cfg.get("api_key") else "NO configurada - agregala a .env como MESHY_API_KEY"))
    print("  Ctrl+C para detener")
    print("=" * 62)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nchau")


if __name__ == "__main__":
    main()
