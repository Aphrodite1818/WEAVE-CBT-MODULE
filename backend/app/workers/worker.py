"""ARQ worker configuation for Weave CBT background jobs"""


from __future__ import annotations
import logging

from arq import cron

from app.core.database import engine
from app.integrations.weave.client import weave_client
from app.workers.broker import arq_redis_settings
from app.workers.candidates import prepare_exam_roster
from app.workers.maintenance import recover_background_work
from app.workers.results import sync_exam_results



logger = logging.getLogger(__name__)


async def on_startup(_ctx : dict) -> None:
    """
    Initiate worker-process resources.

    ARQ itself provides the Redis connection in ctx["redis"], so there is no
    need to create another ARQ  pool here
    """


    logger.info("Weave CBT background worker started")



async def on_shutdown(_ctx : dict) -> None:
    """
    Cleanly release process-local resources owned by the worker
    """

    await weave_client.close()
    await engine.dispose()

    logger.info("Weave CBT background worker stopped")



class WorkerSettings:
    """
    ARQ configuration for the Weave CBT background worker

    Business logic belongs to the domain services. This class only registers
    executable jobs and operational worker settings
    """


    redis_settings = arq_redis_settings


    #registered jobs

    functions = [
        prepare_exam_roster,
        sync_exam_results
    ]




    #Manitenance / recovery

    #Run every two minutes

    #run_at_startup= True means a newly started worker immediately checks
    #PostgreSQL for work which may have been missed while the worker or 
    #Redis was unavailavle

    cron_jobs = [
        cron(
            coroutine=recover_background_work,
            minute = set(range(0, 60 , 2)),
            second = 0,
            run_at_startup=True,
            unique = True
        )
    ]



    #Worker execution policy

    #Allow several async jobs to make progress concurrently without spawning 
    #one process per job/domain

    max_job = 10

    #Roster generation and large result synchronization may legitimately
    #take longer than ordinary HTTP-request work 

    job_timeout = 30 * 60




    #ARQ can retry raised job failures. Domain state and PostgreSQL
    #idempotency makes duplicate execution safe

    max_tries = 5


    keep_result = 60

    on_startup = on_startup
    on_shutdown = on_shutdown