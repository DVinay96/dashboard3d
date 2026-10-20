import base64
import json
import re

import httpx
import pytest

from app.config import get_settings
from app.services import unity as unity_svc

BASE = "https://unity.test/assets/v1"


class FakeUnity:
    def __init__(self):
        self.calls = []
        self.fail = {}
        self.link_response = None
        self.n_assets = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        path = (url.replace(BASE, "") if url.startswith(BASE) else url).split("?")[0]
        self.calls.append((request.method, path, dict(request.headers), body, request.url.query.decode()))
        for frag, statuses in self.fail.items():
            if frag in path and statuses:
                code = statuses.pop(0)
                if code:
                    return httpx.Response(code, json={"message": "fallo simulado"})
        if request.method == "PUT" and url.startswith("https://blob.test/"):
            return httpx.Response(201)
        if request.method == "POST" and re.fullmatch(r"/projects/[^/]+/assets", path):
            self.n_assets += 1
            return httpx.Response(200, json={"assetId": f"A{self.n_assets}", "assetVersion": f"V{self.n_assets}", "datasets": [
                {"datasetId": "D-prev", "name": "Preview", "systemTags": ["Preview"]},
                {"datasetId": "D-src", "name": "Source", "systemTags": ["Source"]}]})
        if request.method == "POST" and path.endswith("/files"):
            name = body["filePath"]
            return httpx.Response(200, json={"uploadUrl": f"https://blob.test/up/{name}?sig=1"})
        if request.method == "GET" and path.endswith("/upload-url"):
            return httpx.Response(200, json={"url": "https://blob.test/up/retry?sig=2"})
        if request.method == "GET" and path == "/libraries":
            return httpx.Response(200, json={"results": [], "total": 0})
        if path.endswith("/finalize"):
            return httpx.Response(204)
        if path.endswith("/autosubmit"):
            return httpx.Response(200, json={"versionNumber": 1})
        if "/link/projects/" in path:
            if self.link_response is not None:
                return httpx.Response(200, json=self.link_response)
            return httpx.Response(200, json={"addedAssetIds": [path.split("/assets/")[1].split("/")[0]], "alreadyLinkedAssetIds": [], "assetErrors": []})
        return httpx.Response(404, json={"message": "ruta no simulada " + path})

    def of(self, kind):
        return [c for c in self.calls if (c[0], c[1].rsplit("/", 1)[-1]) == kind or (c[0] == kind[0] and kind[1] in c[1])]


@pytest.fixture
def unity(monkeypatch, api, fake_blender):
    monkeypatch.setenv("UNITY_KEY_ID", "key-id")
    monkeypatch.setenv("UNITY_KEY_SECRET", "key-secret")
    monkeypatch.setenv("UNITY_API_BASE", BASE)
    get_settings.cache_clear()
    fake = FakeUnity()
    client = unity_svc.UnityClient("key-id", "key-secret", BASE, http=httpx.Client(transport=httpx.MockTransport(fake.handler)), retry_sleep=0)
    monkeypatch.setattr(unity_svc, "get_client", lambda: client)
    rows = api.call("GET", "/api/integrations").json()["items"]
    unity_row = next(i for i in rows if i["kind"] == "unity")
    api.call("PUT", "/api/integrations/" + unity_row["id"], json={"config": {"auto_sync": False}})
    fake.client = client
    return fake


def setup_client(api, projects=("General",), unity_ids=None, modules=None):
    c = api.mk_client("Acme", modules or ["catalog", "generation", "brands", "unity"])
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    prj = api.projects(who=ana)
    for name in projects:
        if name not in prj:
            api.call("POST", "/api/projects", who=ana, json={"name": name})
    prj = api.projects(who=ana)
    for name, uid in (unity_ids or {"General": "UP-1"}).items():
        r = api.call("PATCH", "/api/projects/" + prj[name]["id"], client_id=c["id"], json={"unity_project_id": uid})
        assert r.status_code == 200, r.text
    return c, ana, prj


def sync(api, who, pid):
    return api.call("POST", f"/api/products/{pid}/unity/sync", who=who)


def test_full_flow_one_project(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla Cloudrest").json()["id"]
    r = sync(api, ana, pid)
    assert r.status_code == 202, r.text

    kinds = [(m, p.split("/", 3)[-1] if p.startswith("/projects") else p) for m, p, *_ in unity.calls]
    methods = [m for m, *_ in unity.calls]
    assert methods[0] == "POST" and unity.calls[0][1] == "/projects/UP-1/assets"
    create = unity.calls[0]
    assert create[3]["name"] == "Silla Cloudrest" and create[3]["primaryType"] == "3D Model"
    assert "pipeline3d" in create[3]["tags"] and "acme" in create[3]["tags"]
    assert "Cliente: Acme" in create[3]["description"] and "ana@acme.com" in create[3]["description"]

    expected = "Basic " + base64.b64encode(b"key-id:key-secret").decode()
    for method, path, headers, body, _ in unity.calls:
        if path.startswith("https://blob.test"):
            assert "authorization" not in headers and headers["x-ms-blob-type"] == "BlockBlob"
        else:
            assert headers["authorization"] == expected

    files = [c_ for c_ in unity.calls if c_[0] == "POST" and c_[1].endswith("/files")]
    assert [f[3]["filePath"] for f in files] == ["silla_cloudrest.glb", "silla_cloudrest.metadata.json"]
    assert files[0][3]["mainFile"] is True and files[1][3]["mainFile"] is False
    assert all("/assets/A1/versions/V1/datasets/D-src/files" in f[1] for f in files)
    assert len([c_ for c_ in unity.calls if c_[1].endswith("/finalize")]) == 2
    order = [("asset" if p.endswith("/assets") else "file" if p.endswith("/files") else "put" if m == "PUT" else "fin" if p.endswith("/finalize") else "submit")
             for m, p, *_ in unity.calls]
    assert order == ["asset", "file", "put", "fin", "file", "put", "fin", "submit"]

    row = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]
    assert row["status"] == "SYNCED" and row["unity_asset_id"] == "A1" and row["project_name"] == "General"
    st = api.call("GET", "/api/unity/status", who=ana).json()
    assert st["configured"] is True and [i["status"] for i in st["items"]] == ["SYNCED"]


def test_several_projects_create_once_and_link_the_rest(api, unity):
    c, ana, prj = setup_client(api, ("General", "Otoño", "Verano"), {"General": "UP-1", "Otoño": "UP-2", "Verano": "UP-1"})
    ids = [prj[n]["id"] for n in ("General", "Otoño", "Verano")]
    pid = api.mk_product(ana, "Mesa", ids).json()["id"]
    assert sync(api, ana, pid).status_code == 202
    assert unity.n_assets == 1
    links = [c_ for c_ in unity.calls if "/link/projects/" in c_[1]]
    assert [l[1] for l in links] == ["/projects/UP-1/assets/A1/link/projects/UP-2"]
    rows = {r["project_name"]: r for r in api.call("GET", "/api/products/" + pid, who=ana).json()["unity"]}
    assert {n: r["status"] for n, r in rows.items()} == {"General": "SYNCED", "Otoño": "SYNCED", "Verano": "SYNCED"}
    assert {r["unity_asset_id"] for r in rows.values()} == {"A1"}


def test_resync_is_refused_and_a_new_project_only_links(api, unity):
    c, ana, prj = setup_client(api, ("General", "Otoño"), {"General": "UP-1"})
    pid = api.mk_product(ana, "Mesa", [prj["General"]["id"]]).json()["id"]
    assert sync(api, ana, pid).status_code == 202
    assert sync(api, ana, pid).status_code == 409
    api.call("PATCH", "/api/projects/" + prj["Otoño"]["id"], client_id=c["id"], json={"unity_project_id": "UP-9"})
    api.call("PUT", f"/api/products/{pid}/projects", who=ana, json={"project_ids": [prj["General"]["id"], prj["Otoño"]["id"]]})
    unity.calls.clear()
    assert sync(api, ana, pid).status_code == 202
    assert [(m, p) for m, p, *_ in unity.calls] == [("POST", "/projects/UP-1/assets/A1/link/projects/UP-9")]
    assert unity.n_assets == 1


def test_failure_is_reported_and_retry_resumes_without_duplicates(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    unity.fail["metadata.json/finalize"] = [503, 503, 503]
    assert sync(api, ana, pid).status_code == 202
    row = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]
    assert row["status"] == "FAILED" and "tras 3 intentos" in row["error"] and row["attempts"] == 1
    assert unity.n_assets == 1
    assert "Unity: ERROR" in api.call("GET", f"/api/products/{pid}/log", who=ana).text

    unity.calls.clear()
    assert sync(api, ana, pid).status_code == 202
    row = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]
    assert row["status"] == "SYNCED" and row["attempts"] == 2 and row["error"] is None
    assert unity.n_assets == 1
    created = [c_[3]["filePath"] for c_ in unity.calls if c_[0] == "POST" and c_[1].endswith("/files")]
    assert created == ["silla.metadata.json"]


def test_a_500_is_not_retried_but_explained(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    unity.fail["/assets"] = [500]
    sync(api, ana, pid)
    row = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]
    assert row["status"] == "FAILED" and "HTTP 500" in row["error"]
    assert len([c_ for c_ in unity.calls if c_[1] == "/projects/UP-1/assets"]) == 1


def test_http_errors_come_with_a_useful_hint(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    unity.fail["/assets"] = [403]
    sync(api, ana, pid)
    err = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]["error"]
    assert "HTTP 403" in err and "Contributor" in err
    unity.fail["/assets"] = [401]
    sync(api, ana, pid)
    err = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]["error"]
    assert "HTTP 401" in err and "UNITY_KEY_ID" in err


def test_transient_errors_are_retried(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    unity.fail["/autosubmit"] = [503, 429]
    sync(api, ana, pid)
    assert api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]["status"] == "SYNCED"


def test_partial_and_conflicting_file_creation_fall_back_to_upload_url(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    unity.fail["/datasets/D-src/files"] = [409, 0]
    sync(api, ana, pid)
    assert api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]["status"] == "SYNCED"
    assert any(c_[0] == "GET" and c_[1].endswith("/silla.glb/upload-url") for c_ in unity.calls)


def test_link_errors_fail_the_destination(api, unity):
    c, ana, prj = setup_client(api, ("General", "Otoño"), {"General": "UP-1", "Otoño": "UP-2"})
    pid = api.mk_product(ana, "Mesa", [prj["General"]["id"], prj["Otoño"]["id"]]).json()["id"]
    unity.link_response = {"addedAssetIds": [], "alreadyLinkedAssetIds": [], "assetErrors": [{"message": "sin permiso"}]}
    sync(api, ana, pid)
    rows = {r["project_name"]: r for r in api.call("GET", "/api/products/" + pid, who=ana).json()["unity"]}
    assert rows["General"]["status"] == "SYNCED" and rows["Otoño"]["status"] == "FAILED"
    assert "no pudo enlazar" in rows["Otoño"]["error"]
    unity.link_response = None
    sync(api, ana, pid)
    assert unity.n_assets == 1
    assert {r["status"] for r in api.call("GET", "/api/products/" + pid, who=ana).json()["unity"]} == {"SYNCED"}


def test_not_configured_is_a_clear_409(api, fake_blender, monkeypatch):
    for k in ("UNITY_KEY_ID", "UNITY_KEY_SECRET"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    r = sync(api, ana, pid)
    assert r.status_code == 409 and "UNITY_KEY_ID" in r.json()["detail"]
    assert api.call("GET", "/api/unity/status", who=ana).json()["configured"] is False
    assert api.call("GET", "/api/platform/settings").json()["unity_configured"] is False


def test_platform_settings_report_unity(api, unity):
    s = api.call("GET", "/api/platform/settings").json()
    assert s["unity_configured"] is True and s["unity_api_base"] == BASE


def test_only_finished_products_with_a_destination_can_sync(api, unity):
    c, ana, prj = setup_client(api, ("General", "SinUnity"), {"General": "UP-1"})
    ok = api.mk_product(ana, "Ok", [prj["General"]["id"]]).json()["id"]
    no_dest = api.mk_product(ana, "NoDest", [prj["SinUnity"]["id"]]).json()["id"]
    r = sync(api, ana, no_dest)
    assert r.status_code == 400 and "destino en Unity" in r.json()["detail"]
    from app.db import session_scope
    from app.models import Product

    with session_scope() as db:
        db.get(Product, ok).status = "QA_FAILED"
    assert sync(api, ana, ok).status_code == 409
    assert sync(api, ana, "nope").status_code == 404
    assert unity.calls == []


def test_permissions_and_module_gating(api, unity):
    c, ana, prj = setup_client(api)
    viewer = api.mk_user(c["id"], "vic@acme.com", ["viewer"])["id"]
    pid = api.mk_product(ana, "Silla").json()["id"]
    assert sync(api, viewer, pid).status_code == 403
    assert api.call("GET", "/api/unity/status", who=viewer).status_code == 200
    other = api.mk_client("Beta", ["catalog", "generation", "brands", "unity"])
    bob = api.mk_user(other["id"], "bob@beta.com", ["admin"])["id"]
    assert sync(api, bob, pid).status_code == 404
    assert api.call("GET", "/api/unity/status", who=bob).json()["items"] == []
    api.call("PATCH", "/api/clients/" + c["id"], json={"modules": ["catalog", "generation", "brands"]})
    assert sync(api, ana, pid).status_code == 403
    assert api.call("GET", "/api/unity/status", who=ana).status_code == 403
    assert unity.calls == []


def test_scoped_role_only_syncs_its_project(api, unity):
    c, ana, prj = setup_client(api, ("General", "Otoño"), {"General": "UP-1", "Otoño": "UP-2"})
    role = api.mk_role("Sync Otoño", [{"effect": "allow", "actions": ["products:list", "products:read", "unity:*"],
                                      "resources": ["project/%s/*" % prj["Otoño"]["id"]]}], c["id"])
    lu = api.mk_user(c["id"], "lu@acme.com", [role["id"]])["id"]
    g = api.mk_product(ana, "G", [prj["General"]["id"]]).json()["id"]
    o = api.mk_product(ana, "O", [prj["Otoño"]["id"]]).json()["id"]
    assert sync(api, lu, g).status_code == 403
    assert sync(api, lu, o).status_code == 202
    items = api.call("GET", "/api/unity/status", who=lu).json()["items"]
    assert [i["product_id"] for i in items] == [o]


def test_interrupted_syncs_fail_on_restart(api, unity):
    c, ana, prj = setup_client(api)
    pid = api.mk_product(ana, "Silla").json()["id"]
    sync(api, ana, pid)
    from app.db import session_scope
    from app.models import UnitySync
    from app.services.bootstrap import fail_interrupted

    with session_scope() as db:
        db.query(UnitySync).one().status = "SYNCING"
    with session_scope() as db:
        fail_interrupted(db)
    with session_scope() as db:
        row = db.query(UnitySync).one()
        assert row.status == "FAILED" and "Interrumpido" in row.error
