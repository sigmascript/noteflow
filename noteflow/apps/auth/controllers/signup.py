"""Handle GET and POST /auth/signup."""

import sqlite3

from aurora import Controller, View, redirect, url_for
from aurora.security import csrf_token, hash_password_async, protected_form

from ....helpers.auth import current_user_id, validate_registration
from ....models import User

from ....helpers.database_work import database_work


class Signup(Controller):
    """Display the registration form and create accounts."""

    def get(self):
        if current_user_id(self.request) is not None:
            return redirect(url_for("notes.index"))

        return View(
            "auth/signup",
            title="Create account",
            error="",
            username="",
            email="",
        )

    async def post(self):
        data = await protected_form(self.request)
        if current_user_id(self.request) is not None:
            return redirect(url_for("notes.index"))

        username, email, password, error = validate_registration(data)
        if not error:
            password_hash = await hash_password_async(password)

            try:
                user = await database_work(
                    self.request,
                    lambda connection: User.create(
                        username=username, email=email, password_hash=password_hash
                    ),
                )
            except sqlite3.IntegrityError:
                # Database uniqueness also protects concurrent registrations.
                error = "Username or email is already registered."
            else:
                await self.request.session.regenerate()
                self.request.session["user_id"] = user.id
                csrf_token(self.request)
                return redirect(url_for("notes.index"))

        return View(
            "auth/signup",
            status_code=400,
            title="Create account",
            error=error,
            username=username,
            email=email,
        )
