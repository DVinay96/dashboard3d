from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from ..config import get_settings


class MeshyError(Exception):
    pass


def request(method: str, path: str, api_key: str, payload: dict | None = None, timeout: int = 90) -> dict:
    url = get_settings().meshy_base + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + api_key)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
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
            402: "Créditos insuficientes en la cuenta del generador 3D.",
            429: "Rate limit del generador 3D alcanzado, reintenta en unos minutos.",
        }
        raise MeshyError("HTTP %s %s -- %s %s" % (e.code, e.reason, hints.get(e.code, ""), detail))
    except urllib.error.URLError as e:
        raise MeshyError("Error de red hacia Meshy: %s" % e.reason)


def data_uri(path: str | Path) -> str:
    path = str(path)
    mime, _ = mimetypes.guess_type(path)
    if mime not in ("image/jpeg", "image/png"):
        mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    with open(path, "rb") as fh:
        return "data:%s;base64,%s" % (mime, base64.b64encode(fh.read()).decode("ascii"))


def build_payload(options: dict, images: list[str]) -> tuple[str, dict]:
    o = options
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
        return "/multi-image-to-3d", payload

    payload["image_url"] = data_uri(images[0])
    if o.get("auto_size", True):
        payload["auto_size"] = True
        payload["origin_at"] = "bottom"
    payload["remove_lighting"] = bool(o.get("remove_lighting", True))
    payload["image_enhancement"] = bool(o.get("image_enhancement", True))
    return "/image-to-3d", payload


def build_retexture_payload(options: dict, prompt: str, parent_task_id: str | None, parent_glb: Path | None):
    payload = {
        "text_style_prompt": prompt[:800],
        "ai_model": options.get("ai_model", "meshy-7"),
        "enable_pbr": bool(options.get("enable_pbr", True)),
        "texture_resolution": options.get("texture_resolution", "2k"),
        "remove_lighting": True,
        "target_formats": ["glb", "fbx"],
    }
    if parent_task_id:
        payload["input_task_id"] = parent_task_id
    elif parent_glb and parent_glb.exists():
        payload["model_url"] = "data:model/gltf-binary;base64," + base64.b64encode(parent_glb.read_bytes()).decode("ascii")
    else:
        raise MeshyError("El producto original no tiene modelo para re-texturizar.")
    return "/retexture", payload


def download(url: str, dest: Path, timeout: int = 300) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "pipeline3d/2.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest
