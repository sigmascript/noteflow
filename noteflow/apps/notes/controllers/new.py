"""GET and POST /notes/new."""

from datetime import datetime, timezone

from aurora import Controller, redirect, url_for
from aurora.security import protected_form, login_required

from ....helpers.auth import current_user_id, require_user
from ....helpers.notes import note_values, validate_note
from ....models import Note
from ....helpers.form import note_form


class NewNote(Controller):
    """Display the note form and create a note."""

    @login_required(
        "auth.signin",
        authenticated=lambda request: current_user_id(request) is not None,
        with_next=True,
    )
    def get(self):
        return note_form(
            title="New note",
            action=url_for("notes.new"),
            values={"title": "", "content": ""},
        )

    async def post(self):
        data = await protected_form(self.request)
        user_id = require_user(self.request)
        values = note_values(data)
        error = validate_note(values)

        if error:
            return note_form(
                title="New note",
                action=url_for("notes.new"),
                values=values,
                error=error,
                status_code=400,
            )

        note = Note.create(
            user_id=user_id,
            **values,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        return redirect(url_for("notes.detail", id=note.id))
