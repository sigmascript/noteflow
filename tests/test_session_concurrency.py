"""Concurrent authenticated reads must not race to initialize CSRF state."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from noteflow.app import create_app
from noteflow.database import configure_database, create_tables
from tests.test_noteflow import Browser, PASSWORD


class ConcurrentSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_authenticated_page_requests_are_read_only(self):
        with tempfile.TemporaryDirectory(prefix="noteflow-session-race-") as folder:
            base = Path(folder)
            notes_path = base / "notes.sqlite3"
            with configure_database(notes_path) as connection:
                create_tables(connection)

            app = create_app(
                session_database_path=base / "sessions.sqlite3",
                notes_database_path=notes_path,
                secure=False,
            )
            browser = Browser(app)
            status, _, _ = await browser.submit("/auth/signup", {
                "username": "alice",
                "email": "alice@example.invalid",
                "password": PASSWORD,
                "confirm": PASSWORD,
            })
            self.assertEqual(status, 303)

            # Use distinct browser objects sharing the authenticated cookie,
            # just as concurrent tabs share a session token.
            clients = [Browser(app) for _ in range(8)]
            for client in clients:
                client.cookies.update(browser.cookies)

            results = await asyncio.gather(
                *(client.request("/notes") for client in clients)
            )
            self.assertEqual([status for status, _, _ in results], [200] * 8)
            self.assertTrue(all("alice" in body for _, _, body in results))
            self.assertTrue(all(client.cookies == browser.cookies for client in clients))

            # CSRF remains functional with the pre-generated token.
            token = await browser.form_token("/notes")
            self.assertTrue(token)
            status, _, _ = await browser.request(
                "/auth/signout", "POST", {"csrf_token": token}
            )
            self.assertEqual(status, 303)
            self.assertEqual((await browser.request("/notes"))[0], 303)
