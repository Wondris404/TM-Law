import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import aclosing, asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .extract import MAX_UPLOAD
from .rag import answer
from .runtime import MockRuntime, ModelRuntime, Ollama, RuntimeUnavailable
from .schemas import ChatInput, Kind, LegalVersion
from .store import Store

LOOPBACK_HOST = re.compile(r"^(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?$")
BUILD = Path(__file__).resolve().parents[2] / "frontend" / "dist"
DEFAULT_MODEL = "abliterant/qwen3.5-rana:9b"


def create_app(directory: Path | None = None, runtime: ModelRuntime | None = None) -> FastAPI:
    directory = directory or Path(os.getenv("TM_LAW_DATA_DIR", ".tm-law")).expanduser()
    store = Store(directory)
    if runtime is None:
        adapter = os.getenv("TM_LAW_ADAPTER", "ollama")
        if adapter == "mock":
            runtime = MockRuntime()
        elif adapter == "ollama":
            runtime = Ollama(
                os.getenv("TM_LAW_OLLAMA_URL", "http://127.0.0.1:11434"),
                os.getenv("TM_LAW_MODEL", DEFAULT_MODEL),
            )
        else:
            raise ValueError("TM_LAW_ADAPTER must be ollama or mock")

    @asynccontextmanager
    async def lifespan(_app):
        store.initialize()
        yield

    app = FastAPI(title="TM-Law", version="0.1.1", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        origin = request.headers.get("origin")
        if (
            not LOOPBACK_HOST.fullmatch(host)
            or origin is not None
            and origin != f"http://{host}"
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Rozhranie je dostupné iba lokálne."}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            length = request.headers.get("content-length", "")
            if not length.isascii() or not length.isdecimal() or len(length) > 10:
                return JSONResponse({"detail": "Vyžaduje sa veľkosť požiadavky."}, status_code=411)
            is_upload = request.url.path == "/api/documents"
            expected = "multipart/form-data" if is_upload else "application/json"
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != expected:
                return JSONResponse({"detail": "Nepodporovaný typ požiadavky."}, status_code=415)
            limit = MAX_UPLOAD + 64 * 1024 if is_upload else 5 * 1024 * 1024
            if int(length) > limit:
                return JSONResponse({"detail": "Požiadavka prekračuje limit."}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": app.version, "simulated": runtime.simulated}

    @app.get("/api/settings")
    def settings():
        return {
            "version": app.version,
            "simulated": runtime.simulated,
            "default_model": runtime.default_model,
            "language": "sk",
            "runtime_url": runtime.url if isinstance(runtime, Ollama) else None,
            "data_directory": str(store.directory.resolve()),
            "peak_ram_bytes": None,
        }

    @app.get("/api/models")
    async def models():
        try:
            return {"models": await runtime.models(), "simulated": runtime.simulated}
        except RuntimeUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/search")
    def search(
        q: Annotated[str, Query(max_length=400)] = "",
        kind: Kind | None = None,
        as_of: date | None = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 15,
    ):
        hits = store.search(q, kind=kind, as_of=as_of, limit=limit)
        note = None
        if as_of:
            note = (
                "Pre zadaný dátum sa nenašlo doložené znenie zodpovedajúce dopytu."
                if not hits
                else "Dátumový filter vychádza z metadát importu."
            )
        return {"hits": hits, "note": note}

    @app.post("/api/legal/import")
    def import_legal(version: LegalVersion):
        try:
            digest, created = store.import_version(version)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return JSONResponse(
            {"version_id": version.version_id, "sha256": digest, "created": created},
            status_code=201 if created else 200,
        )

    @app.get("/api/documents")
    def documents():
        return {"documents": store.list_documents()}

    @app.post("/api/documents", status_code=201)
    async def upload(file: Annotated[UploadFile, File()]):
        data = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if not data or len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Súbor musí mať od 1 bajtu do 8 MiB.")
        name = re.split(r"[/\\]", file.filename or "")[-1]
        name = "".join(char for char in name if char.isprintable()).strip()
        suffix = Path(name).suffix.lower()
        if suffix not in {".txt", ".pdf", ".docx"}:
            raise HTTPException(415, "Podporované sú TXT, PDF a DOCX.")
        try:
            result = await run_in_threadpool(
                subprocess.run,
                [sys.executable, str(Path(__file__).with_name("extract.py")), suffix],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(422, "Spracovanie dokumentu prekročilo časový limit.") from exc
        if result.returncode:
            message = result.stdout.decode("utf-8") if result.returncode == 2 else ""
            raise HTTPException(422, message or "Dokument sa nepodarilo bezpečne spracovať.")
        text = result.stdout.decode("utf-8")
        document_id = uuid4().hex
        display_name = name[:200]
        await run_in_threadpool(
            store.save_document, document_id, display_name, text, hashlib.sha256(data).hexdigest()
        )
        return {"id": document_id, "name": display_name}

    @app.delete("/api/documents/{document_id}")
    def delete(document_id: str):
        if not store.delete_document(document_id):
            raise HTTPException(404, "Dokument neexistuje.")
        return {"deleted": True}

    @app.post("/api/chat")
    async def chat(request: ChatInput):
        document = None
        if request.document_id:
            document = await run_in_threadpool(store.get_document, request.document_id)
            if document is None:
                raise HTTPException(404, "Dokument neexistuje.")

        async def stream():
            async with aclosing(answer(store, runtime, request, document)) as events:
                async for event in events:
                    yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    if BUILD.is_dir():
        app.mount("/", StaticFiles(directory=BUILD, html=True), name="frontend")
    return app


app = create_app()
