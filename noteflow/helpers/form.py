"""Shared presentation helper for the note form."""

from aurora import View


def note_form(*, title, action, values, error="", status_code=200):
    """Render the same form for creating and editing notes."""
    return View(
        "notes/form",
        status_code=status_code,
        title=title,
        action=action,
        values=values,
        error=error,
    )
