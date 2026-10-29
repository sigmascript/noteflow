"""Explicit AuroraSQL connections for NoteFlow's disposable SQLite database."""

from pathlib import Path

from aurora.aurorasql import Model, connect, create_tables as create_model_tables

from .models import Note, User


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "noteflow.sqlite3"


def database_url(path=DATABASE_PATH):
    """Build an absolute SQLite URL without creating a database."""
    return f"sqlite:///{Path(path).resolve().as_posix()}"


def configure_database(path=DATABASE_PATH):
    """Open a caller-owned AuroraSQL connection; no global model binding."""
    return connect(database_url(path))


def create_tables(database):
    """Initialize only an explicitly selected, empty database.

    This is a disposable development bootstrap, not a migration operation.
    """
    existing = database.fetch_all(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name IN ('users', 'notes')"
    )
    if existing:
        raise RuntimeError("Refusing to initialize an existing NoteFlow schema")
    create_model_tables(database, User, Note)
