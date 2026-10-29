"""Handle GET and POST /notes/{id}/edit."""

from aurora import Controller, View, redirect, url_for
from aurora.core.http_exception import HTTPException
from aurora.security import protected_form

from ....helpers.auth import current_user_id, require_user
from ....helpers.notes import get_owned_note, validate_note
from ....helpers.database_work import database_work
from ....models import Note


class EditNote(Controller):
    """Display and process edits to an owned note."""

    async def get(self, id):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        note = await database_work(
            self.request, lambda connection: get_owned_note(id, user_id)
        )
        return View(
            "notes/form",
            title="Edit note",
            action=url_for("notes.edit", id=note.id),
            values={"title": note.title, "content": note.content},
        )

    async def post(self, id):
        data = await protected_form(self.request)
        user_id = require_user(self.request)
        note = await database_work(
            self.request, lambda connection: get_owned_note(id, user_id)
        )
        values = {
            "title": data.get("title", "").strip(),
            "content": data.get("content", ""),
        }
        error = validate_note(values)

        if error:
            return View(
                "notes/form",
                title="Edit note",
                action=url_for("notes.edit", id=note.id),
                values=values,
                error=error,
                status_code=400,
            )

        # Recheck ownership and write atomically in the same worker connection.
        def update_owned(connection):
            with connection.transaction():
                owned = get_owned_note(id, user_id)
                affected = Note.update(
                    values=values,
                    where={"id": owned.id, "user_id": user_id},
                )
                if affected == 0:
                    raise HTTPException(404, "Note not found")
                return owned.id

        note_id = await database_work(self.request, update_owned)

        return redirect(url_for("notes.detail", id=note_id))
