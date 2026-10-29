"""Free Notes view locations and request-scoped presentation values."""
from pathlib import Path

from aurora.security import csrf_field

from .models import User
from .helpers.database_work import database_work

BASE_DIR = Path(__file__).resolve().parent
VIEW_DIRECTORIES = [
    BASE_DIR / "views",
    BASE_DIR / "apps" / "auth" / "views",
    BASE_DIR / "apps" / "notes" / "views",
]


async def view_context(request):
    """Supply shared view values; no database query for anonymous visitors."""
    user_id = request.session.get("user_id")
    user = (
        await database_work(
            request, lambda connection: User.read(where={"id": user_id}).first()
        )
        if user_id is not None else None
    )
    return {"current_user": user, "request": request, "csrf_field": csrf_field}
