"""Exercise NoteFlow through ASGI with isolated application databases."""

import re
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from aurora.database import Model

from noteflow.app import create_app
from noteflow.database import configure_database, create_tables
from noteflow.models import Note, User


PASSWORD = "a long example passphrase"
TOKEN_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


class Browser:
    """Small ASGI browser that retains its own session cookies."""

    def __init__(self, app):
        self.app = app
        self.cookies = {}

    async def request(self, path, method="GET", data=None):
        parsed = urlsplit(path)
        body = urlencode(data or {}).encode("utf-8")
        headers = [(b"content-type", b"application/x-www-form-urlencoded")]
        if self.cookies:
            cookie_header = "; ".join(
                f"{key}={value}" for key, value in self.cookies.items()
            )
            headers.append((b"cookie", cookie_header.encode("ascii")))

        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "scheme": "http",
            "server": ("localhost", 80),
            "client": ("127.0.0.1", 12345),
            "method": method,
            "path": parsed.path,
            "raw_path": parsed.path.encode("ascii"),
            "root_path": "",
            "query_string": parsed.query.encode("ascii"),
            "headers": headers,
        }
        await self.app(scope, receive, send)

        start = next(message for message in messages if message["type"] == "http.response.start")
        for key, value in start["headers"]:
            if key.lower() != b"set-cookie":
                continue
            cookie = SimpleCookie()
            cookie.load(value.decode("latin-1"))
            for name, morsel in cookie.items():
                if morsel["max-age"] == "0" or not morsel.value:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = morsel.value

        content = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        response_headers = dict(start["headers"])
        return start["status"], response_headers, content.decode("utf-8")

    async def form_token(self, path):
        status, _, html = await self.request(path)
        if status != 200:
            raise AssertionError(f"GET {path} returned {status}, not 200")
        match = TOKEN_PATTERN.search(html)
        if match is None:
            raise AssertionError(f"No CSRF token in {path}")
        return match.group(1)

    async def submit(self, path, data, *, token_path=None):
        token = await self.form_token(token_path or path)
        return await self.request(path, "POST", {"csrf_token": token, **data})


class NoteFlowIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_database = Model.database
        self.directory = tempfile.TemporaryDirectory(prefix="noteflow-test-")
        base = Path(self.directory.name)
        self.database = configure_database(base / "notes.sqlite3")
        create_tables(self.database)
        self.app = create_app(
            session_database_path=base / "sessions.sqlite3", secure=False
        )
        self.alice = Browser(self.app)
        self.bob = Browser(self.app)

    def tearDown(self):
        self.database.dispose()
        Model.database = self.previous_database
        self.directory.cleanup()

    async def register(self, browser, username):
        status, _, body = await browser.submit("/auth/signup", {
            "username": username,
            "email": f"{username}@example.invalid",
            "password": PASSWORD,
            "confirm": PASSWORD,
        })
        self.assertEqual(status, 303, body)

    async def create_note(self, browser, title):
        status, headers, body = await browser.submit("/notes/new", {
            "title": title, "content": "Private note content",
        })
        self.assertEqual(status, 303, body)
        location = headers.get(b"location", b"").decode("latin-1")
        self.assertRegex(location, r"/notes/[1-9][0-9]*$")
        return location

    async def test_home_and_anonymous_access(self):
        self.assertEqual((await self.alice.request("/"))[0], 200)
        self.assertEqual((await self.alice.request("/notes"))[0], 303)
        self.assertEqual((await self.alice.request("/notes/new"))[0], 303)
        self.assertEqual((await self.alice.request("/auth/signup"))[0], 200)

    async def test_registration_and_signout(self):
        await self.register(self.alice, "alice")
        status, _, html = await self.alice.request("/notes")
        self.assertEqual(status, 200)
        self.assertIn("alice", html)
        status, _, _ = await self.alice.submit(
            "/auth/signout", {}, token_path="/notes"
        )
        self.assertEqual(status, 303)
        self.assertEqual((await self.alice.request("/notes"))[0], 303)

    async def test_signin_and_invalid_credentials(self):
        await self.register(self.alice, "alice")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")
        status, _, html = await self.alice.submit("/auth/signin", {
            "username": "alice", "password": "wrong password",
        })
        self.assertEqual(status, 400)
        self.assertIn("Invalid username or password", html)
        status, _, _ = await self.alice.submit("/auth/signin", {
            "username": "alice", "password": PASSWORD,
        })
        self.assertEqual(status, 303)
        self.assertEqual((await self.alice.request("/notes"))[0], 200)

    async def test_registration_validation_and_duplicate_account(self):
        status, _, html = await self.alice.submit("/auth/signup", {
            "username": "alice", "email": "not-an-email",
            "password": PASSWORD, "confirm": PASSWORD,
        })
        self.assertEqual(status, 400)
        self.assertIn("valid email", html)
        await self.register(self.alice, "alice")
        status, _, html = await self.bob.submit("/auth/signup", {
            "username": "alice", "email": "another@example.invalid",
            "password": PASSWORD, "confirm": PASSWORD,
        })
        self.assertEqual(status, 400)
        self.assertIn("already registered", html)

    async def test_crud_and_ownership(self):
        await self.register(self.alice, "alice")
        await self.register(self.bob, "bob")
        path = await self.create_note(self.alice, "Alice private")
        self.assertEqual((await self.alice.request(path))[0], 200)
        self.assertEqual((await self.bob.request(path))[0], 404)
        self.assertEqual((await self.bob.request(path + "/edit"))[0], 404)
        self.assertEqual((await self.bob.request(path + "/delete"))[0], 404)
        status, _, _ = await self.alice.submit(path + "/edit", {
            "title": "Updated title", "content": "Updated body",
        })
        self.assertEqual(status, 303)
        self.assertIn("Updated title", (await self.alice.request(path))[2])
        self.assertEqual((await self.bob.request(path))[0], 404)
        status, _, _ = await self.alice.submit(path + "/delete", {})
        self.assertEqual(status, 303)
        self.assertEqual((await self.alice.request(path))[0], 404)

    async def test_cross_account_writes_are_forbidden(self):
        await self.register(self.alice, "alice")
        await self.register(self.bob, "bob")
        path = await self.create_note(self.alice, "Original title")
        status, _, _ = await self.bob.submit(path + "/edit", {
            "title": "Attack", "content": "Attack",
        }, token_path="/notes/new")
        self.assertEqual(status, 404)
        status, _, _ = await self.bob.submit(
            path + "/delete", {}, token_path="/notes/new"
        )
        self.assertEqual(status, 404)
        self.assertIn("Original title", (await self.alice.request(path))[2])

    async def test_missing_csrf_rejected(self):
        await self.alice.form_token("/auth/signup")
        status, _, _ = await self.alice.request("/auth/signup", "POST", {
            "username": "alice", "email": "alice@example.invalid",
            "password": PASSWORD, "confirm": PASSWORD,
        })
        self.assertEqual(status, 403)
        self.assertIsNone(User.read(where={"username": "alice"}).first())

    async def test_old_csrf_rejected_after_authentication(self):
        old_token = await self.alice.form_token("/auth/signup")
        await self.register(self.alice, "alice")
        status, _, _ = await self.alice.request("/notes/new", "POST", {
            "csrf_token": old_token, "title": "Blocked", "content": "Blocked",
        })
        self.assertEqual(status, 403)
        self.assertEqual(Note.read(where={"title": "Blocked"}).all(), [])

    async def test_anonymous_post_with_csrf_is_forbidden(self):
        token = await self.alice.form_token("/auth/signup")
        status, _, _ = await self.alice.request("/notes/new", "POST", {
            "csrf_token": token, "title": "Blocked", "content": "Blocked",
        })
        self.assertEqual(status, 403)

    async def test_note_validation(self):
        await self.register(self.alice, "alice")
        status, _, html = await self.alice.submit("/notes/new", {
            "title": "  ", "content": "Valid content",
        })
        self.assertEqual(status, 400)
        self.assertIn("Enter a title", html)

    async def test_invalid_note_ids_are_not_disclosed(self):
        await self.register(self.alice, "alice")
        for path in ("/notes/0", "/notes/999999999999999999999", "/notes/123456789"):
            with self.subTest(path=path):
                self.assertEqual((await self.alice.request(path))[0], 404)


    async def test_safe_return_after_signin(self):
        await self.register(self.alice, "alice")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")

        status, headers, _ = await self.alice.request("/notes/new")
        self.assertEqual(status, 303)
        signin_path = headers[b"location"].decode("latin-1")
        self.assertEqual(signin_path, "/auth/signin?next=%2Fnotes%2Fnew")

        token = await self.alice.form_token(signin_path)
        status, _, html = await self.alice.request(signin_path)
        self.assertEqual(status, 200)
        self.assertIn('name="next" value="/notes/new"', html)

        status, headers, _ = await self.alice.request("/auth/signin", "POST", {
            "csrf_token": token, "username": "alice",
            "password": PASSWORD, "next": "/notes/new",
        })
        self.assertEqual(status, 303)
        self.assertEqual(headers[b"location"], b"/notes/new")
        self.assertEqual((await self.alice.request("/notes/new"))[0], 200)

    async def test_external_return_url_is_rejected(self):
        await self.register(self.alice, "alice")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")

        signin_path = "/auth/signin?next=https%3A%2F%2Fevil.example"
        token = await self.alice.form_token(signin_path)
        status, _, html = await self.alice.request(signin_path)
        self.assertEqual(status, 200)
        self.assertIn('name="next" value="/notes"', html)

        status, headers, _ = await self.alice.request("/auth/signin", "POST", {
            "csrf_token": token, "username": "alice",
            "password": PASSWORD, "next": "//evil.example",
        })
        self.assertEqual(status, 303)
        self.assertEqual(headers[b"location"], b"/notes")

    async def test_failed_signin_preserves_safe_return_and_csrf(self):
        await self.register(self.alice, "alice")
        await self.alice.submit("/auth/signout", {}, token_path="/notes")

        token = await self.alice.form_token("/auth/signin?next=%2Fnotes%2Fnew")
        status, _, html = await self.alice.request("/auth/signin", "POST", {
            "csrf_token": token, "username": "alice",
            "password": "incorrect", "next": "/notes/new",
        })
        self.assertEqual(status, 400)
        self.assertIn('name="next" value="/notes/new"', html)
        self.assertRegex(html, TOKEN_PATTERN)


if __name__ == "__main__":
    unittest.main()
