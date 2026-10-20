import json


def stmt(effect, actions, resources=("*",)):
    return {"effect": effect, "actions": list(actions), "resources": list(resources)}


def test_client_crud_and_counts(api):
    acme = api.mk_client("Acme", ["catalog"])
    api.mk_user(acme["id"], "ana@acme.com", ["viewer"])
    got = api.call("GET", "/api/clients/" + acme["id"]).json()
    assert got["user_count"] == 1 and got["project_count"] == 1 and got["product_count"] == 0
    assert api.call("POST", "/api/clients", json={"name": "acme"}).status_code == 409
    r = api.call("PATCH", "/api/clients/" + acme["id"],
                 json={"name": "Acme SA", "theme": {"accent": "#ff8800", "logo_url": "https://x/l.png"}})
    assert r.json()["name"] == "Acme SA" and r.json()["theme"]["accent"] == "#ff8800"
    assert api.call("PATCH", "/api/clients/" + acme["id"], json={"theme": {"accent": "rojo"}}).status_code == 400
    assert api.call("PATCH", "/api/clients/" + acme["id"], json={"theme": {"logo_url": "javascript:x"}}).status_code == 400
    assert api.call("GET", "/api/clients/nope").status_code == 404


def test_delete_client_cascades_unless_it_has_products(api, fake_blender):
    acme = api.mk_client("Acme")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    api.mk_product(ana["id"])
    assert api.call("DELETE", "/api/clients/" + acme["id"]).status_code == 409
    empty = api.mk_client("Vacío")
    api.mk_user(empty["id"], "v@v.com", ["viewer"])
    assert api.call("DELETE", "/api/clients/" + empty["id"]).status_code == 204
    assert [u["email"] for u in api.call("GET", "/api/users").json()] == ["admin@local", "ana@acme.com"]


def test_user_rules(api):
    acme, beta = api.mk_client("Acme"), api.mk_client("Beta")
    mine = api.mk_role("Mío", [stmt("allow", ["brands:read"])], acme["id"])
    ok = api.mk_user(acme["id"], "  Ana@Acme.COM ", [mine["id"], "viewer"])
    assert ok["email"] == "ana@acme.com" and set(ok["role_ids"]) == {mine["id"], "viewer"}
    assert ok["client_name"] == "Acme"
    r = lambda body: api.call("POST", "/api/users", json=body).status_code
    assert r({"email": "ana@acme.com", "client_id": acme["id"]}) == 409
    assert r({"email": "no-es-email", "client_id": acme["id"]}) == 400
    assert r({"email": "x@y.com"}) == 400
    assert r({"email": "x@y.com", "client_id": "ghost"}) == 400
    assert r({"email": "x@y.com", "client_id": beta["id"], "role_ids": [mine["id"]]}) == 400
    assert r({"email": "x@y.com", "client_id": beta["id"], "role_ids": ["ghost"]}) == 400
    sa = api.call("POST", "/api/users", json={"email": "boss@corp.com", "is_super_admin": True, "client_id": acme["id"]})
    assert sa.status_code == 201 and sa.json()["client_id"] is None
    assert [u["email"] for u in api.call("GET", "/api/users?client_id=" + acme["id"]).json()] == ["ana@acme.com"]


def test_super_admin_guards(api):
    me = api.call("GET", "/api/me").json()["user"]
    assert api.call("DELETE", "/api/users/" + me["id"]).status_code == 400
    assert api.call("PATCH", "/api/users/" + me["id"], json={"disabled": True}).status_code == 400
    other = api.call("POST", "/api/users", json={"email": "boss@corp.com", "is_super_admin": True}).json()
    assert api.call("PATCH", "/api/users/" + me["id"], who=other["id"], json={"disabled": True}).status_code == 200
    third = api.call("POST", "/api/users", who=other["id"], json={"email": "t@corp.com", "is_super_admin": True}).json()
    api.call("PATCH", "/api/users/" + third["id"], who=other["id"], json={"disabled": True})
    assert api.call("PATCH", "/api/users/" + other["id"], who=third["id"], json={"disabled": True}).status_code == 403
    assert api.call("DELETE", "/api/users/" + other["id"], who=other["id"]).status_code == 400


def test_user_update_roles_and_name(api):
    acme = api.mk_client("Acme")
    u = api.mk_user(acme["id"], "ana@acme.com", ["viewer"])
    r = api.call("PATCH", "/api/users/" + u["id"], json={"display_name": "Ana", "role_ids": ["operator"]}).json()
    assert r["display_name"] == "Ana" and r["role_names"] == ["Operador"]
    assert api.call("PATCH", "/api/users/" + u["id"], json={"role_ids": ["ghost"]}).status_code == 400
    assert api.call("PATCH", "/api/users/nope", json={}).status_code == 404


def test_builtin_roles_seeded_and_protected(api):
    roles = {r["id"]: r for r in api.call("GET", "/api/roles").json()}
    assert {"viewer", "operator", "manager", "admin"} <= set(roles)
    assert all(roles[i]["builtin"] for i in ("viewer", "operator", "manager", "admin"))
    assert api.call("DELETE", "/api/roles/viewer").status_code == 400


def test_role_validation_scope_and_deletion(api):
    acme, beta = api.mk_client("Acme"), api.mk_client("Beta")
    bad = {"name": "Mala", "statements": [stmt("allow", ["producs:read"])]}
    assert api.call("POST", "/api/roles", json=bad).status_code == 400
    r = api.mk_role("Custom", [stmt("allow", ["brands:read"])], acme["id"])
    assert api.call("POST", "/api/roles", json={"name": "custom", "statements": [stmt("allow", ["brands:read"])],
                                                 "client_id": acme["id"]}).status_code == 409
    api.mk_role("Custom", [stmt("allow", ["brands:read"])], beta["id"])
    names = [x["name"] for x in api.call("GET", "/api/roles?client_id=" + acme["id"]).json()]
    assert "Custom" in names and names.count("Custom") == 1 and "Solo lectura" in names
    u = api.mk_user(acme["id"], "ana@acme.com", [r["id"]])
    assert api.call("DELETE", "/api/roles/" + r["id"]).status_code == 409
    api.call("PATCH", "/api/users/" + u["id"], json={"role_ids": []})
    assert api.call("DELETE", "/api/roles/" + r["id"]).status_code == 204
    assert api.call("PUT", "/api/roles/ghost", json={"name": "x", "statements": [stmt("allow", ["*"])]}).status_code == 404


def test_role_edit_takes_effect_immediately(api):
    acme = api.mk_client("Acme")
    role = api.mk_role("R", [stmt("allow", ["brands:read"])], acme["id"])
    u = api.mk_user(acme["id"], "ana@acme.com", [role["id"]])
    assert api.call("GET", "/api/projects", who=u["id"]).status_code == 403
    api.call("PUT", "/api/roles/" + role["id"], json={"name": "R", "statements": [stmt("allow", ["projects:read"])]})
    assert api.call("GET", "/api/projects", who=u["id"]).status_code == 200


def test_project_rules(api, fake_blender):
    acme = api.mk_client("Acme")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])["id"]
    pr = api.call("POST", "/api/projects", who=ana, json={"name": "Otoño", "description": "d"}).json()
    assert api.call("POST", "/api/projects", who=ana, json={"name": "otoño"}).status_code == 409
    assert api.call("PATCH", "/api/projects/" + pr["id"], who=ana, json={"name": "General"}).status_code == 409
    assert api.call("PATCH", "/api/projects/" + pr["id"], who=ana, json={"unity_project_id": "u-1"}).status_code == 403
    r = api.call("PATCH", "/api/projects/" + pr["id"], client_id=acme["id"], json={"unity_project_id": " u-1 "})
    assert r.json()["unity_project_id"] == "u-1"
    r = api.call("PATCH", "/api/projects/" + pr["id"], client_id=acme["id"], json={"unity_project_id": None})
    assert r.json()["unity_project_id"] is None
    api.mk_product(ana, "x", [pr["id"]])
    assert api.call("DELETE", "/api/projects/" + pr["id"], who=ana).status_code == 409
    assert api.projects(who=ana)["Otoño"]["product_count"] == 1
    other = api.mk_client("Beta")
    assert api.call("PATCH", "/api/projects/" + pr["id"], client_id=other["id"], json={"name": "x"}).status_code == 404


def test_brands_are_per_client_and_validated(api):
    acme, beta = api.mk_client("Acme"), api.mk_client("Beta")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])["id"]
    bob = api.mk_user(beta["id"], "bob@beta.com", ["admin"])["id"]
    brand = api.call("POST", "/api/brands", who=ana, json={"name": "Nórdica"}).json()
    assert api.call("GET", "/api/brands", who=bob).json()["brands"] == []
    assert api.call("PUT", "/api/brands/" + brand["id"], who=bob, json={"name": "x"}).status_code == 404
    assert api.call("DELETE", "/api/brands/" + brand["id"], who=bob).status_code == 404
    for bad in ({"name": ""}, {"name": "nórdica"},
                {"name": "B", "fields": [{"label": "SKU"}]},
                {"name": "B", "fields": [{"label": "L", "type": "select"}]},
                {"name": "B", "pipeline": {"tri_budget": "x"}}):
        assert api.call("POST", "/api/brands", who=ana, json=bad).status_code == 400, bad
    up = api.call("PUT", "/api/brands/" + brand["id"], who=ana, json={"name": "Nórdica 2", "notes": "n"}).json()
    assert up["name"] == "Nórdica 2" and up["slug"] == "nordica_2"
    fields = api.call("GET", "/api/brands/%s/fields" % brand["id"], who=ana).json()
    assert [f["key"] for f in fields["fields"]] == ["sku", "nombre_comercial", "precio"]
    assert api.call("GET", "/api/brands/none/fields", who=ana).status_code == 200
    assert api.call("GET", "/api/brands/ghost/fields", who=ana).status_code == 404
    assert api.call("DELETE", "/api/brands/" + brand["id"], who=ana).status_code == 204


def test_base_fields_are_per_client(api):
    acme, beta = api.mk_client("Acme"), api.mk_client("Beta")
    r = api.call("PUT", "/api/brands/base-fields", client_id=acme["id"],
                 json={"fields": [{"label": "Código interno", "type": "text", "required": True}]})
    assert [f["key"] for f in r.json()["base_fields"]] == ["codigo_interno"]
    beta_fields = api.call("GET", "/api/brands", client_id=beta["id"]).json()["base_fields"]
    assert [f["key"] for f in beta_fields] == ["sku", "nombre_comercial", "precio"]
    dup = api.call("PUT", "/api/brands/base-fields", client_id=acme["id"],
                   json={"fields": [{"label": "A"}, {"label": "a"}]})
    assert dup.status_code == 400


def test_brand_scoped_role(api):
    acme = api.mk_client("Acme")
    root = api.mk_user(acme["id"], "root@acme.com", ["admin"])["id"]
    b1 = api.call("POST", "/api/brands", who=root, json={"name": "Uno"}).json()
    b2 = api.call("POST", "/api/brands", who=root, json={"name": "Dos"}).json()
    role = api.mk_role("Solo Uno", [stmt("allow", ["brands:read"], ["brand/%s" % b1["id"]])], acme["id"])
    u = api.mk_user(acme["id"], "u@acme.com", [role["id"]])["id"]
    assert [b["name"] for b in api.call("GET", "/api/brands", who=u).json()["brands"]] == ["Uno"]
    assert api.call("GET", "/api/brands/%s/fields" % b2["id"], who=u).status_code == 403
    assert api.call("GET", "/api/brands/none/fields", who=u).status_code == 403


def test_platform_settings(api, tmp_path):
    s = api.call("GET", "/api/platform/settings").json()
    assert s["meshy_key_set"] is False and s["unity_export_dir"] == ""
    r = api.call("PUT", "/api/platform/settings", json={"unity_export_dir": str(tmp_path), "blender_path": "/no/existe"})
    assert r.json()["unity_export_dir"] == str(tmp_path) and r.json()["blender_ok"] is False


def test_modules_catalog_and_dev_identities(api):
    ids = [m["id"] for m in api.call("GET", "/api/modules").json()]
    assert ids == ["catalog", "generation", "brands", "unity"]
    acme = api.mk_client("Acme")
    api.mk_user(acme["id"], "ana@acme.com", ["viewer"])
    d = api.call("GET", "/api/dev/identities").json()
    assert [c["name"] for c in d["clients"]] == ["Acme"]
    assert [u["email"] for u in d["users"]] == ["ana@acme.com"]


def test_unknown_auth_mode_is_refused(data_dir, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("AUTH_MODE", "oidc")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/me").status_code == 501
        assert c.get("/api/dev/identities").status_code == 404


def test_security_headers_and_no_store(api):
    r = api.call("GET", "/api/me")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_access_overview_matches_what_users_can_really_do(api):
    acme = api.mk_client("Acme", ["catalog", "brands"])
    viewer = api.mk_user(acme["id"], "vic@acme.com", ["viewer"])
    admin = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    off = api.mk_user(acme["id"], "off@acme.com", ["admin"])
    api.call("PATCH", "/api/users/" + off["id"], json={"disabled": True})
    rows = {r["email"]: r for r in api.call("GET", "/api/access").json()}
    assert rows["admin@local"]["is_super_admin"] and rows["admin@local"]["effective_modules"] == [
        "catalog", "generation", "brands", "unity"]
    assert rows["vic@acme.com"]["effective_modules"] == ["catalog", "brands"]
    assert rows["ana@acme.com"]["effective_modules"] == ["catalog", "brands"]
    assert rows["ana@acme.com"]["client_modules"] == ["catalog", "brands"]
    assert rows["off@acme.com"]["effective_modules"] == [] and rows["off@acme.com"]["action_count"] == 0
    assert rows["vic@acme.com"]["roles"] == ["Solo lectura"]
    me = api.call("GET", "/api/me", who=viewer["id"]).json()
    assert rows["vic@acme.com"]["action_count"] == len(me["can"])
    assert api.call("GET", "/api/access", who=admin["id"]).status_code == 403
    api.call("PATCH", "/api/clients/" + acme["id"], json={"disabled": True})
    assert {r["effective_modules"] != [] for r in api.call("GET", "/api/access").json() if r["client_id"]} == {False}


def test_foreign_origin_cannot_write_but_same_origin_can(api):
    body = {"name": "Evil"}
    assert api.call("POST", "/api/clients", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert api.call("DELETE", "/api/clients/x", headers={"Origin": "https://evil.example"}).status_code == 403
    assert api.call("POST", "/api/clients", json={"name": "Ok"}, headers={"Origin": "http://testserver"}).status_code == 201
    assert api.call("GET", "/api/me", headers={"Origin": "https://evil.example"}).status_code == 200


def test_unknown_host_is_refused(api):
    assert api.call("GET", "/api/me", headers={"Host": "attacker.example"}).status_code == 400


def test_upload_limit_is_enforced_while_reading(api, fake_blender, monkeypatch):
    from app.routers import products

    monkeypatch.setattr(products, "MAX_UPLOAD", 1024)
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    r = api.call("POST", "/api/products", who=ana, data={"name": "x", "metadata": '{"sku": "1"}'},
                 files=[("files", ("a.glb", b"x" * 2048, "model/gltf-binary"))])
    assert r.status_code == 413
    assert api.call("GET", "/api/products", who=ana).json()["products"] == []


def test_setup_checklist_tracks_what_is_connected(api, fake_blender, monkeypatch):
    from app.config import get_settings

    for k in ("UNITY_KEY_ID", "UNITY_KEY_SECRET", "MESHY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    out = api.call("GET", "/api/platform/setup").json()
    done = {s["id"]: s["done"] for s in out["steps"]}
    assert done == {"blender": True, "meshy": False, "unity": False, "client": False, "users": False, "unity_projects": False, "auth": False}
    assert out["ready"] is False
    meshy_row = next(i for i in api.call("GET", "/api/integrations").json()["items"] if i["kind"] == "meshy")
    unity_row = next(i for i in api.call("GET", "/api/integrations").json()["items"] if i["kind"] == "unity")
    api.call("PUT", "/api/integrations/" + meshy_row["id"], json={"secrets": {"api_key": "msy_AAAAAAAAAAAA"}})
    api.call("PUT", "/api/integrations/" + unity_row["id"], json={"secrets": {"key_id": "kid-123456789", "key_secret": "sec-123456789"}})
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    prj = api.projects(who=ana)["General"]["id"]
    api.call("PATCH", "/api/projects/" + prj, client_id=c["id"], json={"unity_project_id": "UP-1"})
    out = api.call("GET", "/api/platform/setup").json()
    assert {s["id"]: s["done"] for s in out["steps"]} == {"blender": True, "meshy": True, "unity": True, "client": True, "users": True, "unity_projects": True, "auth": False}
    assert out["ready"] is True
    assert api.call("GET", "/api/platform/setup", who=ana).status_code == 403
