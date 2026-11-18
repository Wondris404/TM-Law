import asyncio
import socket
from contextlib import suppress
from urllib.parse import urlsplit

import psutil

INTERVAL = 0.5
PROCESS_ERRORS = (psutil.Error, OSError)


class MemorySampler:
    """Sample resident memory of this process and a verified local Ollama listener tree."""

    def __init__(self, runtime_url: str | None):
        self.backend = psutil.Process()
        self.endpoint = urlsplit(runtime_url) if runtime_url else None
        self.listener = None
        self.peaks = {}
        self.samples = 0
        self.ollama_seen = False
        self.peak_combined_pss = None
        self.peak_system_used = None
        self.task = None
        self.stopping = asyncio.Event()

    def find_listener(self):
        if not self.endpoint:
            return None
        if self.listener and self.listener.is_running():
            return self.listener
        self.listener = None
        host = self.endpoint.hostname
        family = socket.AF_INET6 if host == "::1" else socket.AF_INET
        for process in psutil.process_iter(["name"]):
            if (process.info["name"] or "").lower() not in {"ollama", "ollama.exe"}:
                continue
            try:
                connections = process.net_connections(kind="tcp")
                if any(
                    c.status == psutil.CONN_LISTEN
                    and c.family == family
                    and c.laddr.port == self.endpoint.port
                    and c.laddr.ip in {host, "::", "0.0.0.0"}
                    for c in connections
                ):
                    self.listener = process
                    return process
            except PROCESS_ERRORS:
                continue
        return None

    def sample(self):
        self.samples += 1
        listener = self.find_listener()
        processes = [(self.backend, "backend")]
        complete_tree = False
        if listener is not None and listener.pid != self.backend.pid:
            processes.append((listener, "ollama"))
            try:
                workers = listener.children(recursive=True)
                processes.extend((p, "ollama_worker") for p in workers if p.pid != self.backend.pid)
                complete_tree = True
            except PROCESS_ERRORS:
                pass

        pss_values = []
        for process, role in processes:
            try:
                identity = (process.pid, process.create_time())
                info = process.memory_info()
                current = self.peaks.setdefault(
                    identity,
                    {
                        "role": role,
                        "pid": process.pid,
                        "peak_rss_bytes": 0,
                        "peak_private_bytes": None,
                    },
                )
                current["peak_rss_bytes"] = max(current["peak_rss_bytes"], info.rss)
                if role == "ollama":
                    self.ollama_seen = True
                full = process.memory_full_info()
                private_bytes = getattr(full, "uss", None)
                if private_bytes is not None:
                    current["peak_private_bytes"] = max(
                        current["peak_private_bytes"] or 0, private_bytes
                    )
                pss = getattr(full, "pss", None)
                if pss is not None:
                    pss_values.append(pss)
            except PROCESS_ERRORS:
                continue
        if complete_tree and len(pss_values) == len(processes):
            self.peak_combined_pss = max(self.peak_combined_pss or 0, sum(pss_values))
        with suppress(*PROCESS_ERRORS):
            memory = psutil.virtual_memory()
            self.peak_system_used = max(self.peak_system_used or 0, memory.total - memory.available)

    async def __aenter__(self):
        await asyncio.to_thread(self.sample)
        self.task = asyncio.create_task(self.poll())
        return self

    async def stop(self):
        if self.task is not None:
            # Let a running thread finish before collecting the final snapshot.
            task, self.task = self.task, None
            self.stopping.set()
            await task

    async def poll(self):
        while not self.stopping.is_set():
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=INTERVAL)
            except TimeoutError:
                await asyncio.to_thread(self.sample)

    async def __aexit__(self, *_):
        await self.stop()

    async def finish(self) -> dict:
        await self.stop()
        await asyncio.to_thread(self.sample)
        return {
            "sample_interval_seconds": INTERVAL,
            "samples": self.samples,
            "processes": list(self.peaks.values()),
            "ollama_listener_measured": self.ollama_seen,
            "combined_peak_pss_bytes": self.peak_combined_pss,
            "peak_system_used_bytes": self.peak_system_used,
        }
