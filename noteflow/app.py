"""NoteFlow ASGI entry point and explicit application factory."""
from pathlib import Path

from aurora import Aurora, View
from aurora.security.sessions import SessionSettings

from .apps.auth.controllers import Signin, Signup, Signout
from .apps.notes.controllers import (
    Notes, NewNote, NoteDetail, EditNote, DeleteNote,
)
from .presentation import VIEW_DIRECTORIES, view_context
from .database import configure_database, database_url
from .helpers.database_work import create_database_runner


def create_app(*, session_database_path, secure=True, notes_database_path=None):
    """Build the migrated app with explicit session storage configuration."""
    app = Aurora(
        views_directory=VIEW_DIRECTORIES,
        view_context=view_context,
        view_headers={"Cache-Control": "no-store"},
        sessions=SessionSettings(
            database_path=str(session_database_path), secure=secure,
        ),
    )

    # The session and HTTP lifecycle remain on the event loop. Only complete
    # synchronous database callbacks execute on worker-owned connections.
    notes_url = database_url(notes_database_path) if notes_database_path else database_url()
    database_work = create_database_runner(notes_url, max_concurrent=4)

    async def database_scope(request, call_next):
        request.scope["noteflow.database_work"] = database_work
        return await call_next(request)

    app.add_middleware(database_scope)

    def home(request):
        return View("home", title="NoteFlow")

    app.add_route("/", home, name="home")

    # One URL, one controller. HTTP verbs dispatch to get()/post().
    app.route("/auth/signin", Signin, name="auth.signin")
    app.route("/auth/signup", Signup, name="auth.signup")
    app.route("/auth/signout", Signout, name="auth.signout")

    app.route("/notes", Notes, name="notes.index")
    app.route("/notes/new", NewNote, name="notes.new")
    app.route("/notes/{id}", NoteDetail, name="notes.detail")
    app.route("/notes/{id}/edit", EditNote, name="notes.edit")
    app.route("/notes/{id}/delete", DeleteNote, name="notes.delete")

    return app


# Local ASGI entry point. This explicit binding is application-specific;
# create_app() itself does not bind models or create application tables.
# Use secure=True for HTTPS deployments.
LOCAL_SESSION_DATABASE = Path(__file__).resolve().parent / "noteflow_sessions.sqlite3"
app = create_app(session_database_path=LOCAL_SESSION_DATABASE, secure=False)
