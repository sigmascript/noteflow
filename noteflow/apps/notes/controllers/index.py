"""GET /notes."""

from aurora import Controller, View, redirect, url_for

from ....helpers.auth import current_user_id
from ....models import Note


class Notes(Controller):
    """List the signed-in user's notes."""

    def get(self):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        notes = Note.read(where={"user_id": user_id}).all()
        notes.sort(key=lambda note: note.id, reverse=True)
        return View("notes/index", title="Notes", notes=notes)
