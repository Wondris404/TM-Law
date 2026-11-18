import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest
from fastapi.testclient import TestClient
from tm_law.api import create_app
from tm_law.runtime import MODEL_ERROR, Ollama, RuntimeUnavailable, loopback_url
from tm_law.schemas import RuntimeOptions

from .test_mvp import fixture as legal_fixture


def test_api_ollama_http_contract_excludes_fixtures(tmp_path):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3.5:4b"
        assert payload["options"]["num_ctx"] == 4096 and payload["stream"]
        assert json.loads(payload["messages"][-1]["content"])["sources"] == []
        return httpx.Response(
            200,
            text='{"message":{"content":"Skúška [[fake/id]]"},"done":false}\n'
            '{"done":true,"eval_count":10,"eval_duration":2000000000}\n',
        )

    runtime = Ollama("http://localhost:11434", "qwen3.5:4b", httpx.MockTransport(handler))
    with TestClient(create_app(tmp_path, runtime), base_url="http://localhost") as client:
        client.post("/api/legal/import", json=legal_fixture(2022))
        response = client.post("/api/chat", json={"question": "evidencia", "as_of": "2022-06-01"})
        events = [json.loads(line) for line in response.iter_lines()]
        assert events[0]["simulated"] is False
        assert events[-1]["rejected"] == ["fake/id"]
        assert events[-1]["metrics"]["tokens_per_second"] == 5
        missing = client.post(
            "/api/chat", json={"question": "evidencia", "options": {"model": "absent"}}
        )
        assert json.loads(missing.text.splitlines()[-1])["message"] == MODEL_ERROR


@pytest.mark.asyncio
async def test_unavailable_and_incomplete_backend():
    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(offline))
    with pytest.raises(RuntimeUnavailable, match="neodpovedá"):
        await runtime.models()

    def incomplete(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model"}]})
        return httpx.Response(200, text='{"message":{"content":"partial"}}\n')

    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(incomplete))
    with pytest.raises(RuntimeUnavailable, match="bez potvrdenia"):
        async for _ in runtime.stream([], RuntimeOptions()):
            pass


@pytest.mark.parametrize(
    "address",
    [
        "https://example.com",
        "http://localhost@example.com",
        "http://localhost/api",
        "http://127.1",
        "http://169.254.169.254",
        "http://localhost?forward=1",
    ],
)
def test_remote_and_ambiguous_runtime_addresses_are_rejected(address):
    with pytest.raises(ValueError):
        loopback_url(address)


@pytest.mark.ollama
@pytest.mark.asyncio
async def test_real_local_ollama():
    model = os.getenv("TM_LAW_TEST_OLLAMA_MODEL")
    if not model:
        pytest.skip("TM_LAW_TEST_OLLAMA_MODEL is unset")
    runtime = Ollama(os.getenv("TM_LAW_OLLAMA_URL", "http://127.0.0.1:11434"), model)
    chunks = [
        item
        async for item in runtime.stream(
            [{"role": "user", "content": "Odpovedz jedným slovom: Koľko je 2 + 2?"}],
            RuntimeOptions(context_window=2048, max_tokens=64),
        )
    ]
    assert "".join(item.text for item in chunks).strip()


class LocalOllamaHandler(BaseHTTPRequestHandler):
    def write_response(self, content, content_type):
        body = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/api/tags":
            self.send_error(404)
            return
        self.write_response(
            json.dumps(
                {
                    "models": [
                        {"name": "test-local"},
                        {"name": "test:cloud"},
                        {"name": "remote", "remote_host": "https://example.com"},
                    ]
                }
            ),
            "application/json",
        )

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if payload["model"] != "test-local" or not payload["stream"]:
            self.send_error(400)
            return
        self.write_response(
            '{"message":{"content":"Lokálna sieťová skúška."},"done":false}\n{"done":true}\n',
            "application/x-ndjson",
        )


@pytest.mark.asyncio
async def test_ollama_over_local_http():
    with ThreadingHTTPServer(("127.0.0.1", 0), LocalOllamaHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            runtime = Ollama(f"http://127.0.0.1:{server.server_port}", "test-local")
            assert await runtime.models() == ["test-local"]
            messages = [{"role": "user", "content": "Test stream"}]
            chunks = [item async for item in runtime.stream(messages, RuntimeOptions())]
            assert "".join(item.text for item in chunks) == "Lokálna sieťová skúška."
        finally:
            server.shutdown()
            thread.join(timeout=2)
