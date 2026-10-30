"""Alpha 8: concurrent authenticated access and failure isolation contracts."""

import asyncio
import unittest

from noteflow.models import Note
from tests import test_noteflow as baseline


class Alpha8ConcurrentBoundaries(unittest.IsolatedAsyncioTestCase):
    setUp = baseline.NoteFlowIntegrationTests.setUp
    tearDown = baseline.NoteFlowIntegrationTests.tearDown
    register = baseline.NoteFlowIntegrationTests.register
    create_note = baseline.NoteFlowIntegrationTests.create_note

    async def test_parallel_accounts_only_see_their_own_notes(self):
        await self.register(self.alice, "alice")
        await self.register(self.bob, "bob")
        alice_path = await self.create_note(self.alice, "Alice secret")
        bob_path = await self.create_note(self.bob, "Bob secret")

        jobs = []
        for _ in range(8):
            jobs.extend([
                self.alice.request(alice_path),
                self.bob.request(bob_path),
                self.alice.request(bob_path),
                self.bob.request(alice_path),
            ])
        results = await asyncio.gather(*jobs)
        self.assertEqual(
            [status for status, _, _ in results],
            [200, 200, 404, 404] * 8,
        )
        self.assertTrue(
            all("Alice secret" in results[i][2] for i in range(0, len(results), 4))
        )
        self.assertTrue(
            all("Bob secret" in results[i][2] for i in range(1, len(results), 4))
        )

    async def test_parallel_cross_account_writes_cannot_change_owner_note(self):
        await self.register(self.alice, "alice")
        await self.register(self.bob, "bob")
        path = await self.create_note(self.alice, "Protected original")
        token = await self.bob.form_token("/notes/new")

        async def attack(index):
            if index % 2:
                return await self.bob.request(
                    path + "/delete",
                    "POST",
                    {"csrf_token": token},
                )
            return await self.bob.request(
                path + "/edit",
                "POST",
                {
                    "csrf_token": token,
                    "title": f"Unauthorized {index}",
                    "content": "Unauthorized body",
                },
            )

        results = await asyncio.gather(*(attack(i) for i in range(8)))
        self.assertTrue(all(status == 404 for status, _, _ in results))

        status, _, html = await self.alice.request(path)
        self.assertEqual(status, 200)
        self.assertIn("Protected original", html)
        self.assertEqual(
            Note.using(self.database)
            .read(where={"title": "Protected original"})
            .count(),
            1,
        )

    async def test_failed_csrf_write_does_not_block_subsequent_valid_write(self):
        await self.register(self.alice, "alice")
        token = await self.alice.form_token("/notes/new")

        status, _, _ = await self.alice.request(
            "/notes/new",
            "POST",
            {
                "csrf_token": "invalid-token",
                "title": "Should not exist",
                "content": "Blocked",
            },
        )
        self.assertEqual(status, 403)

        status, headers, _ = await self.alice.request(
            "/notes/new",
            "POST",
            {
                "csrf_token": token,
                "title": "Allowed after rejection",
                "content": "Saved",
            },
        )
        self.assertEqual(status, 303)
        self.assertIn(b"/notes/", headers[b"location"])

        self.assertEqual(
            Note.using(self.database)
            .read(where={"title": "Should not exist"})
            .all(),
            [],
        )
        self.assertEqual(
            Note.using(self.database)
            .read(where={"title": "Allowed after rejection"})
            .count(),
            1,
        )
