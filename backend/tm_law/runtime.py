import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from .schemas import RuntimeOptions

MODEL_ERROR = "Model nie je nainštalovaný v Ollame. Najprv ho stiahnite cez ollama pull."


class RuntimeUnavailable(Exception):
    pass


@dataclass
class Chunk:
    text: str = ""
    eval_count: int | None = None
    eval_duration_ns: int | None = None


class ModelRuntime(Protocol):
    simulated: bool
    default_model: str

    async def models(self) -> list[str]: ...

    def stream(self, messages: list[dict], options: RuntimeOptions) -> AsyncIterator[Chunk]: ...


def loopback_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Adresa Ollamy musí byť lokálna HTTP adresa bez cesty.")
    host = "[::1]" if parts.hostname == "::1" else "127.0.0.1"
    return f"http://{host}:{parts.port or 11434}"


class Ollama:
    simulated = False

    def __init__(self, url: str, model: str, transport=None):
        self.url = loopback_url(url)
        self.default_model = model
        self.transport = transport

    def client(self):
        return httpx.AsyncClient(
            base_url=self.url,
            timeout=httpx.Timeout(120, connect=3),
            trust_env=False,
            follow_redirects=False,
            transport=self.transport,
        )

    async def models(self) -> list[str]:
        try:
            async with self.client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                return [
                    item["name"]
                    for item in response.json()["models"]
                    if not item["name"].casefold().endswith((":cloud", "-cloud"))
                    and not item.get("remote_model")
                    and not item.get("remote_host")
                ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeUnavailable("Ollama neodpovedá. Spustite lokálny server Ollama.") from exc

    async def stream(self, messages: list[dict], options: RuntimeOptions) -> AsyncIterator[Chunk]:
        model = options.model or self.default_model
        installed = await self.models()
        if model not in installed and f"{model}:latest" not in installed:
            raise RuntimeUnavailable(MODEL_ERROR)
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {
                "num_ctx": options.context_window,
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            },
        }
        try:
            async with (
                self.client() as client,
                client.stream("POST", "/api/chat", json=payload) as r,
            ):
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("error"):
                        raise RuntimeUnavailable("Ollama nedokončila generovanie.")
                    piece = row.get("message", {}).get("content", "")
                    if not isinstance(piece, str):
                        raise ValueError("Invalid message content")
                    if piece:
                        yield Chunk(text=piece)
                    if row.get("done") is True:
                        yield Chunk(
                            eval_count=row.get("eval_count"),
                            eval_duration_ns=row.get("eval_duration"),
                        )
                        return
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeUnavailable("Ollama nedokončila generovanie.") from exc
        raise RuntimeUnavailable("Ollama ukončila odpoveď bez potvrdenia dokončenia.")


class MockRuntime:
    simulated = True
    default_model = "tm-law-mock"

    async def models(self) -> list[str]:
        return [self.default_model]

    async def stream(self, messages: list[dict], options: RuntimeOptions) -> AsyncIterator[Chunk]:
        if options.model and options.model != self.default_model:
            raise RuntimeUnavailable("V testovacom režime je dostupný iba tm-law-mock.")
        evidence = json.loads(messages[-1]["content"])
        refs = evidence["sources"]
        yield Chunk("Testovacia odpoveď · simulácia. ")
        if refs:
            yield Chunk(f"Lokálny index našiel zdroj [[{refs[0]['id']}]].")
        else:
            yield Chunk("K otázke sa nenašiel právny zdroj.")
        if evidence.get("document"):
            yield Chunk(" Kontext obsahoval vybraný súkromný dokument.")
