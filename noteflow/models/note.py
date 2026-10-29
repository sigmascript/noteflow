from datetime import datetime

from aurora.aurorasql import Model, column


class Note(Model):
    """Store a plain-text note owned by one user."""

    __table__ = "notes"

    id = column(int, primary_key=True)
    user_id = column(int, references="users.id")
    title = column(str, length=200)
    content = column(str)
    created_at = column(datetime)
