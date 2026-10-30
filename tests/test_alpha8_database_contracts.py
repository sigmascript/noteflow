"""Alpha 8: real NoteFlow model and worker integration safety contracts."""

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aurora.aurorasql import Model
from noteflow.database import configure_database, create_tables, database_url
from noteflow.helpers.database_work import create_database_runner
from noteflow.models import Note, User


class NoteFlowDatabaseContracts(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="noteflow-alpha8-")
        self.path = Path(self.folder.name) / "notes.sqlite3"
        with configure_database(self.path) as connection:
            create_tables(connection)
        self.runner = create_database_runner(database_url(self.path), max_concurrent=2)

    def tearDown(self):
        self.folder.cleanup()

    async def test_failed_multi_model_transaction_rolls_back(self):
        def work(connection):
            with connection.transaction():
                user = User.create(
                    username="rollback", email="rollback@example.invalid",
                    password_hash="not-a-real-password-hash",
                )
                Note.create(
                    user_id=user.id, title="temporary", content="temporary",
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                raise RuntimeError("deliberate rollback")

        with self.assertRaisesRegex(RuntimeError, "deliberate rollback"):
            await self.runner(work)

        with configure_database(self.path) as connection:
            self.assertEqual(User.using(connection).all(), [])
            self.assertEqual(Note.using(connection).all(), [])
        self.assertIsNone(Model.database)

    async def test_failed_worker_does_not_poison_following_request(self):
        def failed(connection):
            with connection.transaction():
                User.create(
                    username="reused", email="reused@example.invalid",
                    password_hash="not-a-real-password-hash",
                )
                raise ValueError("abort request")

        with self.assertRaisesRegex(ValueError, "abort request"):
            await self.runner(failed)

        def succeeded(connection):
            with connection.transaction():
                return User.create(
                    username="reused", email="reused@example.invalid",
                    password_hash="not-a-real-password-hash",
                ).id

        user_id = await self.runner(succeeded)
        with configure_database(self.path) as connection:
            users = User.using(connection).all()
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0].id, user_id)
        self.assertIsNone(Model.database)

    async def test_concurrent_workers_keep_model_bindings_isolated(self):
        def count_users(connection):
            return User.read().count()

        results = await asyncio.gather(*(self.runner(count_users) for _ in range(8)))
        self.assertEqual(results, [0] * 8)
        self.assertIsNone(Model.database)
