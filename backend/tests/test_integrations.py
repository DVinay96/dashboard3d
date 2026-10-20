import hashlib
import hmac
import json
import re

import httpx
import pytest

from app.config import get_settings
from app.db import session_scope
from app.models import Integration
from app.services import events, integrations, meshy
from app.services import unity as unity_svc
from test_unity import BASE, FakeUnity, setup_client, sync


def by_kind(api, kind):
    return [i for i in api.call("GET", "/api/integrations").json()["items"] if i["kind"] == kind]


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(events, "RETRY_SLEEP", 0)


class Receiver:
    def __init__(self):
        self.requests = []
        self.fail = []

    def handler(self, request):
        body = request.content.decode()
        self.requests.append((str(request.url), dict(request.headers), body))
        if self.fail:
            code = self.fail.pop(0)
            if code:
                return httpx.Response(code, text="no")
        data = json.loads(body) if body else {}
        if "jsonrpc" in data:
            return self.mcp(data)
        return httpx.Response(200, json={"ok": True})

    def mcp(self, data):
        method = data["method"]
        if method == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": {"serverInfo": {"name": "agente", "version": "1.2"}}}, headers={"mcp-session-id": "S1"})
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/list":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": {"tools": [{"name": "on_event"}, {"name": "otra"}]}})
        if method == "tools/call":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": {"content": []}})
        return httpx.Response(404)

    def calls(self, kind):
        return [json.loads(b) for _, _, b in self.requests if kind in b]


@pytest.fixture
def receiver(monkeypatch):
    r = Receiver()
    monkeypatch.setattr(integrations, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(r.handler)))
    return r


def create(api, **body):
    r = api.call("POST", "/api/integrations", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_singletons_exist_and_cannot_be_deleted_or_created(api):
    kinds = [i["kind"] for i in api.call("GET", "/api/integrations").json()["items"]]
    assert kinds == ["meshy", "unity"]
    meshy_row = by_kind(api, "meshy")[0]
    assert api.call("DELETE", "/api/integrations/" + meshy_row["id"]).status_code == 400
    assert api.call("POST", "/api/integrations", json={"kind": "meshy", "name": "x"}).status_code == 400
    events_list = api.call("GET", "/api/integrations").json()["events"]
    assert {e["name"] for e in events_list} == set(integrations.EVENTS)


def test_secrets_are_encrypted_masked_and_never_returned(api, data_dir):
    row = by_kind(api, "meshy")[0]
    r = api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": "msy_SECRET_KEY_1234"}})
    assert r.status_code == 200
    out = r.json()
    assert out["secrets"]["api_key"] == {"set": True, "hint": "…1234"}
    assert "SECRET_KEY" not in json.dumps(api.call("GET", "/api/integrations").json())
    with session_scope() as db:
        raw = db.get(Integration, row["id"]).secrets_enc
    assert raw and "SECRET_KEY" not in raw
    assert oct((data_dir / "secrets.key").stat().st_mode & 0o777) == "0o600"
    assert api.call("GET", "/api/platform/settings").json()["meshy_key_set"] is True
    assert integrations.meshy_key() == "msy_SECRET_KEY_1234"


def test_blank_secret_keeps_current_and_clear_removes(api):
    row = by_kind(api, "meshy")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": "msy_AAAAAAAAAAAA"}})
    again = api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": ""}, "name": "Meshy"}).json()
    assert again["secrets"]["api_key"]["set"] is True and again["name"] == "Meshy"
    cleared = api.call("PUT", "/api/integrations/" + row["id"], json={"clear_secrets": ["api_key"]}).json()
    assert cleared["secrets"]["api_key"]["set"] is False
    assert api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"nope": "x"}}).status_code == 400


def test_integration_key_wins_over_env_and_disabled_falls_back(api, monkeypatch):
    monkeypatch.setenv("MESHY_API_KEY", "env-key")
    get_settings.cache_clear()
    assert integrations.meshy_key() == "env-key"
    row = by_kind(api, "meshy")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": "ui-key-123456"}})
    assert integrations.meshy_key() == "ui-key-123456"
    api.call("PUT", "/api/integrations/" + row["id"], json={"enabled": False})
    assert integrations.meshy_key() == "env-key"


def test_meshy_connection_test(api, monkeypatch):
    row = by_kind(api, "meshy")[0]
    assert api.call("POST", f"/api/integrations/{row['id']}/test").json()["ok"] is False
    api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": "ui-key-123456"}})
    seen = []
    monkeypatch.setattr(meshy, "request", lambda m, p, k, payload=None, timeout=90: seen.append((m, p, k)) or {"balance": 120})
    r = api.call("POST", f"/api/integrations/{row['id']}/test").json()
    assert r["ok"] is True and "120" in r["message"] and seen == [("GET", "/balance", "ui-key-123456")]
    assert by_kind(api, "meshy")[0]["last_status"] == "OK"
    monkeypatch.setattr(meshy, "request", lambda *a, **k: (_ for _ in ()).throw(meshy.MeshyError("HTTP 401")))
    r = api.call("POST", f"/api/integrations/{row['id']}/test").json()
    assert r["ok"] is False and "401" in r["message"]
    assert by_kind(api, "meshy")[0]["last_status"] == "FAILED"


def test_unity_credentials_from_the_ui(api, monkeypatch):
    for k in ("UNITY_KEY_ID", "UNITY_KEY_SECRET"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    assert unity_svc.is_configured() is False
    row = by_kind(api, "unity")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"key_id": "kid-123456789", "key_secret": "sec-123456789"}, "config": {"api_base": "https://unity.test/assets/v1/"}})
    creds = integrations.unity_credentials()
    assert creds["key_id"] == "kid-123456789" and creds["api_base"] == "https://unity.test/assets/v1" and creds["auto_sync"] is True
    s = api.call("GET", "/api/platform/settings").json()
    assert s["unity_configured"] is True and s["unity_api_base"] == "https://unity.test/assets/v1"
    api.call("PUT", "/api/integrations/" + row["id"], json={"enabled": False})
    assert unity_svc.is_configured() is False
    assert api.call("PUT", "/api/integrations/" + row["id"], json={"config": {"api_base": "ftp://x"}}).status_code == 400


def test_unity_connection_test(api, monkeypatch):
    fake = FakeUnity()
    client = unity_svc.UnityClient("a", "b", BASE, http=httpx.Client(transport=httpx.MockTransport(fake.handler)), retry_sleep=0)
    monkeypatch.setattr(unity_svc, "get_client", lambda: client)
    row = by_kind(api, "unity")[0]
    assert api.call("POST", f"/api/integrations/{row['id']}/test").json()["ok"] is True
    fake.fail["/libraries"] = [403]
    r = api.call("POST", f"/api/integrations/{row['id']}/test").json()
    assert r["ok"] is False and "HTTP 403" in r["message"] and "Contributor" in r["message"]


def test_unity_test_without_credentials(api, monkeypatch):
    for k in ("UNITY_KEY_ID", "UNITY_KEY_SECRET"):
        monkeypatch.delenv(k, raising=False)
    get_settings.cache_clear()
    row = by_kind(api, "unity")[0]
    r = api.call("POST", f"/api/integrations/{row['id']}/test").json()
    assert r["ok"] is False and "Faltan" in r["message"]


def test_webhook_and_mcp_validation(api):
    bad = [
        {"kind": "webhook", "name": "x", "config": {"url": "ftp://x"}},
        {"kind": "webhook", "name": "x", "config": {"url": "https://x", "events": ["nope"]}},
        {"kind": "mcp", "name": "x", "config": {}},
        {"kind": "webhook", "name": "x", "config": {"url": "https://x"}, "secrets": {"api_key": "y"}},
        {"kind": "mcp", "name": "", "config": {"url": "https://x"}},
    ]
    for body in bad:
        assert api.call("POST", "/api/integrations", json=body).status_code in (400, 422), body
    ok = create(api, kind="webhook", name="Agente", config={"url": "https://agent.test/hook", "events": ["product.done", "unity.synced"]}, secrets={"signing_secret": "whsec_123456789"})
    assert ok["config"]["events"] == ["product.done", "unity.synced"] and ok["secrets"]["signing_secret"]["set"] is True
    assert api.call("DELETE", "/api/integrations/" + ok["id"]).status_code == 204
    assert api.call("DELETE", "/api/integrations/" + ok["id"]).status_code == 404


def test_mcp_connection_test(api, receiver):
    mcp = create(api, kind="mcp", name="Agente MCP", config={"url": "https://mcp.test/mcp", "event_tool": "on_event", "events": ["product.done"]}, secrets={"token": "tok_123456789"})
    r = api.call("POST", f"/api/integrations/{mcp['id']}/test").json()
    assert r["ok"] is True and "agente 1.2" in r["message"] and "2" in r["message"]
    init = [h for u, h, b in receiver.requests if '"initialize"' in b][0]
    assert init["authorization"] == "Bearer tok_123456789" and "text/event-stream" in init["accept"]
    later = [h for u, h, b in receiver.requests if '"tools/list"' in b][0]
    assert later["mcp-session-id"] == "S1"
    api.call("PUT", "/api/integrations/" + mcp["id"], json={"config": {"event_tool": "inexistente"}})
    r = api.call("POST", f"/api/integrations/{mcp['id']}/test").json()
    assert r["ok"] is False and "inexistente" in r["message"]


def test_mcp_accepts_sse_replies(monkeypatch, api):
    def handler(request):
        data = json.loads(request.content)
        if data["method"] == "notifications/initialized":
            return httpx.Response(202)
        result = {"serverInfo": {"name": "sse"}} if data["method"] == "initialize" else {"tools": []}
        body = "event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": data["id"], "result": result}) + "\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(integrations, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    mcp = create(api, kind="mcp", name="SSE", config={"url": "https://mcp.test/mcp", "events": []})
    assert api.call("POST", f"/api/integrations/{mcp['id']}/test").json()["ok"] is True


def test_mcp_errors_are_reported(api, monkeypatch):
    monkeypatch.setattr(integrations, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))))
    mcp = create(api, kind="mcp", name="X", config={"url": "https://mcp.test/mcp", "events": []})
    r = api.call("POST", f"/api/integrations/{mcp['id']}/test").json()
    assert r["ok"] is False and "credenciales" in r["message"]


def test_webhook_test_sends_a_signed_ping(api, receiver):
    hook = create(api, kind="webhook", name="Hook", config={"url": "https://agent.test/hook", "events": []}, secrets={"signing_secret": "whsec_123456789"})
    assert api.call("POST", f"/api/integrations/{hook['id']}/test").json()["ok"] is True
    url, headers, body = receiver.requests[0]
    assert url == "https://agent.test/hook" and headers["x-pipeline-event"] == "ping"
    expected = "sha256=" + hmac.new(b"whsec_123456789", body.encode(), hashlib.sha256).hexdigest()
    assert headers["x-pipeline-signature"] == expected


def test_product_events_reach_subscribed_webhooks_only(api, fake_blender, receiver):
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    done = create(api, kind="webhook", name="Done", config={"url": "https://a.test/done", "events": ["product.done"]})
    create(api, kind="webhook", name="Fails", config={"url": "https://a.test/fails", "events": ["product.failed"]})
    off = create(api, kind="webhook", name="Off", config={"url": "https://a.test/off", "events": ["product.done"]}, enabled=False)
    pid = api.mk_product(ana, "Silla").json()["id"]
    urls = [u for u, _, _ in receiver.requests]
    assert urls == ["https://a.test/done"]
    body = json.loads(receiver.requests[0][2])
    assert body["event"] == "product.done" and body["client"]["slug"] == "acme"
    assert body["product"]["id"] == pid and body["product"]["status"] == "DONE" and body["product"]["created_by"] == "ana@acme.com"
    assert body["product"]["metadata"]["sku"] == "SKU-Silla" and body["product"]["projects"][0]["name"] == "General"
    row = [i for i in api.call("GET", "/api/integrations").json()["items"] if i["id"] == done["id"]][0]
    assert row["last_status"] == "OK" and "product.done" in row["last_message"]
    assert off["enabled"] is False


def test_failed_product_emits_failed_event(api, receiver):
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    create(api, kind="webhook", name="Fails", config={"url": "https://a.test/fails", "events": ["product.failed", "product.done"]})
    api.mk_product(ana, "Silla")
    events_seen = [json.loads(b)["event"] for _, _, b in receiver.requests]
    body = json.loads(receiver.requests[0][2])
    assert events_seen == ["product.failed"] and "Blender" in body["product"]["error"]


def test_delivery_retries_then_records_failure(api, fake_blender, receiver, no_sleep):
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    hook = create(api, kind="webhook", name="H", config={"url": "https://a.test/h", "events": ["product.done"]})
    receiver.fail = [503, 500]
    api.mk_product(ana, "Silla")
    assert len(receiver.requests) == 3
    assert [i for i in api.call("GET", "/api/integrations").json()["items"] if i["id"] == hook["id"]][0]["last_status"] == "OK"
    receiver.requests.clear()
    receiver.fail = [500, 500, 500]
    api.mk_product(ana, "Otra")
    assert len(receiver.requests) == 3
    row = [i for i in api.call("GET", "/api/integrations").json()["items"] if i["id"] == hook["id"]][0]
    assert row["last_status"] == "FAILED" and "HTTP 500" in row["last_message"]
    receiver.requests.clear()
    receiver.fail = [400]
    api.mk_product(ana, "Tercera")
    assert len(receiver.requests) == 1


def test_mcp_receives_events_as_tool_calls(api, fake_blender, receiver):
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    create(api, kind="mcp", name="Agente", config={"url": "https://mcp.test/mcp", "event_tool": "on_event", "events": ["product.done"]}, secrets={"token": "tok_123456789"})
    create(api, kind="mcp", name="Sin herramienta", config={"url": "https://mcp2.test/mcp", "events": ["product.done"]})
    api.mk_product(ana, "Silla")
    calls = receiver.calls("tools/call")
    assert len(calls) == 1 and calls[0]["params"]["name"] == "on_event"
    args = calls[0]["params"]["arguments"]
    assert args["event"] == "product.done" and args["payload"]["product"]["name"] == "Silla"
    assert not any("mcp2.test" in u for u, _, _ in receiver.requests)


def test_only_super_admin_manages_integrations(api):
    c = api.mk_client("Acme")
    ana = api.mk_user(c["id"], "ana@acme.com", ["admin"])["id"]
    row = by_kind(api, "meshy")[0]
    for method, path, body in (("GET", "/api/integrations", None), ("POST", "/api/integrations", {"kind": "webhook", "name": "x", "config": {"url": "https://x"}}),
                               ("PUT", "/api/integrations/" + row["id"], {"enabled": False}), ("DELETE", "/api/integrations/" + row["id"], None),
                               ("POST", f"/api/integrations/{row['id']}/test", None)):
        assert api.call(method, path, who=ana, json=body).status_code == 403, (method, path)


def test_lost_encryption_key_is_handled(api, monkeypatch, data_dir):
    row = by_kind(api, "meshy")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"secrets": {"api_key": "msy_AAAAAAAAAAAA"}})
    (data_dir / "secrets.key").write_text("A" * 43 + "=")
    out = by_kind(api, "meshy")[0]
    assert out["secrets"]["api_key"]["set"] is False
    assert integrations.meshy_key() == ""
    assert api.call("POST", f"/api/integrations/{row['id']}/test").json()["ok"] is False


def fake_unity_client(monkeypatch):
    fake = FakeUnity()
    client = unity_svc.UnityClient("k", "s", BASE, http=httpx.Client(transport=httpx.MockTransport(fake.handler)), retry_sleep=0)
    monkeypatch.setattr(unity_svc, "get_client", lambda: client)
    monkeypatch.setenv("UNITY_KEY_ID", "k")
    monkeypatch.setenv("UNITY_KEY_SECRET", "s")
    get_settings.cache_clear()
    return fake


def test_finished_products_sync_to_unity_automatically(api, fake_blender, monkeypatch, receiver):
    fake = fake_unity_client(monkeypatch)
    c, ana, prj = setup_client(api)
    create(api, kind="webhook", name="H", config={"url": "https://a.test/h", "events": ["unity.synced", "unity.failed"]})
    pid = api.mk_product(ana, "Silla").json()["id"]
    assert fake.n_assets == 1
    row = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"][0]
    assert row["status"] == "SYNCED" and row["unity_asset_id"] == "A1"
    synced = [json.loads(b) for _, _, b in receiver.requests]
    assert [e["event"] for e in synced] == ["unity.synced"]
    assert synced[0]["unity"][0]["asset_id"] == "A1" and synced[0]["unity"][0]["status"] == "SYNCED"


def test_automatic_sync_failure_emits_event_and_keeps_the_product_done(api, fake_blender, monkeypatch, receiver):
    fake = fake_unity_client(monkeypatch)
    c, ana, prj = setup_client(api)
    create(api, kind="webhook", name="H", config={"url": "https://a.test/h", "events": ["unity.failed"]})
    fake.fail["/assets"] = [403]
    pid = api.mk_product(ana, "Silla").json()["id"]
    p = api.call("GET", "/api/products/" + pid, who=ana).json()
    assert p["status"] == "DONE" and p["unity"][0]["status"] == "FAILED"
    assert json.loads(receiver.requests[0][2])["event"] == "unity.failed"


def test_automatic_sync_respects_flag_module_and_destination(api, fake_blender, monkeypatch):
    fake = fake_unity_client(monkeypatch)
    c, ana, prj = setup_client(api, ("General", "SinUnity"), {"General": "UP-1"})
    row = by_kind(api, "unity")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"config": {"auto_sync": False}})
    api.mk_product(ana, "Apagado", [prj["General"]["id"]])
    assert fake.n_assets == 0
    api.call("PUT", "/api/integrations/" + row["id"], json={"config": {"auto_sync": True}})
    api.mk_product(ana, "SinDestino", [prj["SinUnity"]["id"]])
    assert fake.n_assets == 0
    api.call("PATCH", "/api/clients/" + c["id"], json={"modules": ["catalog", "generation", "brands"]})
    api.mk_product(ana, "SinModulo", [prj["General"]["id"]])
    assert fake.n_assets == 0
    api.call("PATCH", "/api/clients/" + c["id"], json={"modules": ["catalog", "generation", "brands", "unity"]})
    api.mk_product(ana, "Listo", [prj["General"]["id"]])
    assert fake.n_assets == 1


def test_assigning_a_synced_product_to_a_new_project_links_it(api, fake_blender, monkeypatch):
    fake = fake_unity_client(monkeypatch)
    c, ana, prj = setup_client(api, ("General", "Otoño"), {"General": "UP-1", "Otoño": "UP-2"})
    pid = api.mk_product(ana, "Mesa", [prj["General"]["id"]]).json()["id"]
    assert fake.n_assets == 1
    fake.calls.clear()
    api.call("PUT", f"/api/products/{pid}/projects", who=ana, json={"project_ids": [prj["General"]["id"], prj["Otoño"]["id"]]})
    assert [(m, p) for m, p, *_ in fake.calls] == [("POST", "/projects/UP-1/assets/A1/link/projects/UP-2")]
    rows = api.call("GET", "/api/products/" + pid, who=ana).json()["unity"]
    assert {r["project_name"]: r["status"] for r in rows} == {"General": "SYNCED", "Otoño": "SYNCED"}


def test_manual_sync_still_available_when_auto_is_off(api, fake_blender, monkeypatch):
    fake = fake_unity_client(monkeypatch)
    c, ana, prj = setup_client(api)
    row = by_kind(api, "unity")[0]
    api.call("PUT", "/api/integrations/" + row["id"], json={"config": {"auto_sync": False}})
    pid = api.mk_product(ana, "Silla").json()["id"]
    assert fake.n_assets == 0
    assert sync(api, ana, pid).status_code == 202 and fake.n_assets == 1
