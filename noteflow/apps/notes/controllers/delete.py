"""GET and POST /notes/{id}/delete."""

from aurora import Controller, View, redirect, url_for
from aurora.core.http_exception import HTTPException
from aurora.security import protected_form

from ....helpers.auth import current_user_id, require_user
from ....helpers.notes import get_owned_note
from ....models import Note


class DeleteNote(Controller):
    """Confirm and delete a note owned by the current user."""

    def get(self, id):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        note = get_owned_note(id, user_id)
        return View("notes/delete", title="Delete note", note=note)

    async def post(self, id):
        await protected_form(self.request)
        user_id = require_user(self.request)
        note = get_owned_note(id, user_id)

        affected = Note.delete(where={"id": note.id, "user_id": user_id})
        if affected == 0:
            raise HTTPException(404, "Note not found")

        return redirect(url_for("notes.index"))
