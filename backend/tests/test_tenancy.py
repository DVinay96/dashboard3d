def setup_two_clients(api):
    acme = api.mk_client("Acme")
    beta = api.mk_client("Beta")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    bob = api.mk_user(beta["id"], "bob@beta.com", ["admin"])
    return acme, beta, ana, bob


def test_no_auth_defaults_to_super_admin(api):
    me = api.call("GET", "/api/me").json()
    assert me["is_super_admin"] and me["client"] is None and me["auth_mode"] == "none"


def test_super_admin_needs_a_client_context_for_tenant_data(api):
    assert api.call("GET", "/api/products").status_code == 400
    acme = api.mk_client("Acme")
    assert api.call("GET", "/api/products", client_id=acme["id"]).status_code == 200


def test_new_client_gets_default_project_and_modules(api):
    acme = api.mk_client("Acme")
    assert acme["modules"] == ["catalog", "generation", "brands"]
    assert list(api.projects(client_id=acme["id"])) == ["General"]


def test_clients_cannot_see_each_others_data(api, fake_blender):
    acme, beta, ana, bob = setup_two_clients(api)
    pid = api.mk_product(ana["id"]).json()["id"]
    assert api.call("GET", "/api/products", who=bob["id"]).json()["products"] == []
    assert api.call("GET", "/api/products/" + pid, who=bob["id"]).status_code == 404
    assert api.call("DELETE", "/api/products/" + pid, who=bob["id"]).status_code == 404
    assert api.call("GET", "/api/products/%s/files/out/silla.glb" % pid, who=bob["id"]).status_code == 404
    assert list(api.projects(who=bob["id"])) == ["General"]
    assert api.projects(who=bob["id"])["General"]["id"] != api.projects(who=ana["id"])["General"]["id"]


def test_cannot_assign_product_to_another_clients_project(api, fake_blender):
    acme, beta, ana, bob = setup_two_clients(api)
    foreign = api.projects(who=bob["id"])["General"]["id"]
    r = api.mk_product(ana["id"], project_ids=[foreign])
    assert r.status_code == 400


def test_client_user_cannot_use_x_client_id_to_hop(api):
    acme, beta, ana, bob = setup_two_clients(api)
    me = api.call("GET", "/api/me", who=ana["id"], client_id=beta["id"]).json()
    assert me["client"]["id"] == acme["id"]


def test_client_users_cannot_manage_platform(api):
    acme, _, ana, _ = setup_two_clients(api)
    for method, path in (("GET", "/api/clients"), ("POST", "/api/clients"), ("GET", "/api/users"),
                         ("GET", "/api/roles"), ("GET", "/api/platform/settings"),
                         ("PUT", "/api/platform/settings")):
        assert api.call(method, path, who=ana["id"], json={}).status_code == 403, (method, path)


def test_disabled_module_blocks_its_actions_even_for_admin_role(api):
    acme = api.mk_client("Acme", modules=["catalog"])
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    me = api.call("GET", "/api/me", who=ana["id"]).json()
    assert "products:list" in me["can"] and "products:create" not in me["can"]
    assert api.mk_product(ana["id"]).status_code == 403
    assert api.call("GET", "/api/brands", who=ana["id"]).status_code == 403
    api.call("PATCH", "/api/clients/" + acme["id"], json={"modules": ["catalog", "brands"]})
    assert api.call("GET", "/api/brands", who=ana["id"]).status_code == 200


def test_unknown_module_rejected(api):
    assert api.call("POST", "/api/clients", json={"name": "X", "modules": ["nope"]}).status_code == 400


def test_disabled_client_locks_its_users_out(api):
    acme = api.mk_client("Acme")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    api.call("PATCH", "/api/clients/" + acme["id"], json={"disabled": True})
    assert api.call("GET", "/api/me", who=ana["id"]).status_code == 403


def test_disabled_user_is_locked_out(api):
    acme = api.mk_client("Acme")
    ana = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    api.call("PATCH", "/api/users/" + ana["id"], json={"disabled": True})
    assert api.call("GET", "/api/me", who=ana["id"]).status_code == 403


def test_viewer_reads_but_cannot_write(api, fake_blender):
    acme = api.mk_client("Acme")
    admin = api.mk_user(acme["id"], "ana@acme.com", ["admin"])
    viewer = api.mk_user(acme["id"], "vic@acme.com", ["viewer"])
    pid = api.mk_product(admin["id"]).json()["id"]
    assert api.call("GET", "/api/products", who=viewer["id"]).status_code == 200
    assert api.call("GET", "/api/products/" + pid, who=viewer["id"]).status_code == 200
    assert api.call("DELETE", "/api/products/" + pid, who=viewer["id"]).status_code == 403
    assert api.call("POST", "/api/projects", who=viewer["id"], json={"name": "X"}).status_code == 403
    assert api.mk_product(viewer["id"]).status_code == 403
    f = "/api/products/%s/files/out/silla.glb" % pid
    assert api.call("GET", f, who=viewer["id"]).status_code == 200
    assert api.call("GET", f + "?download=1", who=viewer["id"]).status_code == 403


def test_role_scoped_to_one_project(api, fake_blender):
    acme = api.mk_client("Acme")
    root = api.mk_user(acme["id"], "root@acme.com", ["admin"])
    api.call("POST", "/api/projects", who=root["id"], json={"name": "Otoño"})
    prj = api.projects(who=root["id"])
    role = api.mk_role("Solo Otoño", [{"effect": "allow", "actions": ["products:*", "projects:read"],
                                      "resources": ["project/%s" % prj["Otoño"]["id"],
                                                    "project/%s/*" % prj["Otoño"]["id"]]}], acme["id"])
    lu = api.mk_user(acme["id"], "lu@acme.com", [role["id"]])
    in_general = api.mk_product(root["id"], "G", [prj["General"]["id"]]).json()["id"]
    in_otono = api.mk_product(root["id"], "O", [prj["Otoño"]["id"]]).json()["id"]

    ids = [p["id"] for p in api.call("GET", "/api/products", who=lu["id"]).json()["products"]]
    assert ids == [in_otono]
    assert list(api.projects(who=lu["id"])) == ["Otoño"]
    assert api.call("GET", "/api/products/" + in_general, who=lu["id"]).status_code == 403
    assert api.mk_product(lu["id"], "X", [prj["General"]["id"]]).status_code == 403
    assert api.mk_product(lu["id"], "Y", [prj["Otoño"]["id"]]).status_code == 201


def test_product_in_two_projects_visible_through_either_and_deny_wins(api, fake_blender):
    acme = api.mk_client("Acme")
    root = api.mk_user(acme["id"], "root@acme.com", ["admin"])
    api.call("POST", "/api/projects", who=root["id"], json={"name": "B"})
    prj = api.projects(who=root["id"])
    a, b = prj["General"]["id"], prj["B"]["id"]
    pid = api.mk_product(root["id"], "Multi", [a, b]).json()["id"]
    only_a = api.mk_role("Solo A", [{"effect": "allow", "actions": ["products:*"], "resources": ["project/%s/*" % a]}], acme["id"])
    ua = api.mk_user(acme["id"], "a@acme.com", [only_a["id"]])
    assert api.call("GET", "/api/products/" + pid, who=ua["id"]).status_code == 200
    api.call("PUT", "/api/roles/" + only_a["id"], json={"name": "Solo A", "statements": [
        {"effect": "allow", "actions": ["products:*"], "resources": ["project/%s/*" % a]},
        {"effect": "deny", "actions": ["products:*"], "resources": ["project/%s/*" % b]}]})
    assert api.call("GET", "/api/products/" + pid, who=ua["id"]).status_code == 403
    assert api.call("GET", "/api/products", who=ua["id"]).json()["products"] == []
