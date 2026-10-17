"""GET /notes/{id}."""

from aurora import Controller, View, redirect, url_for

from ....helpers.auth import current_user_id
from ....helpers.notes import get_owned_note


class NoteDetail(Controller):
    """Show a note only to its owner."""

    def get(self, id):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        note = get_owned_note(id, user_id)
        return View("notes/show", title=note.title, note=note)
