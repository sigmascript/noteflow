"""Bounded worker-owned database operations for NoteFlow's ASGI handlers."""

import asyncio
import logging


logger = logging.getLogger(__name__)

from aurora.aurorasql import run_database_work


def create_database_runner(url, *, max_concurrent=4):
    """Limit active workers, including work surviving request cancellation.

    Each callback runs to completion in a worker with its own connection.
    Never pass a Request, session, cursor or connection into the callback.
    """
    if not isinstance(max_concurrent, int) or isinstance(max_concurrent, bool) or max_concurrent < 1:
        raise ValueError("max_concurrent must be a positive integer")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def database_work(callback):
        await semaphore.acquire()
        try:
            task = asyncio.create_task(run_database_work(url, callback))
        except BaseException:
            semaphore.release()
            raise

        def release_after_completion(finished):
            semaphore.release()
            try:
                finished.result()
            except asyncio.CancelledError:
                logger.warning("Database worker task was cancelled unexpectedly")
            except Exception:
                logger.exception("Detached database worker failed after request cancellation")

        # shield prevents request cancellation from cancelling the worker task.
        # Retain the slot until the actual database callback has finished.
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                semaphore.release()
            else:
                task.add_done_callback(release_after_completion)

    return database_work


async def database_work(request, callback):
    """Execute one synchronous, fully materialized database work unit."""
    return await request.scope["noteflow.database_work"](callback)
