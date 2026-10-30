"""Alpha 8: real HTTP session lifecycle and authentication boundaries."""

import asyncio
import unittest

from noteflow.models import Note
from tests import test_noteflow as baseline


class Alpha8SessionLifecycle(unittest.IsolatedAsyncioTestCase):
    """Exercise sessions through the same ASGI browser as NoteFlow."""

    setUp = baseline.NoteFlowIntegrationTests.setUp
    tearDown = baseline.NoteFlowIntegrationTests.tearDown
    register = baseline.NoteFlowIntegrationTests.register
    create_note = baseline.NoteFlowIntegrationTests.create_note

    async def test_signout_revokes_access_without_affecting_another_account(self):
        await self.register(self.alice, "alice")
        await self.register(self.bob, "bob")
        alice_path = await self.create_note(self.alice, "Alice private after logout")
        bob_path = await self.create_note(self.bob, "Bob remains signed in")

        status, _, _ = await self.alice.submit(
            "/auth/signout", {}, token_path="/notes"
        )
        self.assertEqual(status, 303)
        results = await asyncio.gather(
            self.alice.request(alice_path),
            self.alice.request(bob_path),
            self.bob.request(bob_path),
            self.bob.request(alice_path),
        )
        self.assertEqual([item[0] for item in results], [303, 303, 200, 404])
        self.assertEqual(
            Note.using(self.database).read(where={"title": "Alice private after logout"}).count(),
            1,
        )

    async def test_old_csrf_cannot_write_after_signout_and_signin(self):
        await self.register(self.alice, "alice")
        old_token = await self.alice.form_token("/notes/new")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")
        status, _, _ = await self.alice.submit("/auth/signin", {
            "username": "alice", "password": baseline.PASSWORD,
        })
        self.assertEqual(status, 303)

        status, _, _ = await self.alice.request("/notes/new", "POST", {
            "csrf_token": old_token,
            "title": "Stale session token", "content": "Must not persist",
        })
        self.assertEqual(status, 403)
        self.assertEqual(
            Note.using(self.database).read(where={"title": "Stale session token"}).count(),
            0,
        )
        status, _, _ = await self.alice.submit("/notes/new", {
            "title": "Fresh session token", "content": "Persisted",
        })
        self.assertEqual(status, 303)

    async def test_failed_signin_does_not_authenticate_or_block_valid_signin(self):
        await self.register(self.alice, "alice")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")

        status, _, _ = await self.alice.submit("/auth/signin", {
            "username": "alice", "password": "incorrect",
        })
        self.assertEqual(status, 400)
        self.assertEqual((await self.alice.request("/notes"))[0], 303)

        status, _, _ = await self.alice.submit("/auth/signin", {
            "username": "alice", "password": baseline.PASSWORD,
        })
        self.assertEqual(status, 303)
        self.assertEqual((await self.alice.request("/notes"))[0], 200)
