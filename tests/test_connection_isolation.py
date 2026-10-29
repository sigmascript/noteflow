"""Verify that NoteFlow database operations run on worker-owned connections."""

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from aurora.aurorasql import Model
from noteflow.app import create_app
from noteflow.database import configure_database, create_tables
from noteflow.helpers.database_work import create_database_runner
from tests.test_noteflow import Browser, PASSWORD


class WorkerBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_database_work_uses_worker_connections(self):
        with tempfile.TemporaryDirectory(prefix="noteflow-workers-") as folder:
            base = Path(folder)
            db_path = base / "notes.sqlite3"
            with configure_database(db_path) as db:
                create_tables(db)
            app = create_app(
                session_database_path=base / "sessions.sqlite3",
                notes_database_path=db_path,
                secure=False,
            )
            browser = Browser(app)
            loop_thread = threading.get_ident()
            import aurora.aurorasql.async_work as worker_module
            original_connect = worker_module.connect
            observed = []

            def observed_connect(url):
                connection = original_connect(url)
                observed.append((threading.get_ident(), connection))
                return connection

            with patch.object(worker_module, "connect", side_effect=observed_connect):
                status, _, _ = await browser.submit("/auth/signup", {
                    "username": "alice",
                    "email": "alice@example.invalid",
                    "password": PASSWORD,
                    "confirm": PASSWORD,
                })
                self.assertEqual(status, 303)
                results = [await browser.request("/notes") for _ in range(5)]

            self.assertTrue(all(status == 200 for status, _, _ in results))
            self.assertGreaterEqual(len(observed), 6)
            self.assertTrue(all(tid != loop_thread for tid, _ in observed))
            self.assertEqual(len({id(connection) for _, connection in observed}), len(observed))
            self.assertTrue(all(connection._closed for _, connection in observed))
            self.assertIsNone(Model.database)

    async def test_cancellation_keeps_worker_slot_until_work_finishes(self):
        runner = create_database_runner("sqlite:///:memory:", max_concurrent=1)
        started = threading.Event()
        finish = threading.Event()
        second_started = threading.Event()

        def first_work(connection):
            started.set()
            if not finish.wait(5):
                raise AssertionError("Timed out waiting to finish first work")
            return 1

        def second_work(connection):
            second_started.set()
            return 2

        first = asyncio.create_task(runner(first_work))
        try:
            await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(runner(second_work))
            await asyncio.sleep(0.05)
            self.assertFalse(second_started.is_set())
        finally:
            finish.set()

        self.assertEqual(await asyncio.wait_for(second, 3), 2)
        self.assertTrue(second_started.is_set())

    async def test_event_loop_remains_responsive_during_database_work(self):
        runner = create_database_runner("sqlite:///:memory:", max_concurrent=1)
        started = threading.Event()
        finish = threading.Event()

        def blocking_work(connection):
            started.set()
            if not finish.wait(5):
                raise AssertionError("Work was not released")
            return 42

        task = asyncio.create_task(runner(blocking_work))
        try:
            self.assertTrue(await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 3))
            self.assertEqual(await asyncio.wait_for(asyncio.sleep(0, result="alive"), 1), "alive")
        finally:
            finish.set()
        self.assertEqual(await asyncio.wait_for(task, 3), 42)
