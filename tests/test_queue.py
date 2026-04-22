import asyncio

import pytest

from app.models import ReviewJob, TriggerType
from app.queue_manager import ReviewQueueManager


@pytest.mark.asyncio
async def test_enqueue_runs_first_job_immediately_and_second_job_waits():
    started = []
    allow_finish = asyncio.Event()

    async def worker(job: ReviewJob):
        started.append(job.job_id)
        if job.job_id == 'job-1':
            await allow_finish.wait()

    manager = ReviewQueueManager(worker=worker)

    first_state = await manager.enqueue(ReviewJob(job_id='job-1', project_id=1, mr_iid=1, sha='a', trigger_type=TriggerType.AUTO))
    second_state = await manager.enqueue(ReviewJob(job_id='job-2', project_id=1, mr_iid=2, sha='b', trigger_type=TriggerType.MANUAL))

    await asyncio.sleep(0.05)
    assert first_state == 'running'
    assert second_state == 'queued'
    assert started == ['job-1']

    allow_finish.set()
    await asyncio.sleep(0.05)
    assert started == ['job-1', 'job-2']


@pytest.mark.asyncio
async def test_queue_depth_counts_waiting_jobs_only():
    block = asyncio.Event()

    async def worker(job: ReviewJob):
        await block.wait()

    manager = ReviewQueueManager(worker=worker)
    await manager.enqueue(ReviewJob(job_id='job-1', project_id=1, mr_iid=1, sha='a', trigger_type=TriggerType.AUTO))
    await manager.enqueue(ReviewJob(job_id='job-2', project_id=1, mr_iid=2, sha='b', trigger_type=TriggerType.AUTO))
    await manager.enqueue(ReviewJob(job_id='job-3', project_id=1, mr_iid=3, sha='c', trigger_type=TriggerType.AUTO))

    await asyncio.sleep(0.05)
    assert manager.queue_depth == 2
    block.set()
