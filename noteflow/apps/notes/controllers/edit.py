"""GET and POST /notes/{id}/edit."""

from aurora import Controller, redirect, url_for
from aurora.core.http_exception import HTTPException
from aurora.security import protected_form

from ....helpers.auth import current_user_id, require_user
from ....helpers.notes import get_owned_note, note_values, validate_note
from ....models import Note
from ....helpers.form import note_form


class EditNote(Controller):
    """Display and process edits to an owned note."""

    def get(self, id):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        note = get_owned_note(id, user_id)
        return note_form(
            title="Edit note",
            action=url_for("notes.edit", id=note.id),
            values={"title": note.title, "content": note.content},
        )

    async def post(self, id):
        data = await protected_form(self.request)
        user_id = require_user(self.request)
        note = get_owned_note(id, user_id)
        values = note_values(data)
        error = validate_note(values)

        if error:
            return note_form(
                title="Edit note",
                action=url_for("notes.edit", id=note.id),
                values=values,
                error=error,
                status_code=400,
            )

        # Scope the UPDATE by owner even after the initial ownership check.
        affected = Note.update(
            values=values,
            where={"id": note.id, "user_id": user_id},
        )
        if affected == 0:
            raise HTTPException(404, "Note not found")

        return redirect(url_for("notes.detail", id=note.id))
