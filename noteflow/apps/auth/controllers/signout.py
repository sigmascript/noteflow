"""POST /auth/signout."""

from aurora import Controller, redirect, url_for
from aurora.security import protected_form


class Signout(Controller):
    """Invalidate the session after CSRF validation."""

    async def post(self):
        await protected_form(self.request)
        await self.request.session.invalidate()
        return redirect(url_for("auth.signin"))
