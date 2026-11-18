import json
import re
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
    prompt_eval_count: int | None = None
    load_duration_ns: int | None = None
    runtime_duration_ns: int | None = None
    done_reason: str | None = None
    thinking: bool = False
    model_digest: str | None = None
    model_metadata: dict | None = None
    applied_think: bool | str | None = None


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

    def __init__(self, url: str, model: str, transport=None, *, keep_alive: int | None = None):
        self.url = loopback_url(url)
        self.default_model = model
        self.transport = transport
        self.keep_alive = keep_alive

    def client(self):
        return httpx.AsyncClient(
            base_url=self.url,
            timeout=httpx.Timeout(120, connect=3),
            trust_env=False,
            follow_redirects=False,
            transport=self.transport,
        )

    async def catalog(self) -> dict[str, dict]:
        try:
            async with self.client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                models = response.json()["models"]
            return {
                item["name"]: catalog_entry(item)
                for item in models
                if not item["name"].casefold().endswith((":cloud", "-cloud"))
                and not item.get("remote_model")
                and not item.get("remote_host")
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise RuntimeUnavailable("Ollama neodpovedá. Spustite lokálny server Ollama.") from exc

    async def models(self) -> list[str]:
        return list(await self.catalog())

    async def thinking_control(self, model: str, mode: str) -> bool | str | None:
        if mode == "auto":
            return None
        try:
            async with self.client() as client:
                response = await client.post("/api/show", json={"model": model})
                response.raise_for_status()
                metadata = response.json()
            if not isinstance(metadata, dict):
                raise ValueError("Invalid model metadata")
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeUnavailable(
                "Ollama nevie overiť režim uvažovania. Aktualizujte ju alebo vyberte Auto."
            ) from exc

        thinking = metadata.get("thinking")
        values = thinking.get("values") if isinstance(thinking, dict) else None
        if isinstance(values, list):
            if mode == "off" and any(value is False for value in values):
                return False
            if mode == "on":
                if any(value is True for value in values):
                    return True
                named = [value for value in values if isinstance(value, str) and value]
                if named:
                    default = thinking.get("default")
                    return default if default in named else named[0]
        elif "thinking" in (metadata.get("capabilities") or []):
            # Older versions declare the capability without describing accepted controls.
            details = metadata.get("details") or {}
            family = details.get("family", "") if isinstance(details, dict) else ""
            if family in {"qwen3", "qwen3moe", "qwen35", "qwen35moe"}:
                return mode == "on"
            if family == "gptoss" and mode == "on":
                return "medium"
        raise RuntimeUnavailable(
            "Model nepotvrdzuje podporu zvoleného režimu uvažovania. Vyberte Auto."
        )

    async def stream(self, messages: list[dict], options: RuntimeOptions) -> AsyncIterator[Chunk]:
        model = options.model or self.default_model
        installed = await self.catalog()
        resolved = model if model in installed else f"{model}:latest"
        if resolved not in installed:
            raise RuntimeUnavailable(MODEL_ERROR)
        think = await self.thinking_control(resolved, options.reasoning)
        payload = {
            "model": resolved,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": options.context_window,
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            },
        }
        if options.device == "cpu":
            payload["options"]["num_gpu"] = 0
        if options.seed is not None:
            payload["options"]["seed"] = options.seed
        if think is not None:
            payload["think"] = think
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        metadata = installed[resolved]
        yield Chunk(model_digest=metadata["digest"], model_metadata=metadata, applied_think=think)
        visible = VisibleText()
        try:
            async with (
                self.client() as client,
                client.stream("POST", "/api/chat", json=payload) as r,
            ):
                if r.status_code == 400 and think is not None:
                    raise RuntimeUnavailable(
                        "Ollama odmietla zvolený režim uvažovania. Vyberte Auto."
                    )
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("error"):
                        raise RuntimeUnavailable("Ollama nedokončila generovanie.")
                    message = row.get("message", {})
                    piece = message.get("content", "")
                    if not isinstance(piece, str):
                        raise ValueError("Invalid message content")
                    done = row.get("done") is True
                    text, inline_thinking = visible.feed(piece, final=done)
                    has_thinking = bool(message.get("thinking")) or inline_thinking
                    if text or has_thinking:
                        yield Chunk(text=text, thinking=has_thinking)
                    if done:
                        yield Chunk(
                            eval_count=reported_count(row, "eval_count"),
                            eval_duration_ns=reported_count(row, "eval_duration"),
                            prompt_eval_count=reported_count(row, "prompt_eval_count"),
                            load_duration_ns=reported_count(row, "load_duration"),
                            runtime_duration_ns=reported_count(row, "total_duration"),
                            done_reason=row.get("done_reason")
                            if isinstance(row.get("done_reason"), str)
                            else None,
                        )
                        return
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeUnavailable("Ollama nedokončila generovanie.") from exc
        raise RuntimeUnavailable("Ollama ukončila odpoveď bez potvrdenia dokončenia.")


def catalog_entry(item: dict) -> dict:
    details = item.get("details")
    if not isinstance(details, dict):
        details = {}

    def label_value(values, key):
        value = values.get(key)
        return value if isinstance(value, str) and 0 < len(value) <= 240 else None

    return {
        "tag": item["name"],
        "digest": label_value(item, "digest"),
        "format": label_value(details, "format"),
        "family": label_value(details, "family"),
        "parameter_size": label_value(details, "parameter_size"),
        "quantization_level": label_value(details, "quantization_level"),
        "disk_size_bytes": reported_count(item, "size"),
        "experimental": item["name"].rsplit("/", 1)[-1].casefold().startswith("tm-law"),
    }


def reported_count(row: dict, key: str) -> int | None:
    value = row.get(key)
    return value if type(value) is int and value >= 0 else None


class VisibleText:
    """Discard legacy <think> blocks even when tags are split across chunks."""

    def __init__(self):
        self.inside = False
        self.pending = ""

    def feed(self, piece: str, *, final: bool) -> tuple[str, bool]:
        pending = self.pending + piece
        self.pending = ""
        output = []
        thinking = self.inside and bool(pending)
        while pending:
            marker = "</think>" if self.inside else "<think>"
            match = re.search(marker, pending, re.IGNORECASE)
            if match:
                if not self.inside:
                    output.append(pending[: match.start()])
                pending = pending[match.end() :]
                self.inside = not self.inside
                thinking |= self.inside
                continue
            for size in range(min(len(marker) - 1, len(pending)), 0, -1):
                if marker.startswith(pending[-size:].casefold()):
                    self.pending = pending[-size:]
                    pending = pending[:-size]
                    break
            if not self.inside:
                output.append(pending)
                if final:
                    output.append(self.pending)
            break
        return "".join(output), thinking


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
