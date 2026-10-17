from pathlib import Path

from sqlalchemy import event

from aurora.database import Database, Model

from .models import Note, User


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "noteflow.sqlite3"


def configure_database(path=DATABASE_PATH) -> Database:
    """Bind the models to SQLite and return the caller-owned database."""
    database = Database(f"sqlite:///{Path(path).resolve().as_posix()}")

    # SQLite requires foreign-key enforcement on every connection.
    @event.listens_for(database.engine, "connect")
    def enable_foreign_keys(connection, connection_record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    Model.bind(database)
    return database


def create_tables(database: Database) -> None:
    """Create missing model tables; existing schemas are not migrated."""
    database.create_tables(Model.metadata)
