import asyncio

import pytest

from app.models import ReviewJob, TriggerType
from app.queue_manager import ReviewQueueManager


@pytest.mark.asyncio
async def test_queue_continues_after_worker_exception():
    started = []

    async def worker(job: ReviewJob):
        started.append(job.job_id)
        if job.job_id == 'job-1':
            raise RuntimeError('boom')

    manager = ReviewQueueManager(worker=worker)

    await manager.enqueue(ReviewJob(job_id='job-1', project_id=1, mr_iid=1, sha='a', trigger_type=TriggerType.AUTO))
    await manager.enqueue(ReviewJob(job_id='job-2', project_id=1, mr_iid=2, sha='b', trigger_type=TriggerType.AUTO))

    await asyncio.sleep(0.05)

    assert started == ['job-1', 'job-2']
