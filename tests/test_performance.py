import asyncio
import socket
from types import SimpleNamespace

import psutil
import pytest
from tm_law import performance


@pytest.mark.asyncio
async def test_live_backend_only_stops_polling():
    async with performance.MemorySampler(None) as sampler:
        result = await sampler.finish()
    assert result["samples"] >= 2
    assert result["processes"][0]["role"] == "backend"
    assert result["processes"][0]["peak_rss_bytes"] > 0
    assert not result["ollama_listener_measured"]
    assert result["combined_peak_pss_bytes"] is None
    count = sampler.samples
    await asyncio.sleep(0)
    assert sampler.samples == count


@pytest.mark.parametrize("supports_pss", [True, False])
def test_memory_attribution_and_pss_availability(monkeypatch, supports_pss):
    def process(pid, family, port=None, children=()):
        connection = SimpleNamespace(
            status=psutil.CONN_LISTEN,
            family=socket.AF_INET,
            laddr=SimpleNamespace(port=port, ip="127.0.0.1"),
        )
        return SimpleNamespace(
            info={"name": family},
            pid=pid,
            memory_info=lambda: SimpleNamespace(rss=1000),
            memory_full_info=lambda: SimpleNamespace(uss=400, pss=500 if supports_pss else None),
            create_time=lambda: pid,
            is_running=lambda: True,
            net_connections=lambda kind: [connection],
            children=lambda recursive: list(children),
        )

    worker = process(3, "ollama.exe")
    backend = process(1, "python.exe")
    other = process(4, "ollama.exe", 11435)
    daemon = process(2, "ollama.exe", 11434, children=(worker,))
    monkeypatch.setattr(performance.psutil, "Process", lambda: backend)
    monkeypatch.setattr(performance.psutil, "process_iter", lambda _: [other, daemon, worker])
    sampler = performance.MemorySampler("http://127.0.0.1:11434")
    sampler.sample()
    assert sampler.ollama_seen
    assert {entry["pid"]: entry["role"] for entry in sampler.peaks.values()} == {
        1: "backend",
        2: "ollama",
        3: "ollama_worker",
    }
    assert sampler.peak_combined_pss == (1500 if supports_pss else None)
