import json

import httpx

PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    pass


class McpClient:
    def __init__(self, url: str, token: str = "", http: httpx.Client | None = None):
        self.url = url
        self._token = token
        self._http = http or httpx.Client(timeout=httpx.Timeout(20.0))
        self._session: str | None = None
        self._id = 0
        self._ready = False

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._token:
            h["Authorization"] = "Bearer " + self._token
        if self._session:
            h["Mcp-Session-Id"] = self._session
        return h

    @staticmethod
    def _parse(response: httpx.Response) -> dict:
        ctype = response.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        return json.loads(payload)
            raise McpError("El servidor MCP respondió un stream vacío.")
        return response.json()

    def _post(self, body: dict, expect_reply: bool = True) -> dict:
        try:
            r = self._http.post(self.url, json=body, headers=self._headers())
        except httpx.HTTPError as e:
            raise McpError("No se pudo conectar con el servidor MCP: %s" % e)
        if r.status_code in (401, 403):
            raise McpError("El servidor MCP rechazó las credenciales (HTTP %d)." % r.status_code)
        if r.status_code >= 400:
            raise McpError("El servidor MCP respondió HTTP %d: %s" % (r.status_code, r.text[:200]))
        if "mcp-session-id" in r.headers:
            self._session = r.headers["mcp-session-id"]
        if not expect_reply or r.status_code == 202 or not r.content:
            return {}
        try:
            data = self._parse(r)
        except ValueError:
            raise McpError("Respuesta invalida del servidor MCP.")
        if "error" in data:
            raise McpError("Error MCP: %s" % (data["error"].get("message") or data["error"]))
        return data.get("result", {})

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        return self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})

    def initialize(self) -> dict:
        result = self._request(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "pipeline3d", "version": "2.0"}},
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_reply=False)
        self._ready = True
        return result

    def _ensure(self) -> None:
        if not self._ready:
            self.initialize()

    def list_tools(self) -> list[dict]:
        self._ensure()
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        self._ensure()
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise McpError("La herramienta '%s' devolvió un error." % name)
        return result
