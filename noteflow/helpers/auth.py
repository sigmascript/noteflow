"""Application authentication and account input rules."""
import re

from aurora.core.http_exception import HTTPException
from aurora import validate
from aurora.security import hash_password, verify_password_async

# Verify even unknown accounts to reduce username-enumeration timing differences.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


def current_user_id(request):
    """Return the signed-in user's ID, or None."""
    return request.session.get("user_id")


def require_user(request):
    """Require a signed-in user for a state-changing request."""
    user_id = current_user_id(request)
    if user_id is None:
        raise HTTPException(403, "Sign in required")
    return user_id


def validate_registration(data):
    """Return normalized account fields and a user-facing validation error."""
    username = data.get("username", "").strip().lower()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if re.fullmatch(r"[a-z0-9_]{3,30}", username) is None:
        error = "Use 3-30 letters, numbers, or underscores for your username."
    elif validate({"email": email}, {"email": "required|email|max:254"}):
        error = "Enter a valid email address."
    elif not 15 <= len(password) <= 128:
        error = "Use a password between 15 and 128 characters."
    elif password != data.get("confirm", ""):
        error = "Passwords do not match."
    else:
        error = ""

    return username, email, password, error


async def verify_credentials(password, user):
    """Perform a password check even when no matching user exists."""
    stored = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid = await verify_password_async(password, stored)
    return user is not None and valid
