from __future__ import annotations

import base64
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from . import integrations


class UnityError(Exception):
    pass


HINTS = {
    401: "Credenciales de la cuenta de servicio invalidas (UNITY_KEY_ID / UNITY_KEY_SECRET).",
    403: "La cuenta de servicio no tiene permiso en ese proyecto: necesita el rol Asset Manager Contributor o Admin.",
    404: "No existe en Unity el proyecto, el asset o el archivo (revisa el ID de proyecto de Unity).",
    409: "Conflicto en Unity: el recurso ya existe o la versión ya esta congelada.",
    429: "Unity limitó las peticiones; reintenta en unos minutos.",
}
RETRY_STATUS = {429, 502, 503, 504}


def _seg(value: str) -> str:
    return quote(value, safe="")


class UnityClient:
    def __init__(self, key_id: str, key_secret: str, base_url: str, http: httpx.Client | None = None,
                 attempts: int = 3, retry_sleep: float = 1.0):
        token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
        self._auth = {"Authorization": "Basic " + token}
        self.base = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=httpx.Timeout(30.0, read=300.0))
        self._attempts = attempts
        self._sleep = retry_sleep

    def _send(self, method: str, url: str, **kw) -> httpx.Response:
        last: Exception | None = None
        for i in range(self._attempts):
            try:
                r = self._http.request(method, url, **kw)
                if r.status_code not in RETRY_STATUS:
                    return r
                last = UnityError(f"HTTP {r.status_code}")
            except httpx.TransportError as e:
                last = e
            if i < self._attempts - 1:
                time.sleep(self._sleep * (2**i))
        raise UnityError(f"Unity no respondió bien tras {self._attempts} intentos: {last}")

    def _call(self, method: str, path: str, ok: tuple[int, ...] = (200, 204), **kw) -> httpx.Response:
        r = self._send(method, self.base + path, headers=self._auth, **kw)
        if r.status_code not in ok:
            detail = r.text[:300].strip()
            raise UnityError(
                f"Unity respondió HTTP {r.status_code} en {method} {path}. {HINTS.get(r.status_code, '')} {detail}".strip()
            )
        return r

    def create_asset(self, project: str, name: str, description: str, tags: list[str]) -> dict:
        r = self._call("POST", f"/projects/{_seg(project)}/assets",
                       json={"name": name[:200], "description": description[:2000], "tags": tags, "primaryType": "3D Model"})
        d = r.json()
        datasets = d.get("datasets") or []
        source = next((x for x in datasets if "Source" in (x.get("systemTags") or [])), datasets[0] if datasets else None)
        if not d.get("assetId") or not d.get("assetVersion") or not source:
            raise UnityError(f"Respuesta inesperada al crear el asset: {r.text[:200]}")
        return {"asset_id": d["assetId"], "version": d["assetVersion"], "dataset_id": source["datasetId"]}

    def _file_path(self, project: str, asset: str, version: str, dataset: str) -> str:
        return f"/projects/{_seg(project)}/assets/{_seg(asset)}/versions/{_seg(version)}/datasets/{_seg(dataset)}/files"

    def upload_url(self, project: str, asset: str, version: str, dataset: str, file_path: str, size: int) -> str:
        r = self._call("GET", f"{self._file_path(project, asset, version, dataset)}/{_seg(file_path)}/upload-url",
                       params={"fileSize": size})
        url = r.json().get("url")
        if not url:
            raise UnityError(f"Unity no devolvió URL de subida para {file_path}")
        return url

    def create_file(self, project: str, asset: str, version: str, dataset: str, file_path: str, size: int,
                    main: bool = False, description: str = "") -> str:
        body = {"filePath": file_path, "fileSize": size, "mainFile": main, "description": description}
        r = self._call("POST", self._file_path(project, asset, version, dataset), ok=(200, 206, 409), json=body)
        if r.status_code == 200 and r.json().get("uploadUrl"):
            return r.json()["uploadUrl"]
        return self.upload_url(project, asset, version, dataset, file_path, size)

    def upload(self, url: str, path: Path) -> None:
        headers = {"x-ms-blob-type": "BlockBlob", "Content-Type": "application/octet-stream"}
        r = self._send("PUT", url, content=path.read_bytes(), headers=headers)
        if r.status_code not in (200, 201):
            raise UnityError(f"La subida de {path.name} falló (HTTP {r.status_code}): {r.text[:200]}")

    def finalize(self, project: str, asset: str, version: str, dataset: str, file_path: str) -> None:
        self._call("POST", f"{self._file_path(project, asset, version, dataset)}/{_seg(file_path)}/finalize", ok=(200, 204))

    def autosubmit(self, project: str, asset: str, version: str, changelog: str) -> int | None:
        r = self._call("POST", f"/projects/{_seg(project)}/assets/{_seg(asset)}/versions/{_seg(version)}/autosubmit",
                       json={"changeLog": changelog[:1000]})
        return (r.json() or {}).get("versionNumber") if r.content else None

    def ping(self) -> None:
        self._call("GET", "/libraries", params={"limit": 1})

    def link(self, project: str, asset: str, destination: str) -> None:
        r = self._call("POST", f"/projects/{_seg(project)}/assets/{_seg(asset)}/link/projects/{_seg(destination)}")
        if r.status_code == 200 and r.content:
            body = r.json()
            errors = body.get("assetErrors") or []
            ok = asset in (body.get("addedAssetIds") or []) or asset in (body.get("alreadyLinkedAssetIds") or [])
            if errors or not ok:
                raise UnityError(f"Unity no pudo enlazar el asset al proyecto {destination}: {errors or body}")


def is_configured() -> bool:
    return integrations.unity_credentials() is not None


def get_client() -> UnityClient | None:
    creds = integrations.unity_credentials()
    if creds is None:
        return None
    return UnityClient(creds["key_id"], creds["key_secret"], creds["api_base"])
