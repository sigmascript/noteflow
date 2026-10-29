"""GET /notes."""

from aurora import Controller, View, redirect, url_for

from ....helpers.auth import current_user_id
from ....models import Note

from ....helpers.database_work import database_work


class Notes(Controller):
    """List the signed-in user's notes."""

    async def get(self):
        user_id = current_user_id(self.request)
        if user_id is None:
            return redirect(url_for("auth.signin"))

        notes = await database_work(
            self.request,
            lambda connection: Note.read({"user_id": user_id}, order_by="-id").all(),
        )
        return View("notes/index", title="Notes", notes=notes)
