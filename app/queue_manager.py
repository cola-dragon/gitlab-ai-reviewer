from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable

from app.models import ReviewJob

logger = logging.getLogger(__name__)


class ReviewQueueManager:
    def __init__(self, worker: Callable[[ReviewJob], Awaitable[None]]):
        self._worker = worker
        self._queue: deque[ReviewJob] = deque()
        self._running_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    async def enqueue(self, job: ReviewJob) -> str:
        async with self._lock:
            if self._running_task is None or self._running_task.done():
                self._running_task = asyncio.create_task(self._run_job(job))
                return 'running'

            self._queue.append(job)
            return 'queued'

    async def _run_job(self, job: ReviewJob) -> None:
        current = job
        while True:
            try:
                await self._worker(current)
            except Exception as exc:  # pragma: no cover
                logger.exception('review worker crashed for job %s: %s', current.job_id, exc)
            async with self._lock:
                if not self._queue:
                    self._running_task = None
                    return
                current = self._queue.popleft()
