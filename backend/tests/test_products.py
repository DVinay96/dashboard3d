import json
import stat

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import session_scope
from app.models import Product
from app.services import meshy


def new_client(api, modules=None):
    c = api.mk_client("Acme", modules)
    u = api.mk_user(c["id"], "ana@acme.com", ["admin"])
    return c, u["id"]


def test_local_glb_runs_pipeline_and_records_creator(api, fake_blender, data_dir):
    c, ana = new_client(api)
    r = api.mk_product(ana, "Silla Cloudrest")
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    p = api.call("GET", "/api/products/" + pid, who=ana).json()
    assert p["status"] == "DONE" and p["progress"] == 100 and p["source"] == "local"
    assert p["created_by"]["email"] == "ana@acme.com"
    assert [x["name"] for x in p["projects"]] == ["General"]
    assert p["metrics"]["exported"] == {"glb": "silla_cloudrest.glb"}
    assert (data_dir / "products" / pid / "out" / "silla_cloudrest.metadata.json").exists()
    sidecar = json.loads((data_dir / "products" / pid / "out" / "silla_cloudrest.metadata.json").read_text())
    assert {f["key"]: f["value"] for f in sidecar["fields"]}["sku"] == "SKU-Silla Cloudrest"
    log = api.call("GET", "/api/products/%s/log" % pid, who=ana).text
    assert "creado 'Silla Cloudrest'" in log and "DONE" in log


def test_download_serves_file_with_attachment_header(api, fake_blender):
    c, ana = new_client(api)
    pid = api.mk_product(ana).json()["id"]
    r = api.call("GET", "/api/products/%s/files/out/silla.glb?download=1" % pid, who=ana)
    assert r.status_code == 200 and r.content == b"glb"
    assert "attachment" in r.headers["content-disposition"]
    assert api.call("GET", "/api/products/%s/files/..%%2F..%%2Fpipeline.db" % pid, who=ana).status_code == 404
    assert api.call("GET", "/api/products/%s/files/out/nope.glb" % pid, who=ana).status_code == 404


def test_missing_blender_fails_with_clear_error(api):
    c, ana = new_client(api)
    pid = api.mk_product(ana).json()["id"]
    p = api.call("GET", "/api/products/" + pid, who=ana).json()
    assert p["status"] == "FAILED" and "Blender" in p["error"]


def test_project_selection_rules(api, fake_blender):
    c, ana = new_client(api)
    assert api.mk_product(ana, "uno").status_code == 201
    api.call("POST", "/api/projects", who=ana, json={"name": "Otro"})
    assert api.mk_product(ana, "dos").status_code == 400
    prj = api.projects(who=ana)
    both = [prj["General"]["id"], prj["Otro"]["id"]]
    p = api.mk_product(ana, "tres", both).json()
    assert {x["name"] for x in p["projects"]} == {"General", "Otro"}
    api.call("PATCH", "/api/projects/" + prj["Otro"]["id"], who=ana, json={"archived": True})
    assert api.mk_product(ana, "cuatro", [prj["Otro"]["id"]]).status_code == 400


def test_assign_projects_replaces_set(api, fake_blender):
    c, ana = new_client(api)
    api.call("POST", "/api/projects", who=ana, json={"name": "Otro"})
    prj = api.projects(who=ana)
    pid = api.mk_product(ana, "x", [prj["General"]["id"]]).json()["id"]
    r = api.call("PUT", "/api/products/%s/projects" % pid, who=ana, json={"project_ids": [prj["Otro"]["id"]]})
    assert [x["name"] for x in r.json()["projects"]] == ["Otro"]
    assert api.call("PUT", "/api/products/%s/projects" % pid, who=ana, json={"project_ids": []}).status_code == 422
    assert api.call("PUT", "/api/products/%s/projects" % pid, who=ana, json={"project_ids": ["zzz"]}).status_code == 400
    in_general = api.call("GET", "/api/products?project_id=" + prj["General"]["id"], who=ana).json()["products"]
    in_otro = api.call("GET", "/api/products?project_id=" + prj["Otro"]["id"], who=ana).json()["products"]
    assert in_general == [] and [p["id"] for p in in_otro] == [pid]


def test_validation_errors(api, fake_blender):
    c, ana = new_client(api)
    no_sku = api.call("POST", "/api/products", who=ana, data={"name": "x"},
                      files=[("files", ("a.glb", b"x", "model/gltf-binary"))])
    assert no_sku.status_code == 400 and "SKU" in no_sku.json()["detail"]
    assert api.call("POST", "/api/products", who=ana, data={"name": "x", "metadata": json.dumps({"sku": "1"})}
                    ).status_code == 400
    bad = api.call("POST", "/api/products", who=ana, data={"name": "x", "metadata": json.dumps({"sku": "1"})},
                   files=[("files", ("a.txt", b"x", "text/plain"))])
    assert bad.status_code == 400
    assert api.mk_product(ana, "x", brand_id="ghost").status_code == 400
    assert api.mk_product(ana, "x", options="{bad").status_code == 400
    assert api.mk_product(ana, "x", options=json.dumps({"tri_budget": "mucho"})).status_code == 400
    assert api.call("GET", "/api/products").status_code == 400


def test_retry_reruns_blender_without_generator(api, fake_blender, data_dir):
    c, ana = new_client(api)
    pid = api.mk_product(ana).json()["id"]
    out = data_dir / "products" / pid / "out" / "silla.glb"
    out.unlink()
    assert api.call("POST", "/api/products/%s/retry" % pid, who=ana).status_code == 202
    assert out.exists()
    assert api.call("GET", "/api/products/" + pid, who=ana).json()["status"] == "DONE"


def test_delete_removes_files_and_refuses_while_active(api, fake_blender, data_dir):
    c, ana = new_client(api)
    pid = api.mk_product(ana).json()["id"]
    with session_scope() as db:
        db.get(Product, pid).status = "GENERATING"
    assert api.call("DELETE", "/api/products/" + pid, who=ana).status_code == 409
    assert api.call("POST", "/api/products/%s/retry" % pid, who=ana).status_code == 409
    with session_scope() as db:
        db.get(Product, pid).status = "DONE"
    assert api.call("DELETE", "/api/products/" + pid, who=ana).status_code == 204
    assert not (data_dir / "products" / pid).exists()
    assert api.call("GET", "/api/products/" + pid, who=ana).status_code == 404


def test_brand_pipeline_defaults_and_metadata(api, fake_blender):
    c, ana = new_client(api)
    r = api.call("POST", "/api/brands", who=ana, json={
        "name": "Nórdica",
        "fields": [{"label": "Colección", "type": "select", "options": "Verano, Invierno", "required": True}],
        "pipeline": {"tri_budget": 9000, "target_height_m": 0.85}})
    assert r.status_code == 201, r.text
    brand = r.json()
    p = api.mk_product(ana, "Mesa", brand_id=brand["id"],
                       metadata=json.dumps({"sku": "M1", "coleccion": "Verano"})).json()
    assert p["options"]["tri_budget"] == 9000 and p["options"]["target_height_m"] == 0.85
    assert p["brand_name"] == "Nórdica" and p["metadata"]["coleccion"] == "Verano"
    bad = api.mk_product(ana, "Mesa2", brand_id=brand["id"], metadata=json.dumps({"sku": "M2", "coleccion": "Otoño"}))
    assert bad.status_code == 400
    assert api.call("DELETE", "/api/brands/" + brand["id"], who=ana).status_code == 409


@pytest.fixture
def with_meshy(data_dir, monkeypatch):
    monkeypatch.setenv("MESHY_API_KEY", "test-key")
    get_settings.cache_clear()
    calls = []

    def fake_request(method, path, api_key, payload=None, timeout=90):
        calls.append((method, path, payload))
        if method == "POST":
            return {"result": "task-123"}
        return {"status": "SUCCEEDED", "progress": 100, "consumed_credits": 20,
                "model_urls": {"glb": "https://x/model.glb", "fbx": "https://x/model.fbx"},
                "texture_urls": [{"base_color": "https://x/t.png"}], "thumbnail_url": "https://x/th.png"}

    def fake_download(url, dest, timeout=300):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"bytes:" + url.encode())
        return dest

    monkeypatch.setattr(meshy, "request", fake_request)
    monkeypatch.setattr(meshy, "download", fake_download)
    from app.main import create_app

    with TestClient(create_app()) as c:
        from conftest import Api

        yield Api(c), calls


def test_photo_to_3d_flow_then_retexture_uses_parent_task(with_meshy, tmp_path):
    api, calls = with_meshy
    script = tmp_path / "fb.py"
    script.write_text(
        "#!/usr/bin/env python3\nimport json,sys,pathlib\na=json.loads(sys.argv[-1])\n"
        "o=pathlib.Path(a['out_dir']);q=pathlib.Path(a['qa_dir']);o.mkdir(parents=True,exist_ok=True);q.mkdir(parents=True,exist_ok=True)\n"
        "(q/'metrics.json').write_text(json.dumps({'checks':[{'id':'x','level':'fail'}],'exported':{}}))\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    api.call("PUT", "/api/platform/settings", json={"blender_path": str(script)})
    c, ana = new_client(api)

    photos = [("files", ("a.jpg", b"\xff\xd8jpg", "image/jpeg")), ("files", ("b.png", b"png", "image/png"))]
    r = api.call("POST", "/api/products", who=ana, files=photos,
                 data={"name": "Sofa", "metadata": json.dumps({"sku": "S1"})})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    p = api.call("GET", "/api/products/" + pid, who=ana).json()
    assert p["status"] == "QA_FAILED" and p["credits"] == 20 and p["source"] == "meshy"
    assert p["raw_files"]["glb"] == "raw/model.glb"
    assert calls[0][1] == "/multi-image-to-3d" and len(calls[0][2]["image_urls"]) == 2

    calls.clear()
    rt = api.call("POST", "/api/products/%s/retexture" % pid, who=ana, json={"prompt": "cuero negro"})
    assert rt.status_code == 201
    child = api.call("GET", "/api/products/" + rt.json()["id"], who=ana).json()
    assert child["parent_id"] == pid and child["source"] == "retexture"
    assert [x["name"] for x in child["projects"]] == ["General"]
    assert calls[0][1] == "/retexture" and calls[0][2]["input_task_id"] == "task-123"


def test_missing_api_key_fails_cleanly(api):
    c, ana = new_client(api)
    r = api.call("POST", "/api/products", who=ana, data={"name": "x", "metadata": json.dumps({"sku": "1"})},
                 files=[("files", ("a.jpg", b"x", "image/jpeg"))])
    p = api.call("GET", "/api/products/" + r.json()["id"], who=ana).json()
    assert p["status"] == "FAILED" and "Integraciones" in p["error"]


def test_interrupted_jobs_are_failed_on_restart(data_dir):
    from app.main import create_app

    with TestClient(create_app()) as c:
        from conftest import Api

        api = Api(c)
        cl, ana = new_client(api)
        pid = api.mk_product(ana).json()["id"]
        with session_scope() as db:
            db.get(Product, pid).status = "CONDITIONING"
    with TestClient(create_app()) as c:
        p = c.get("/api/products/" + pid, headers={"X-Act-As": ana}).json()
        assert p["status"] == "FAILED" and "Interrumpido" in p["error"]
