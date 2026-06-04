import asyncio
import pytest
from app.hooks import HookEventBus


@pytest.mark.asyncio
async def test_emit_delivers_to_subscriber():
    bus = HookEventBus()
    q = bus.subscribe("RELIANCE")
    await bus.emit("RELIANCE", "on_pdf_fetched", {"year": 2021})
    event = q.get_nowait()
    assert event["event"] == "on_pdf_fetched"
    assert event["data"]["year"] == 2021


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = HookEventBus()
    q = bus.subscribe("TCS")
    bus.unsubscribe("TCS", q)
    await bus.emit("TCS", "test", {})
    assert q.empty()


@pytest.mark.asyncio
async def test_history_replays_for_late_subscriber():
    """Events emitted before a client connects are available via history()."""
    bus = HookEventBus()
    await bus.emit("INFY", "agent_start", {})
    await bus.emit("INFY", "on_pdf_fetched", {"year": 2021})
    await bus.emit("INFY", "pipeline_complete", {})
    # Late subscriber sees the full run via history
    history = bus.history("INFY")
    assert [e["event"] for e in history] == ["agent_start", "on_pdf_fetched", "pipeline_complete"]


@pytest.mark.asyncio
async def test_new_run_resets_history():
    """agent_start begins a fresh history (old run's events dropped)."""
    bus = HookEventBus()
    await bus.emit("TCS", "agent_start", {})
    await bus.emit("TCS", "pipeline_complete", {})
    await bus.emit("TCS", "agent_start", {})  # new run
    history = bus.history("TCS")
    assert [e["event"] for e in history] == ["agent_start"]
