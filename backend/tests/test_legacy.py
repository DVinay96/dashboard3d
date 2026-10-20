import json

from fastapi.testclient import TestClient

from app.config import get_settings


def write_legacy(data_dir):
    (data_dir / "products" / "aaa111").mkdir(parents=True)
    (data_dir / "products" / "bbb222").mkdir(parents=True)
    (data_dir / "brands.json").write_text(json.dumps({
        "base_fields": [{"key": "sku", "label": "SKU", "type": "text", "required": True,
                         "options": [], "default": "", "help": ""}],
        "brands": [{"id": "br1", "name": "Nórdica", "slug": "nordica", "notes": "", "pipeline": {"tri_budget": 9000},
                    "fields": [{"key": "color", "label": "Color", "type": "text", "required": False,
                                "options": [], "default": "", "help": ""}], "created_at": 5.0}],
    }))
    (data_dir / "config.json").write_text(json.dumps({"blender_path": "/x/blender", "unity_export_dir": "/x/unity"}))
    base = {"slug": "s", "status": "DONE", "stage": "ok", "progress": 100, "options": {"tri_budget": 15000},
            "photos": [], "raw_files": {"glb": "raw/model.glb"}, "source": "meshy", "error": None, "metadata": {"sku": "1"}}
    (data_dir / "products" / "aaa111" / "meta.json").write_text(json.dumps(
        dict(base, id="aaa111", name="Padre", brand_id="br1", created_at=10.0, updated_at=11.0, credits=20,
             metrics={"checks": []}, task_id="t1")))
    (data_dir / "products" / "bbb222" / "meta.json").write_text(json.dumps(
        dict(base, id="bbb222", name="Hijo", brand_id="borrada", created_at=5.0, updated_at=6.0,
             source="retexture", parent_id="aaa111", retexture_prompt="cuero", created_by={"username": "x"})))


def boot(data_dir):
    from app.main import create_app

    return TestClient(create_app())


def test_legacy_data_is_imported_once(data_dir):
    write_legacy(data_dir)
    with boot(data_dir) as c:
        clients = c.get("/api/clients").json()
        assert [x["name"] for x in clients] == ["Cliente por defecto"]
        cid = clients[0]["id"]
        assert clients[0]["modules"] == ["catalog", "generation", "brands", "unity"]
        assert (clients[0]["product_count"], clients[0]["project_count"]) == (2, 1)

        h = {"X-Client-Id": cid}
        cat = c.get("/api/brands", headers=h).json()
        assert [b["id"] for b in cat["brands"]] == ["br1"] and cat["brands"][0]["pipeline"] == {"tri_budget": 9000}
        assert [f["key"] for f in cat["base_fields"]] == ["sku"]

        prods = {p["id"]: p for p in c.get("/api/products", headers=h).json()["products"]}
        assert set(prods) == {"aaa111", "bbb222"}
        assert prods["aaa111"]["brand_name"] == "Nórdica" and prods["aaa111"]["credits"] == 20
        assert prods["aaa111"]["created_at"] == 10.0 and prods["aaa111"]["metadata"] == {"sku": "1"}
        assert [x["name"] for x in prods["aaa111"]["projects"]] == ["General"]
        assert prods["bbb222"]["parent_id"] == "aaa111" and prods["bbb222"]["brand_id"] is None
        assert prods["bbb222"]["created_by"] is None

        s = c.get("/api/platform/settings").json()
        assert s["blender_path"] == "/x/blender" and s["unity_export_dir"] == "/x/unity"

    get_settings.cache_clear()
    with boot(data_dir) as c:
        assert len(c.get("/api/clients").json()) == 1
        assert c.get("/api/clients").json()[0]["product_count"] == 2
    assert (data_dir / "products" / "aaa111" / "meta.json").exists() and (data_dir / "brands.json").exists()


def test_nothing_imported_on_a_fresh_install(api):
    assert api.call("GET", "/api/clients").json() == []


def test_not_imported_if_clients_already_exist(data_dir):
    with boot(data_dir) as c:
        c.post("/api/clients", json={"name": "Propio"})
    write_legacy(data_dir)
    get_settings.cache_clear()
    with boot(data_dir) as c:
        assert [x["name"] for x in c.get("/api/clients").json()] == ["Propio"]
