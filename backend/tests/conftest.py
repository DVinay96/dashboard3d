import json
import stat

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PIPELINE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PIPELINE_SKIP_DOTENV", "1")
    monkeypatch.setenv("JOB_WORKERS", "0")
    monkeypatch.setenv("MESHY_API_KEY", "")
    monkeypatch.setenv("POLL_SECONDS", "0")
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BLENDER_PATH", raising=False)
    get_settings.cache_clear()
    yield tmp_path / "data"
    get_settings.cache_clear()


@pytest.fixture
def api(data_dir):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield Api(c)


class Api:

    def __init__(self, client):
        self.c = client

    def call(self, method, path, who=None, client_id=None, **kw):
        headers = dict(kw.pop("headers", {}))
        if who:
            headers["X-Act-As"] = who
        if client_id:
            headers["X-Client-Id"] = client_id
        return self.c.request(method, path, headers=headers, **kw)

    def mk_client(self, name, modules=None):
        body = {"name": name}
        if modules is not None:
            body["modules"] = modules
        r = self.call("POST", "/api/clients", json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def mk_user(self, client_id, email, roles=(), **kw):
        r = self.call("POST", "/api/users", json={"email": email, "client_id": client_id, "role_ids": list(roles), **kw})
        assert r.status_code == 201, r.text
        return r.json()

    def mk_role(self, name, statements, client_id=None):
        r = self.call("POST", "/api/roles", json={"name": name, "statements": statements, "client_id": client_id})
        assert r.status_code == 201, r.text
        return r.json()

    def projects(self, who=None, client_id=None):
        r = self.call("GET", "/api/projects", who=who, client_id=client_id)
        assert r.status_code == 200, r.text
        return {p["name"]: p for p in r.json()}

    def mk_product(self, who, name="Silla", project_ids=None, client_id=None, **form):
        data = {"name": name, "metadata": json.dumps({"sku": "SKU-" + name}), **form}
        if project_ids is not None:
            data["project_ids"] = json.dumps(project_ids)
        return self.call("POST", "/api/products", who=who, client_id=client_id, data=data,
                         files=[("files", ("silla.glb", b"glTF-fake", "model/gltf-binary"))])


@pytest.fixture
def fake_blender(tmp_path, api):
    script = tmp_path / "fake_blender.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        "a = json.loads(sys.argv[-1])\n"
        "out, qa = pathlib.Path(a['out_dir']), pathlib.Path(a['qa_dir'])\n"
        "out.mkdir(parents=True, exist_ok=True); qa.mkdir(parents=True, exist_ok=True)\n"
        "(out / (a['slug'] + '.glb')).write_bytes(b'glb')\n"
        "(qa / 'metrics.json').write_text(json.dumps({'checks': [{'id': 'scale', 'level': 'pass'}],"
        " 'exported': {'glb': a['slug'] + '.glb'}, 'summary': {'pass': 1, 'warn': 0, 'fail': 0}}))\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    r = api.call("PUT", "/api/platform/settings", json={"blender_path": str(script)})
    assert r.status_code == 200 and r.json()["blender_ok"]
    return script
