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
