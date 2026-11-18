import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest
from fastapi.testclient import TestClient
from tm_law.api import create_app
from tm_law.rag import answer
from tm_law.runtime import MODEL_ERROR, Ollama, RuntimeUnavailable, loopback_url
from tm_law.schemas import ChatInput, RuntimeOptions
from tm_law.store import Store

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


@pytest.mark.parametrize(
    ("mode", "metadata", "expected"),
    [
        ("auto", None, None),
        ("on", {"thinking": {"values": [False, True], "default": True}}, True),
        ("off", {"thinking": {"values": [False, True], "default": True}}, False),
        ("on", {"thinking": {"values": ["low", "medium", "high"], "default": "medium"}}, "medium"),
        ("off", {"thinking": {"values": [False]}}, False),
        ("off", {"capabilities": ["thinking"], "details": {"family": "qwen35"}}, False),
    ],
)
@pytest.mark.asyncio
async def test_reasoning_controls(mode, metadata, expected):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "model:latest", "digest": "hash"}]}
            )
        if request.url.path == "/api/show":
            assert json.loads(request.content) == {"model": "model:latest"}
            return httpx.Response(200, json=metadata)
        request_body = json.loads(request.content)
        assert request_body["model"] == "model:latest"
        if expected is None:
            assert "think" not in request_body
        else:
            assert request_body["think"] == expected
            assert type(request_body["think"]) is type(expected)
        return httpx.Response(200, text='{"message":{"content":"answer"},"done":true}\n')

    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(handler))
    chunks = [chunk async for chunk in runtime.stream([], RuntimeOptions(reasoning=mode))]
    assert ("/api/show" in paths) == (mode != "auto")
    assert chunks[0].model_digest == "hash" and chunks[0].applied_think == expected


@pytest.mark.parametrize(
    ("mode", "metadata"),
    [
        ("off", {"thinking": {"values": ["low", "medium"]}}),
        ("on", {"thinking": {"values": [False]}}),
        ("on", {"capabilities": ["completion"]}),
        ("off", {"capabilities": ["thinking"], "details": {"family": "gptoss"}}),
    ],
)
@pytest.mark.asyncio
async def test_unsupported_controls_do_not_generate(mode, metadata):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model"}]})
        assert request.url.path == "/api/show"
        return httpx.Response(200, json=metadata)

    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(handler))
    with pytest.raises(RuntimeUnavailable, match="Vyberte Auto"):
        _ = [item async for item in runtime.stream([], RuntimeOptions(reasoning=mode))]


def test_thinking_is_never_published_or_validated(tmp_path):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model"}]})
        lines = [
            {"message": {"thinking": "PRIVATE [[secret/id]]"}},
            {"message": {"content": "Číslo ß<th"}},
            {"message": {"content": "ink>INTERNAL [[secret/inline]]</th"}},
            {"message": {"content": "ink> odpoveď [[fake/ref]]"}},
            {"done": True, "done_reason": "length", "eval_count": 12, "eval_duration": 600000000},
        ]
        return httpx.Response(200, text="\n".join(map(json.dumps, lines)) + "\n")

    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(handler))
    with TestClient(create_app(tmp_path, runtime), base_url="http://localhost") as client:
        response = client.post("/api/chat", json={"question": "Test odpovede."})
    assert "PRIVATE" not in response.text and "INTERNAL" not in response.text
    assert "secret/" not in response.text
    events = [json.loads(line) for line in response.iter_lines()]
    assert events[1] == {"type": "thinking"}
    done = events[-1]
    assert done["answer"] == "Číslo ß odpoveď [neoverený odkaz]"
    assert done["cited_ids"] == done["rejected"] == ["fake/ref"]
    assert done["verified_ids"] == []
    assert done["metrics"]["generated_tokens"] == 12
    assert done["metrics"]["tokens_per_second"] == 20
    assert done["metrics"]["done_reason"] == "length"
    assert done["metrics"]["first_token_seconds"] <= done["metrics"]["first_answer_token_seconds"]


@pytest.mark.asyncio
async def test_cancelled_answer_closes_ollama_stream(tmp_path):
    paused = asyncio.Event()
    closed = asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"message":{"thinking":"private"}}\n'
            paused.set()
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model"}]})
        return httpx.Response(200, stream=SlowStream())

    store = Store(tmp_path)
    store.initialize()
    runtime = Ollama("http://127.0.0.1", "model", httpx.MockTransport(handler))
    stream = answer(store, runtime, ChatInput(question="Test cancellation"), None)
    assert (await anext(stream))["type"] == "start"
    assert (await anext(stream))["type"] == "thinking"
    task = asyncio.create_task(anext(stream))
    await asyncio.wait_for(paused.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


def test_models_show_quantization_and_request_cpu(tmp_path):
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "local/tm-law-4b:q4",
                            "digest": "example",
                            "size": 500,
                            "details": {
                                "format": "gguf",
                                "family": "qwen35",
                                "quantization_level": "Q4_K_M",
                            },
                        }
                    ]
                },
            )
        payload = json.loads(request.content)
        assert payload["options"]["num_gpu"] == 0
        return httpx.Response(200, text='{"done":true,"message":{"content":"Odpoveď"}}\n')

    runtime = Ollama("http://127.0.0.1:11434", "local/tm-law-4b:q4", httpx.MockTransport(handler))
    with TestClient(create_app(tmp_path, runtime), base_url="http://localhost") as client:
        catalog = client.get("/api/models").json()
        metadata = catalog["metadata"]["local/tm-law-4b:q4"]
        assert metadata["quantization_level"] == "Q4_K_M" and metadata["disk_size_bytes"] == 500
        assert metadata["experimental"] is True
        response = client.post(
            "/api/chat", json={"question": "Test CPU", "options": {"device": "cpu"}}
        )
        assert json.loads(response.text.splitlines()[-1])["model_metadata"] == metadata
