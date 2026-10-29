"""Handle GET and POST /auth/signin."""

from aurora import Controller, View, redirect, url_for
from aurora.security import csrf_token, protected_form, redirect_local, request_next, safe_next

from ....helpers.auth import current_user_id, verify_credentials
from ....models import User

from ....helpers.database_work import database_work


class Signin(Controller):
    """Display the sign-in form and authenticate credentials."""

    def get(self):
        if current_user_id(self.request) is not None:
            return redirect(url_for("notes.index"))

        return View(
            "auth/signin", title="Sign in", error="", username="",
            next_url=request_next(self.request, url_for("notes.index")),
        )

    async def post(self):
        data = await protected_form(self.request)
        if current_user_id(self.request) is not None:
            return redirect(url_for("notes.index"))

        return_to = safe_next(data.get("next"), url_for("notes.index"))
        username = data.get("username", "").strip().lower()
        user = await database_work(
            self.request, lambda connection: User.read(where={"username": username}).first()
        )

        if not await verify_credentials(data.get("password", ""), user):
            return View(
                "auth/signin",
                status_code=400,
                title="Sign in",
                error="Invalid username or password.",
                username=username,
                next_url=return_to,
            )

        # Rotate the session identifier before storing the authenticated user.
        await self.request.session.regenerate()
        self.request.session["user_id"] = user.id
        csrf_token(self.request)
        return redirect_local(return_to)
