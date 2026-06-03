import asyncio
from datetime import datetime, timezone
from typing import Dict, List


class HookEventBus:
    def __init__(self):
        self._subs: Dict[str, List[asyncio.Queue]] = {}

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

    async def emit(self, job_id: str, event: str, data: dict):
        payload = {
            "event": event,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        for q in self._subs.get(job_id, []):
            await q.put(payload)


bus = HookEventBus()
