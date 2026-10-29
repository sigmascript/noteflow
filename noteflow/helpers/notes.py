"""Note-specific validation and ownership rules."""
import re

from aurora.core.http_exception import HTTPException
from aurora import validate
from ..models import Note


def validate_note(values):
    """Return a human-readable validation error, or an empty string."""
    if validate(values, {"title": "required|max:200"}):
        return "Enter a title between 1 and 200 characters."
    if validate(values, {"content": "required|max:20000"}):
        return "Enter note content between 1 and 20,000 characters."
    return ""


def get_owned_note(note_id, user_id):
    """Find a note belonging to this user; never disclose another user's note."""
    if re.fullmatch(r"[1-9][0-9]{0,18}", str(note_id)) is None:
        raise HTTPException(404, "Note not found")

    number = int(note_id)
    if number > 2**63 - 1:
        raise HTTPException(404, "Note not found")

    note = Note.read(where={"id": number, "user_id": user_id}).first()
    if note is None:
        raise HTTPException(404, "Note not found")
    return note
