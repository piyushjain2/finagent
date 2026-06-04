import asyncio
from datetime import datetime, timezone
from typing import Dict, List

MAX_HISTORY = 300


class HookEventBus:
    """
    Async pub/sub with per-job event history.
    History lets SSE clients that connect late (or reconnect after a page
    refresh) replay everything that already happened — fixes the race where
    a fast, fully-cached pipeline finishes before the browser starts listening.
    """

    def __init__(self):
        self._subs: Dict[str, List[asyncio.Queue]] = {}
        self._history: Dict[str, List[dict]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        if job_id in self._subs:
            try:
                self._subs[job_id].remove(q)
            except ValueError:
                pass

    def history(self, job_id: str) -> List[dict]:
        """Snapshot of all events emitted for this job (current run)."""
        return list(self._history.get(job_id, []))

    async def emit(self, job_id: str, event: str, data: dict):
        payload = {
            "event": event,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        # A new run starts a fresh history
        if event == "agent_start":
            self._history[job_id] = []
        self._history.setdefault(job_id, []).append(payload)
        if len(self._history[job_id]) > MAX_HISTORY:
            self._history[job_id] = self._history[job_id][-MAX_HISTORY:]

        for q in self._subs.get(job_id, []):
            await q.put(payload)


bus = HookEventBus()
