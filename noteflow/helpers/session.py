"""Shared session operation for authentication endpoints."""


async def sign_in(request, user):
    """Rotate the session token before authenticating a user."""
    await request.session.regenerate()
    request.session["user_id"] = user.id
